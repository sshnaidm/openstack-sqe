#!/usr/bin/env python
import argparse
import time
import ConfigParser
from pygithub3 import Github
import requests
import json
import urllib3
from itertools import chain
from datetime import datetime
import logging

__author__ = 'Sergey Shnaidman <sshnaidm@cisco.com>'


def parse_config(config_file):
    log.debug("Parsing config")
    parser = ConfigParser.SafeConfigParser()
    parser.optionxform = str
    parser.read(config_file)
    config = dict()
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


def check_n_trigger(config, start, conf_file):
    for repo, branch in config['repos'].items():
        latest = get_last_commit(config, repo, branch)
        log.debug("%s:%s Check-n-trigger: start_commit=%s and last_commit=%s" % (
            repo, branch, start[repo], latest))
        if start[repo].sha != latest.sha:
            trigger_jenkins(config, repo, branch, start[repo], latest, conf_file)
            start[repo] = latest
        #time.sleep(config['commit_poll'])


def trigger_jenkins(conf, repo, branch, start, end, conf_file):
    log.info("%s:%s Triggering Jenkins job!" % (repo, branch))
    diff = pretty_print_diff(calculate_diff(conf, repo, branch, start, end))
    log.info("%s:%s Difference is:\n%s" % (repo, branch, diff))
    jenkins_url = (conf["jenkins"]["url"] + "/job/" + conf["jenkins"]["job"] + "/build" +
                   "?token=" + conf["jenkins"]["token"])
    log.info("%s:%s Jenkins URL=%s" % (repo, branch, jenkins_url))
    params = {"parameter": [
        {"name": "tag", "value": "network"},
        {"name": conf_file, "file": "file0"}],
        "statusCode": "303",
        "redirectTo": "."}
    log.info("%s:%s Parameters for Jenkins URL: %s" % (repo, branch, str(params)))
    data, content_type = urllib3.encode_multipart_formdata([
        ("file0", ("changes_file", diff)),
        ("json", json.dumps(params)),
        ("Submit", "Build"),
    ])
    resp = requests.post(jenkins_url,
                         data=data,
                         headers={"content-type": content_type},
                         verify=False)
    log.info("%s:%s Response from Jenkins: %s\n%s" % (
        repo, branch, str(resp.status_code), resp.content))
    if not resp.ok:
        log.info("Failed to post URL: %s" % jenkins_url)


def calculate_diff(config, repo, branch, start, end):
    log.debug("%s:%s Calculate diff from %s to %s" % (repo, branch, start, end))
    user, rep = repo.split("/")
    gh = Github(user=user, repo=rep, **config['credentials'])
    commits = list(gh.repos.commits.list(sha=branch))
    begin = finish = None
    diff = []
    for k, i in enumerate(chain(*[chain(z) for z in commits])):
        if i.sha == end.sha:
            begin = k
        if begin is not None:
            diff.append(i)
        if i.sha == start.sha:
            finish = k
            break
    log.debug("%s:%s Diff: begin=%s finish=%s, len(diff)=%s" % (
        repo, branch, begin, finish, len(diff)))
    if begin is not None and finish is not None:
        return gh.repos.commits.compare(
            diff[-1].sha,
            diff[0].sha,
            user=user,
            repo=rep)


def pretty_print_diff(delta):
    if delta is None:
        return "Changes couldn't be calculated"
    text = "<h4>Changeset</h4>\n"
    text += """<p>Statistics: Total commits: {total}
 <a href="{diff_url}">Files changed</a>: {len_files}</p>
<ul>
            """.format(
        total=delta.total_commits,
        diff_url=delta.html_url,
        len_files=len(delta.files))
    for commit in delta.commits:
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
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', action='store', dest='config_file', default="changes_file",
                        help='Configuration file path')
    parser.add_argument('-l', action='store', dest='log_file', default="./github_poller.log",
                        help='Log file path')
    parser.add_argument('--version', action='version', version='%(prog)s 2.0')

    opts = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename=opts.log_file,
                        filemode='w')
    global log
    log = logging.getLogger('log')

    conf = parse_config(opts.config_file)
    start_values = get_start_values(conf)
    while True:
        log.debug("Sleeping %s seconds" % conf['repo_poll'])
        time.sleep(conf['repo_poll'])
        check_n_trigger(conf, start_values, opts.config_file)

if __name__ == "__main__":
    main()
