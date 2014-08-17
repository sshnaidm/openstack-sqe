#!/usr/bin/env python
__author__ = 'Sergey Shnaidman <sshnaidm@cisco.com>'

import os
import time
import ConfigParser
from pygithub3 import Github
import requests
import json
import urllib3
import sys

CONFIG_FILE="./github_poller.cfg"

def parse_config():
    parser = ConfigParser.SafeConfigParser()
    parser.optionxform = str
    parser.read(CONFIG_FILE)
    config = {}
    config['repos'] = dict(parser.items("repos"))
    config['repo_poll'] = parser.get("timeouts", "repo_poll")
    config['jenkins'] = dict(parser.items("jenkins"))
    return config

def get_last_commit(repo, branch):
    user, rep = repo.split("/")
    gh = Github(user=user, repo=rep)
    branch_coms = gh.repos.commits.list(sha=branch)
    page = next(branch_coms, None)
    if page:
        commit = next(page.iterable, '')
        return commit

def get_start_values(config):
    start = {}
    for repo, branch in config['repos'].items():
        start[repo] = get_last_commit(repo, branch)
    return start

def check_n_trigger(config, start):
    for repo, branch in config['repos'].items():
        latest = get_last_commit(repo, branch)
        if start[repo] != latest:
            trigger_jenkins(config, start[repo], latest)

def trigger_jenkins(conf, start, end):
    diff = calculate_diff(start, end)
    jenkins_url = (conf["jenkins"]["url"] + "/job/" + conf["jenkins"]["job"] + "/build" +
                   "?token=" + conf["jenkins"]["token"])
    params = {"parameter":
                  [{"name": "tag", "value": "network"},
                   {"name": "changes_file", "file": "file0"}],
              "statusCode": "303", "redirectTo": "."}
    data, content_type = urllib3.encode_multipart_formdata([
        ("file0", ("changes_file", diff)),
        ("json", json.dumps(params)),
        ("Submit", "Build"),
    ])
    resp = requests.post(jenkins_url,
                         data=data,
                         headers={"content-type": content_type},
                         verify=False)
    if not resp.ok:
        print >> sys.stderr, "Failed to post URL: %" % jenkins_url

def calculate_diff(start, end):
    return "This file contains a lot\nof changes\nof changes\nof changes\nof changes"

def main():
    conf = parse_config()
    start_values = get_start_values(conf)
    while True:
        time.sleep(conf['repo_poll'])
        check_n_trigger(conf, start_values)

if __name__ == "__main__":
    main()
