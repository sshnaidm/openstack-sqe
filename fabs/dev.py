import os
import time
from fabric.api import task, local
from common import timed, virtual, CUR_VENV
from common import logger as log
from tempest import prepare_coi, run_tests
from . import LAB, WEB, UBUNTU_DISK, UBUNTU_URL_CLOUD, GLOBAL_TIMEOUT

__all__ = ['test', 'prepare', 'install', 'devstack']


@task
@timed
@virtual
def test():
    ''' For testing purposes only  '''
    print "Doing something now in %s" % CUR_VENV
    local("which python")


@task
@timed
@virtual
def prepare(topology='devstack'):
    ''' Prepare VMs of specific topology for Openstack '''
    log.info("Preparing boxes for %s Openstack" % topology)
    log.info("Preparing virtual machines for lab=%s" % LAB)
    if "DISK" not in os.environ:
        disk = UBUNTU_DISK
    else:
        disk = os.environ["DISK"]
    url = WEB + disk
    local("test -e %s || wget -nv %s" % (disk, url))
    local("python ./tools/cloud/create.py  -l {lab} -s /opt/imgs "
          "-z ./{disk} -t {topo} > config_file".format(lab=LAB,
                                                       disk=disk,
                                                       topo=topology))


@task
@timed
@virtual
def install():
    ''' Install devstack Openstack '''
    log.info("Installing devstack Openstack")
    tempest_repo = os.environ.get("TEMPEST_REPO", "")
    tempest_br = os.environ.get("TEMPEST_BRANCH", "")
    local("python ./tools/deployers/install_devstack.py "
          "-c config_file  -u localadmin -p ubuntu -r {repo} -b {br}".format(
        repo=tempest_repo,
        br=tempest_br
    ))
    pass

@task
@timed
def devstack(topology='devstack'):
    ''' Prepare and install devstack Openstack '''
    log.info("Full install of devstack Openstack")
    prepare(topology=topology)
    time.sleep(GLOBAL_TIMEOUT)
    install()





