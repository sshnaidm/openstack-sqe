import os
import yaml
import re
from fabric.colors import yellow, red
from fabric.contrib.files import exists
from fabric.operations import get
import sys
from config import LOGS_COPY

__author__ = 'sshnaidm'


dump = lambda x: yaml.dump(x, default_flow_style=False)
ip_re = re.compile("\d+\.\d+\.\d+\.\d+")

def collect_logs(run_func=None, hostname=None, clean=False):
    dirname = "test_data"
    if "WORKSPACE" in os.environ:
        path = os.path.join(os.environ["WORKSPACE"], dirname)
    else:
        cur_dir = os.path.dirname(__file__)
        path = os.path.join(cur_dir, dirname)
    if not os.path.exists(path):
        os.mkdir(path)
    if clean:
        for i in os.listdir(path):
            os.remove(os.path.join(path, i))
    for dirlog in LOGS_COPY:
        filename = LOGS_COPY[dirlog] + "_" + hostname
        run_func("tar -zcf /tmp/{filename}.tar.gz {dirlog} 2>/dev/null".format(filename=filename, dirlog=dirlog))
        get("/tmp/{filename}.tar.gz".format(filename=filename), path)
        run_func("rm -rf /tmp/{filename}.tar.gz".format(filename=filename))


def change_ip_to(string, ip):
    return ip_re.sub(ip, string)


def all_servers(config):
    ssum = lambda x,y: x+y if isinstance(y, list) else x + [y]
    return reduce(ssum, config['servers'].values(), [])


def quit_if_fail(command):
    """
        Function quits all application if given command failed

    :param command: Command to execute
    """
    if command.failed:
        print(red('FAB ERROR: Command failed'))
        if 'command' in command.__dict__:
            print(red('FAB ERROR: Command {cmd} returned {code}'.format(
                cmd=command.command, code=command.return_code)))
        sys.exit(command.return_code)


def warn_if_fail(command):
    """
        Function prints warning to log if given command failed

    :param command: Command to execute
    """
    if command.failed:
        print(yellow('FAB ERROR: Command failed'))
        if 'command' in command.__dict__:
            print(yellow('FAB ERROR: Command {cmd} returned {code}'.format(
                cmd=command.command, code=command.return_code)))


def update_time(func):
    """
        Update time on remote machine

    :param func: function to execute the ntpdate with
    """
    ntp = False
    if exists("/etc/init.d/ntp"):
        ntp = True
        func("/etc/init.d/ntp stop")
    if func("ntpdate ntp.esl.cisco.com").failed:
        if func("ntpdate 10.81.254.202").failed:
            func("ntpdate ntp.ubuntu.com")
    if ntp:
        func("/etc/init.d/ntp start")

def resolve_names(run_func, use_sudo_flag):
    import socket
    ip_arch = socket.gethostbyname("archive.ubuntu.com")
    ip_cisco = socket.gethostbyname("openstack-repo.cisco.com")
    run_func("echo -e '%s    archive.ubuntu.com\n' >> /etc/hosts" % ip_arch)
    run_func("echo -e '%s    openstack-repo.cisco.com\n' >> /etc/hosts" % ip_cisco)