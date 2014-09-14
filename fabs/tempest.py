import os
import time
from fabric.api import task, local, env, lcd
from common import timed, TEMPEST_VENV, TLVENV, TCVENV, intempest, get_dev_ip
from common import logger as log
from . import TEMPEST_DIR, QA_WAITTIME, QA_KILLTIME, WORKSPACE

__all__ = ['test', 'init', 'prepare_coi', 'prepare', 'prepare_devstack', 'run_tests']

env.host_string = "localhost"
env.abort_on_prompts = True
env.warn_only = True

TESTS_FILE = os.path.join(WORKSPACE, "openstack-sqe", "tools",
                         "tempest-scripts", "tests_set")


@task
@timed
@intempest
def test():
    ''' For testing purposes only '''
    log.info("Tempest test!")
    print "Doing something now in %s" % TEMPEST_VENV
    local("which python")

@task
@timed
def venv(private=True):
    log.info("Installing virtualenv for tempest")
    install = os.path.join(TEMPEST_DIR, "tools", "install_venv.py")
    wraps = ''
    if not private:
        wraps = "export venv=%s; " % TCVENV
    local("%spython " % wraps + install)


@task
@timed
@intempest
def additions():
    log.info("Installing additional modules for tempest")
    local("which python")
    local("pip install junitxml nose")

@task
@timed
def init(private=False):
    venv(private=private)
    additions()

@task
@timed
@intempest
def prepare(openrc=None, ip=None, ipv=None, add=None):
    ''' Prepare tempest '''
    args = ""
    if ip:
        args = " -i " + ip
    elif openrc:
        args = " -o " + openrc
    if ipv:
        args += " -a " + ipv
    if add:
        args += " " + add
    local("python ./tools/tempest-scripts/tempest_configurator.py %s" % args)

@task
@timed
def prepare_coi(topology=None, private=True):
    ''' Prepare tempest especially for COI '''
    log.info("Preparing tempest for COI")
    init(private=private)
    prepare(openrc="./openrc")
    if topology == "2role":
        local("sed -i 's/.*[sS]wift.*\=.*[Tt]rue.*/swift=false/g' ./tempest.conf.jenkins")
    conf_dir = os.path.join(TEMPEST_DIR, "etc")
    local("mv ./tempest.conf.jenkins %s/tempest.conf" % conf_dir)


@task(alias='dev')
@timed
def prepare_devstack(ip=None, private=True):
    ''' Prepare tempest for devstack '''
    init(private=private)
    conf_dir = os.path.join(TEMPEST_DIR, "etc")
    if not ip:
        log.info("Preparing tempest for devstack with ready file")
        local("mv ./tempest.conf %s/tempest.conf" % conf_dir)
    else:
        ip = get_dev_ip()
        log.info("Preparing tempest for devstack with IP: %s" % ip)
        prepare(ip=ip)
        local("mv ./tempest.conf.jenkins %s/tempest.conf" % conf_dir)


@task(alias="run")
@timed
@intempest
def run_tests(force=False):
    ''' Run Tempest tests '''
    log.info("Run Tempest tests")
    time_prefix = "timeout --preserve-status -s 2 -k {kill} {wait} ".format(
        wait=QA_WAITTIME, kill=QA_KILLTIME)
    with lcd(TEMPEST_DIR):
        repo_exists = os.path.exists(os.path.join(TEMPEST_DIR, ".testrepository"))
        if repo_exists and not force:
            log.info("Tests already ran, now run the failed only")
            cmd = "testr run --failing --subunit | subunit-2to1 | tools/colorizer.py"
        else:
            if repo_exists:
                local("rm -rf .testrepository")
            local("testr init")
            if os.path.getsize(TESTS_FILE) > 0:
                log.info("Tests haven't run yet, run them from file %s" % TESTS_FILE)
                cmd = 'testr run --load-list %s --subunit  | subunit-2to1 | tools/colorizer.py' % TESTS_FILE
            else:
                regex = os.environ.get('REG', "")
                log.info("Tests haven't run yet, run them with regex: '%s'" % regex)
                cmd = "testr run '%s' --subunit | subunit-2to1 | tools/colorizer.py" % regex
        local(time_prefix + cmd)
        result = os.path.join(WORKSPACE, "openstack-sqe", time.strftime("%H%M%S"))
        subunit = os.path.join(WORKSPACE, "openstack-sqe", "testr_results.subunit")
        fails_extract = os.path.join(WORKSPACE, "openstack-sqe", "tools",
                                     "tempest-scripts", "extract_failures.py")
        local("testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=%s" % result)
        local("testr last --subunit > %s" % subunit)
        local("python {script} {result} > {tests_file}".format(
            script=fails_extract, result=result, tests_file=TESTS_FILE))

@task(alias="remote")
@timed
@intempest
def run_remote_tests():
    ''' Run Tempest tests remotely'''
    log.info("Run Tempest tests remotely")
    tempest_repo = os.environ.get("TEMPEST_REPO", "")
    tempest_br = os.environ.get("TEMPEST_BRANCH", "")
    ip = get_dev_ip()
    test_regex = os.environ.get('REG', "")
    args = ""
    if os.path.getsize(TESTS_FILE) > 0:
        log.info("Run tests from file %s" % TESTS_FILE)
        args = " -l %s " % TESTS_FILE
    elif test_regex:
        log.info("Run tests with regex: '%s'" % test_regex)
        args = " -f '%s' " % test_regex
    else:
        log.info("Run all tests for devstack")
    local('{wrk}/openstack-sqe/sqe.py run_tempest -r {ip} '
          '{args} --repo {repo} --branch {br}'.format(
        wrk=WORKSPACE, ip=ip, args=args,
        repo=tempest_repo, br=tempest_br
    ))
