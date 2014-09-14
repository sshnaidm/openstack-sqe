import os
import time
from fabric.api import task, local, env
from common import timed, virtual, CUR_VENV, intempest
from common import logger as log
from . import TEMPEST_VENV, TEMPEST_DIR, QA_WAITTIME, QA_KILLTIME

__all__ = ['test', 'init', 'prepare_coi']

env.host_string = "localhost"
env.abort_on_prompts = True
env.warn_only = True

@task
@timed
@intempest
def test():
    ''' For testing purposes only '''
    log.info("Tempest test!")
    print "doing somehting now in %s" % TEMPEST_VENV
    local("which python")

@task
@timed
def venv():
    log.info("Installing virtualenv for tempest")
    install = os.path.join(TEMPEST_DIR, "tools", "install_venv.py")
    local("echo 'python " + install + "'")


@task
@timed
@intempest
def additions():
    log.info("Installing additional modules for tempest")
    local("which python")
    local("echo 'pip install junitxml nose'")

@task
@timed
def init():
    venv()
    additions()

@task
@timed
@intempest
def prepare(openrc=None, ip=None, ipv=None, add=None):
    ''' Prepare tempest '''
    args = ""
    if ip:
        args = "-i " + ip
    elif openrc:
        args = "-o " + openrc
    if ipv:
        args += " -a " + ipv
    if add:
        args += add
    local("echo 'python ./tools/tempest-scripts/tempest_configurator.py %s'" % args)

@task
@timed
def prepare_coi(topology):
    ''' Preparing tempest for COI '''
    log.info("Preparing tempest for COI")
    init()
    prepare(openrc="./openrc")
    if topology == "2role":
        local("sed -i 's/.*[sS]wift.*\=.*[Tt]rue.*/swift=false/g' ./tempest.conf.jenkins")
    conf_dir = os.path.join(TEMPEST_DIR, "etc")
    local("echo 'mv ./tempest.conf.jenkins %s/tempest.conf'" % conf_dir)

@task
@timed
def run_tests(topology):
    ''' Run Tempest tests '''
    log.info("Run Tempest tests")
    time_prefix = "timeout --preserve-status -s 2 -k {kill} {wait} ".format(
        wait=QA_WAITTIME, kill=QA_KILLTIME)
    local(time_prefix + )

