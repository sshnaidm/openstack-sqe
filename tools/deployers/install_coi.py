#!/usr/bin/env python
from aio import AIO
from devstack import Devstack, DevstackDeploy
from role2 import Role2, Role2Deploy
from fullha import FullHA, FullHADeploy
from config import opts, ssh_key_file, verb_mode
from StringIO import StringIO
from fabric.colors import green, red

from common import prepare_repo, prepare_hosts, check_results

__author__ = 'sshnaidm'

import yaml

from utils import warn_if_fail, collect_logs, resolve_names, update_time, all_servers
from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists, contains, append, sed



def main():

    params = opts, ssh_key_file, verb_mode
    mapa = {
        "all-in-one": AIO,
        "devstack": Devstack,
        "2role": Role2,
        "fullha": FullHA,

    }
    deployer = mapa[opts.scenario](*params)
    deployer.run()

if __name__ == "__main__":
    main()
