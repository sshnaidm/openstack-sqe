#!/usr/bin/env python
__author__ = 'Sergey Shnaidman <sshnaidm@cisco.com>'

import os
import time
import ConfigParser
#import pygithub3
from pygithub3 import Github
import requests
import json
import urllib3
import sys
from itertools import chain
from datetime import datetime
import logging
#from gevent import monkey
#monkey.patch_all()

#pygithub3.services.base.Service(login="terrrakot", password="hot78dog")

LOG_FILENAME = 'github_poller.log'
CONFIG_FILE="./github_poller.cfg"
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    filename=LOG_FILENAME,
                    filemode='w')
log = logging.getLogger('log')

def parse_config():
    log.debug("Parsing config")
    parser = ConfigParser.SafeConfigParser()
    parser.optionxform = str
    parser.read(CONFIG_FILE)
    config = {}
    config['repos'] = dict(parser.items("repos"))
    config['repo_poll'] = int(parser.get("timeouts", "repo_poll"))
    config['jenkins'] = dict(parser.items("jenkins"))
    config['commit_poll'] = int(parser.get("timeouts", "commit_poll"))
    config['credentials'] = dict(parser.items("github"))
    log.debug("Configuration: %s" % str(config))
    return config

def get_last_commit(config, repo, branch):
    log.debug("Getting last commit from repo: %s branch: %s" % (repo, branch))
    user, rep = repo.split("/")
    gh = Github(user=user, repo=rep, **config['credentials'])
    branch_coms = gh.repos.commits.list(sha=branch)
    try:
        page = next(branch_coms, None)
        if page:
            log.debug("%s:%s found page: %s" % (repo, branch, page.page))
            commit = next(page.iterable, '')
            log.debug("%s:%s last commit: %s" % (repo, branch, commit.sha))
            return commit
    except Exception as e:
        log.debug("%s:%s FAIL to retrieve last commit:\n%s" % (repo, branch, str(e)))
        return ""

def get_start_values(config):
    start = {}
    for repo, branch in config['repos'].items():
        #time.sleep(config['commit_poll'])
        start[repo] = get_last_commit(config, repo, branch)
    return start

def check_n_trigger(config, start):
    for repo, branch in config['repos'].items():
        latest = get_last_commit(config, repo, branch)
        log.debug("%s:%s Check-n-trigger: start_commit=%s and last_commit=%s" % (
            repo, branch, start[repo], latest))
        if start[repo].sha != latest.sha:
            trigger_jenkins(config, repo, branch, start[repo], latest)
        #time.sleep(config['commit_poll'])

def trigger_jenkins(conf, repo, branch, start, end):
    log.debug("%s:%s Triggering Jenkins job!" % (repo, branch))
    diff = pretty_print_diff(calculate_diff(conf, repo, branch, start, end))
    log.debug("%s:%s Difference is:\n%s"  % (repo, branch, diff))
    jenkins_url = (conf["jenkins"]["url"] + "/job/" + conf["jenkins"]["job"] + "/build" +
                   "?token=" + conf["jenkins"]["token"])
    log.debug("%s:%s Jenkins URL=%s"% (repo, branch, jenkins_url))
    params = {"parameter":
                  [{"name": "tag", "value": "network"},
                   {"name": "changes_file", "file": "file0"}],
              "statusCode": "303", "redirectTo": "."}
    log.debug("%s:%s Parameters for Jenkins URL: %s"% (repo, branch, str(params)))
    data, content_type = urllib3.encode_multipart_formdata([
        ("file0", ("changes_file", diff)),
        ("json", json.dumps(params)),
        ("Submit", "Build"),
    ])
    resp = requests.post(jenkins_url,
                         data=data,
                         headers={"content-type": content_type},
                         verify=False)
    log.debug("%s:%s Response from Jenkins: %s\n%s" % (
        repo, branch, str(resp.status_code), resp.content))
    if not resp.ok:
        log.debug("Failed to post URL: %s" % jenkins_url)

def calculate_diff(config, repo, branch, start, end):
    log.debug("%s:%s Calculate diff from %s to %s" % (repo, branch, start, end))
    user, rep = repo.split("/")
    gh = Github(user=user, repo=rep, **config['credentials'])
    commits = list(gh.repos.commits.list(sha=branch))
    begin = finish = None
    diff = []
    for k, i in enumerate(chain(*[chain(z) for z in commits])):
        if i.sha == start:
            begin = k
        if begin is not None:
            diff.append(i)
        if i.sha == end:
            finish = k
            break
    log.debug("%s:%s Diff: begin=%s finish=%s, len(diff)=%s" % (
        repo, branch, begin, finish, len(diff)))
    if begin and finish:
        return gh.repos.commits.compare(
            diff[-1].sha,
            diff[0].sha,
            user=user,
            repo=rep)

def pretty_print_diff(delta):
    if delta is None:
        return "Changes couldn't be calculated"
    text = "<h4>Changeset</h4>\n"
    text += """<p>Statistics: Total commits: %{total}
 <a href="{diff_url}">Files changed</a>: {len_files}</p>
<ul>
            """.format(
        total=delta.total_commits,
        diff_url=delta.html_url,
        len_files=len(delta.files))
    for commit in delta.commits[:-1]:
        text += """<li>
{date} <a href="{author_url}">{author}</a> (<a href="mailto:{mail}">{mail}</a>)
<br><a href="{url}">{message}</a>
</li>
        """.format(
            url=commit.html_url,
            message=commit.commit['message'],
            author_url=commit.committer.html_url,
            author=commit.commit['author']['name'],
            mail=commit.commit['author']['email'],
            date=datetime.strftime(commit.commit['author']['date'], "%c")
        )
    text += "</ul>"
    return text

def main():
    conf = parse_config()
    start_values = get_start_values(conf)
    while True:
        log.debug("Sleeping %s seconds" % conf['repo_poll'])
        time.sleep(conf['repo_poll'])
        check_n_trigger(conf, start_values)

if __name__ == "__main__":
    main()
