import os
import time
from fabric.api import task, local
from common import timed, virtual, CUR_VENV
from common import logger as log
from tempest import prepare_coi, run_tests
from . import LAB, WEB, CENTOS65_DISK, CENTOS7_DISK, FEDORA20_DISK, GLOBAL_TIMEOUT

__all__ = ['test', 'prepare', 'install', 'devstack']




@task
@timed
@virtual
def prepare_vms(topo, args='', distro="centos7"):
    log.info("Preparing virtual machines for lab=%s" % LAB)
    if "REDHAT_DISK" in os.environ:
        disk = os.environ['REDHAT_DISK']
    else:
        if distro == 'centos7':
            disk = CENTOS7_DISK
        elif distro == 'centos65':
            disk = CENTOS65_DISK
        elif distro == 'fedora20':
            disk = FEDORA20_DISK
        else:
            raise NameError("Please choose distro from 'centos7', 'centos65', 'fedora20'")
    url = WEB + disk
    local("test -e %s || wget -nv %s" %(disk, url))
    local("python ./tools/cloud/create.py  -l {lab} -s /opt/imgs "
          "-z ./{disk} -t {topo} {args} > config_file".format(lab=LAB,
                                                               disk=disk,
                                                               topo=topo,
                                                               args=args))

@task
def prepare(topology, cobbler=False, cloud=False):
    ''' Prepare VMs of specific topology for Openstack '''
    log.info("Preparing boxes for %s Openstack" % topology + (
        " with cobbler" if cobbler else ''))
    args = '-b net' if cobbler else ''
    prepare_vms(topology, cloud=cloud, args=args)


@task
@timed
@virtual
def install_os(script, args='', waittime=10000):
    killtime = waittime + 60
    local("timeout --preserve-status -s 15 "
          "-k {killtime} {waittime} ./tools/deployers/{script} "
          "{args} -c config_file -u root".format(
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
