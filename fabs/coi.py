import os
import time
from fabric.api import task, local
from common import timed, virtual, CUR_VENV
from common import logger as log
from tempest import prepare_coi
from . import LAB, WEB, UBUNTU_DISK, UBUNTU_URL_CLOUD, GLOBAL_TIMEOUT
__all__ = ['test', 'prepare', 'install', 'role2', 'aio', 'fullha', 'full']


GLOBAL_TIMEOUT=1
@task
@timed
@virtual
def test():
    ''' For testing purposes only  '''
    print "doing somehting now in %s" % CUR_VENV
    local("which python")


@task
@timed
@virtual
def prepare_vms(topo, args='', cloud=False):
    log.info("Preparing virtual machines for lab=%s" % LAB)
    if "UBUNTU_DISK" not in os.environ:
        disk = UBUNTU_DISK
    else:
        disk = os.environ["UBUNTU_DISK"]
    if cloud:
        url = UBUNTU_URL_CLOUD + UBUNTU_DISK
    else:
        url = WEB + UBUNTU_DISK
    #local("test -e %s || wget -nv %s" %(disk, url))
    local("which python")
    local("echo './tools/cloud/create.py  -l {lab} -s /opt/imgs "
          "-z ./{disk} -t {topo} {args} > config_file'".format(lab=LAB,
                                                               disk=disk,
                                                               topo=topo,
                                                               args=args))
    #local("./tools/cloud/create.py -l {lab} -s /opt/imgs "
    #      "-z ./{disk} -t aio > config_file".format(lab=LAB, disk=disk)
    pass


@task
def prepare(topology, cobbler=False, cloud=False):
    log.info("Preparing boxes for %s Openstack" % topology + (
        " with cobbler" if cobbler else ''))
    args = '-b net' if cobbler else ''
    prepare_vms(topology, cloud=cloud, args=args)


@task
@timed
@virtual
def install_os(script, args='', waittime=10000):
    killtime = waittime + 60
    local("echo 'timeout --preserve-status -s 15 "
          "-k {killtime} {waittime} ./tools/deployers/{script} "
          "{args} -c config_file -u root'".format(
        script=script,
        args=args,
        waittime=waittime,
        killtime=killtime))
    pass


@task
def install(topology=None, cobbler=False):
    ''' Install Openstack '''
    if not topology or topology not in ("aio", "2role", "fullha"):
        raise NameError("Topology should be one of: 'aio', '2role', 'fullha'")
    log.info("Installing %s Openstack" % topology + (
        " with cobbler" if cobbler else ''))
    args = '-e' if cobbler else ''
    if topology == "aio":
        install_os("install_aio_coi.py")
    elif topology == "2role":
        install_os("install_aio_2role.py", args=args)
        local("touch 2role")
    elif topology == "fullha":
        install_os("install_fullha.py", args=args)

@task
@timed
def aio(cloud=False):
    ''' Prepare and install All in One Openstack '''
    log.info("Full install of All in One Openstack")
    prepare("aio", cloud=cloud)
    time.sleep(GLOBAL_TIMEOUT)
    install("aio")

@task(alias='2role')
def role2(cloud=False, cobbler=False):
    ''' Prepare and install 2role Openstack '''
    log.info("Full install of 2role Openstack" + (
        " with cobbler" if cobbler else ''))
    prepare("2role", cloud=cloud, cobbler=cobbler)
    time.sleep(GLOBAL_TIMEOUT)
    install("2role", cobbler=cobbler)

@task
def fullha(cloud=False, cobbler=False):
    ''' Prepare and install Full HA Openstack '''
    log.info("Full install of Full HA Openstack" + (
        " with cobbler" if cobbler else ''))
    prepare("fullha", cloud=cloud, cobbler=cobbler)
    time.sleep(GLOBAL_TIMEOUT)
    install("fullha", cobbler=cobbler)

@task
@timed
@virtual
def workarounds():
    local("python ./tools/tempest-scripts/tempest_align.py -c config_file -u localadmin -p ubuntu")


@task
@timed
def full(topology, cobbler=False, cloud=False):
    ''' Prepare, install and test with Tempest Openstack '''
    log.info("Full install and test of %s Openstack" % topology + (
        " with cobbler" if cobbler else ''))
    if not topology or topology not in ("aio", "2role", "fullha"):
        raise NameError("Topology should be one of: 'aio', '2role', 'fullha'")
    prepare(topology, cloud=cloud, cobbler=cobbler)
    time.sleep(GLOBAL_TIMEOUT)
    install(topology, cobbler=cobbler)
    workarounds()
    prepare_coi(topology)
