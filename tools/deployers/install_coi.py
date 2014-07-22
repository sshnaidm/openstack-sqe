#!/usr/bin/env python
from aio import AIO
from devstack import Devstack, DevstackDeploy
from role2 import Role2, Role2Deploy
from fullha import FullHA, FullHADeploy
from config import opts, ssh_key_file, verb_mode

__author__ = 'sshnaidm'


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
