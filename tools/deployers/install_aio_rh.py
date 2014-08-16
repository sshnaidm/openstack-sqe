#!/usr/bin/env python
from StringIO import StringIO
import argparse
import os
import yaml

from ConfigParser import SafeConfigParser
from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists, append
from fabric.colors import green, red

from utils import warn_if_fail, quit_if_fail, update_time

__author__ = 'sshnaidm'

DOMAIN_NAME = "domain.name"
# override logs dirs if you need
LOGS_COPY = {
    "/etc": "etc_configs",
    "/var/log": "all_logs",
}

def prepare_answers(path):
    fd = StringIO()
    warn_if_fail(get(path, fd))
    parser = SafeConfigParser()
    parser.optionxform = str
    parser.readfp(fd)
    parser.set("general", "CONFIG_PROVISION_DEMO", "y")
    parser.set("general", "CONFIG_PROVISION_TEMPEST", "y")
    parser.set("general", "CONFIG_PROVISION_TEMPEST_REPO_REVISION", "master")
    fd1 = StringIO()
    parser.write(fd1)
    warn_if_fail(put(fd1, "~/installed_answers"))

def install_devstack(settings_dict,
                     envs=None,
                     verbose=None,
                     proxy=None):
    envs = envs or {}
    verbose = verbose or []
    if settings_dict['user'] != 'root':
        use_sudo_flag = True
        run_func = sudo
    else:
        use_sudo_flag = False
        run_func = run
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        if exists("/etc/gai.conf"):
            append("/etc/gai.conf", "precedence ::ffff:0:0/96  100", use_sudo=use_sudo_flag)
        warn_if_fail(run_func("yum -y update"))
        warn_if_fail(run_func("yum -y install -y git python-pip vimi ntpdate"))
        update_time(run_func)
        warn_if_fail(run_func("git config --global user.email 'test.node@example.com';"
                         "git config --global user.name 'Test Node'"))
        warn_if_fail(run_func("yum install -y http://rdo.fedorapeople.org/rdo-release.rpm"))
        warn_if_fail(run_func("yum install -y openstack-packstack"))
        warn_if_fail(run_func("packstack --gen-answer-file=answers.txt"))
        prepare_answers("~/answers.txt")
        warn_if_fail(run_func("packstack --answer-file=~/installed_answers"))
        if exists('~/keystonerc_admin'):
            get('~/keystonerc_admin', "./openrc")
        else:
            print (red("No openrc file, something went wrong! :("))
        if exists('~/keystonerc_demo'):
            get('~/keystonerc_demo', "./openrc_demo")
        if exists('~/packstack-answers-*'):
            get('~/packstack-answers-*', ".")
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
        box =  config['servers'].keys()[0]
        aio = config['servers'][box][0]
        job = {"host_string": aio["ip"],
               "user": opts.user or aio["user"],
               "password": opts.password or aio["password"],
               "warn_only": True,
               "key_filename": ssh_key_file,
               "abort_on_prompts": True,
               "gateway": opts.gateway or None}

    res = install_devstack(settings_dict=job, envs=None, verbose=verb_mode, proxy=opts.proxy)

    if res:
        print "Job with host {host} finished successfully!".format(host=opts.host)


if __name__ == "__main__":
    main()
