#!/usr/bin/env python
from StringIO import StringIO
import argparse
import os
import yaml

from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists, append, comment
from fabric.colors import green, red

from utils import warn_if_fail, quit_if_fail, update_time

__author__ = 'sshnaidm'

DOMAIN_NAME = "domain.name"
# override logs dirs if you need
LOGS_COPY = {
    "/etc": "etc_configs",
    "/var/log": "all_logs",
}

SERVICES = ['neutron-*', 'nova', 'glance', 'cinder', 'keystone']


def apply_changes():
    warn_if_fail(run("./unstack.sh"))
    kill_services()
    apply_patches()
    warn_if_fail(run("./stack.sh"))


def apply_patches():
    #warn_if_fail(run("git fetch https://review.openstack.org/openstack-dev/devstack "
    #"refs/changes/87/87987/12 && git format-patch -1  FETCH_HEAD"))
    #warn_if_fail(run("patch -p1 < 0001-Add-IPv6-support.patch"))
    #warn_if_fail(run("git fetch https://review.openstack.org/openstack-dev/devstack "
    #"refs/changes/23/97823/1 && git format-patch -1  FETCH_HEAD"))
    warn_if_fail(run("wget -qO- 'https://review.openstack.org/gitweb?p=openstack-dev/"
    "devstack.git;a=patch;h=d258d2e8e8b207d332fd465aad7c02dc3ff0c941' | patch -p1 -N"))

def kill_services():
    for service in SERVICES:
        sudo("pkill -f %s" % service)
    sudo("rm -rf /var/lib/dpkg/lock")
    sudo("rm -rf /var/log/libvirt/libvirtd.log")


def make_local(filepath, sudo_flag):
    conf = """[[local|localrc]]
ADMIN_PASSWORD=secret
DATABASE_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
SERVICE_TOKEN=1112f596-76f3-11e3-b3b2-e716f9080d50
MYSQL_PASSWORD=nova
ENABLED_SERVICES=g-api,g-reg,key,n-api,n-crt,n-obj,n-cpu,n-cond,cinder,c-sch,c-api,c-vol,n-sch,n-novnc,n-xvnc,n-cauth,horizon,rabbit
enable_service mysql
disable_service n-net
enable_service q-svc
enable_service q-agt
enable_service q-l3
enable_service q-dhcp
enable_service q-meta
enable_service q-lbaas
enable_service neutron
enable_service tempest
NOVA_USE_NEUTRON_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
API_RATE_LIMIT=False
VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/logs
IP_VERSION=6
MGMT_NET=6
IPV6_PRIVATE_RANGE=feee:1975::/64
IPV6_NETWORK_GATEWAY=feee:1975::1
REMOVE_PUBLIC_BRIDGE=False
IPV6_PUBLIC_RANGE=2005:1975::/64
IPV6_PUBLIC_NETWORK_GATEWAY=2005:1975::1
"""
    fd = StringIO(conf)
    warn_if_fail(put(fd, filepath, use_sudo=sudo_flag))


def install_devstack(settings_dict,
                     envs=None,
                     verbose=None,
                     proxy=None,
                     patch=False):
    envs = envs or {}
    verbose = verbose or []
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        if exists("/etc/gai.conf"):
            append("/etc/gai.conf", "precedence ::ffff:0:0/96  100", use_sudo=True)
        if proxy:
            warn_if_fail(put(StringIO('Acquire::http::proxy "http://proxy.esl.cisco.com:8080/";'),
                             "/etc/apt/apt.conf.d/00proxy",
                             use_sudo=True))
            warn_if_fail(put(StringIO('Acquire::http::Pipeline-Depth "0";'),
                             "/etc/apt/apt.conf.d/00no_pipelining",
                             use_sudo=True))
        update_time(sudo)
        warn_if_fail(sudo("apt-get update"))
        warn_if_fail(sudo("apt-get install -y git python-pip"))
        warn_if_fail(run("git config --global user.email 'test.node@example.com';"
                         "git config --global user.name 'Test Node'"))
        run("rm -rf ~/devstack")
        quit_if_fail(run("git clone https://github.com/openstack-dev/devstack.git"))
        make_local("devstack/local.conf", sudo_flag=False)
        with cd("devstack"):
            if patch:
                apply_patches()
                comment("lib/neutron", "sudo ip netns exec qrouter-\$ROUTER_ID ip -6 route add ::")
            warn_if_fail(run("./stack.sh"))
        if exists('~/devstack/openrc'):
            get('~/devstack/openrc', "./openrc")
        else:
            print (red("No openrc file, something went wrong! :("))
        print (green("Finished!"))
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', action='store', dest='user',
                        help='User to run the script with')
    parser.add_argument('-p', action='store', dest='password',
                        help='Password for user and sudo')
    parser.add_argument('-a', action='store', dest='host', default=None,
                        help='IP of host in to install Devstack on')
    parser.add_argument('-g', action='store', dest='gateway', default=None,
                        help='Gateway to connect to host')
    parser.add_argument('-q', action='store_true', default=False, dest='quiet',
                        help='Make all silently')
    parser.add_argument('-k', action='store', dest='ssh_key_file', default=None,
                        help='SSH key file, default is from repo')
    parser.add_argument('-j', action='store_true', dest='proxy', default=False,
                        help='Use cisco proxy if installing from Cisco local network')
    parser.add_argument('-m', action='store_true', default=False, dest='patch',
                        help='If apply patches to Devstack')
    parser.add_argument('-c', action='store', dest='config_file', default=None,
                        help='Configuration file, default is None')
    parser.add_argument('--version', action='version', version='%(prog)s 2.0')

    opts = parser.parse_args()
    if opts.quiet:
        verb_mode = ['output', 'running', 'warnings']
    else:
        verb_mode = []
    path2ssh = os.path.join(os.path.dirname(__file__), "..", "libvirt-scripts", "id_rsa")
    ssh_key_file = opts.ssh_key_file if opts.ssh_key_file else path2ssh

    if not opts.config_file:
        job = {"host_string": opts.host,
               "user": opts.user,
               "password": opts.password,
               "warn_only": True,
               "key_filename": ssh_key_file,
               "abort_on_prompts": True,
               "gateway": opts.gateway}
    else:
        with open(opts.config_file) as f:
            config = yaml.load(f)
        aio = config['servers']['devstack-server'][0]
        job = {"host_string": aio["ip"],
               "user": opts.user or aio["user"],
               "password": opts.password or aio["password"],
               "warn_only": True,
               "key_filename": ssh_key_file,
               "abort_on_prompts": True,
               "gateway": opts.gateway or None}

    res = install_devstack(settings_dict=job,
                           envs=None,
                           verbose=verb_mode,
                           proxy=opts.proxy,
                           patch=opts.patch)

    if res:
        print "Job with host {host} finished successfully!".format(host=opts.host)


if __name__ == "__main__":
    main()
