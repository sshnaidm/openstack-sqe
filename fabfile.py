#!/usr/bin/env python

import os, pip
from fabric.api import task, local, env
from fabs.common import LVENV, CVENV, timed, virtual
from fabs.common import logger as log
from fabs import coi, tempest


env.host_string = "localhost"
env.abort_on_prompts = True
env.warn_only = True

@timed
def venv(private=False):
    log.info("Installing packages from requirements")
    #local("sudo apt-get install -y $(cat requirements_packages)")
    if private:
        venv_path = LVENV
    else:
        venv_path = CVENV
    if not os.path.exists(venv_path):
        log.info("Creating virtual environment in {dir}".format(dir=venv_path))
        local("virtualenv --setuptools %s" % venv_path)
    else:
        log.info("Virtual environment in {dir} already exists".format(dir=venv_path))

@timed
@virtual
def requirements():
    log.info("Installing python modules from requirements")
    """
    tmp = local("TMPF=$(mktemp) && pip freeze > $TMPF && echo $TMPF", capture=True)
    if tmp.stdout:
        local("diff ./requirements11 {tmp} >/dev/null || "
              "pip install -Ur requirements11; rm -f {tmp}".format(
            tmp=tmp.stdout))
    else:
        local("pip install -Ur requirements11")
    """
    local("which python; which pip")
    for d in pip.get_installed_distributions(local_only=True):
        if "python-libtorrent" in d.project_name:
            print "General!"

@task
@virtual
def flake8():
    local("flake8 --max-line-length=120 --show-source --exclude=.env1 . || echo")


@task
@virtual
def test():
    log.info("Testing something")
    a = local("which python")
    print a.real_command



@task(default=True)
@timed
def init(private=False):
    venv(private=private)
    requirements()
