from deploy import Standalone
from utils import warn_if_fail, update_time
from StringIO import StringIO
from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists
from fabric.colors import green, red

__author__ = 'sshnaidm'


SERVICES = ['neutron-', 'nova', 'glance', 'cinder', 'keystone']

class Devstack(Standalone):
    def __init__(self, *args):
        Standalone.__init__(*args)
        self.scenario = "devstack"
        self.devstack = None
        if self.conf_yaml:
            self.devstack = self.conf_yaml['servers']['devstack-server'][0]
        self.patch = self.conf.patch

    def parse_file(self):
        self.host = self.devstack["ip"]
        self.user = self.conf.user or self.devstack["user"]
        self.password = self.devstack["password"]

    def run_installer(self):
        install_devstack(self.job, self.env, self.verb, self.conf.proxy, self.conf.patch)


class DevstackDeploy:

    @staticmethod
    def apply_changes(self):
        warn_if_fail(run("./unstack.sh"))
        self.kill_services()
        self.apply_patches()
        warn_if_fail(run("./stack.sh"))

    @staticmethod
    def apply_patches(self):
        warn_if_fail(run("git fetch https://review.openstack.org/openstack-dev/devstack "
        "refs/changes/87/87987/12 && git format-patch -1  FETCH_HEAD"))

        #warn_if_fail(run("git fetch https://review.openstack.org/openstack-dev/devstack "
        #"refs/changes/23/97823/1 && git format-patch -1  FETCH_HEAD"))

    @staticmethod
    def kill_services(self):
        for service in SERVICES:
            sudo("pkill -f %s" % service)
        sudo("rm -rf /var/lib/dpkg/lock")
        sudo("rm -rf /var/log/libvirt/libvirtd.log")

    @staticmethod
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
    LOGFILE=/tmp/stack.sh.log
    USE_SCREEN=True
    SCREEN_LOGDIR=/opt/stack/logs
    TEMPEST_REPO=https://github.com/kshileev/tempest.git
    TEMPEST_BRANCH=ipv6
    #RECLONE=no
    #OFFLINE=True
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
        if proxy:
            warn_if_fail(put(StringIO('Acquire::http::proxy "http://proxy.esl.cisco.com:8080/";'),
                             "/etc/apt/apt.conf.d/00proxy",
                             use_sudo=True))
            warn_if_fail(put(StringIO('Acquire::http::Pipeline-Depth "0";'),
                             "/etc/apt/apt.conf.d/00no_pipelining",
                             use_sudo=True))
        update_time(run)
        warn_if_fail(sudo("apt-get update"))
        warn_if_fail(sudo("apt-get install -y git python-pip"))
        warn_if_fail(run("git config --global user.email 'test.node@example.com';"
                         "git config --global user.name 'Test Node'"))
        warn_if_fail(run("git clone https://github.com/openstack-dev/devstack.git"))
        DevstackDeploy.make_local("devstack/local.conf", sudo_flag=False)
        with cd("devstack"):
            warn_if_fail(run("./stack.sh"))
            if patch:
                DevstackDeploy.apply_changes()
        if exists('~/devstack/openrc'):
            get('~/devstack/openrc', "./openrc")
        else:
            print (red("No openrc file, something went wrong! :("))
        print (green("Finished!"))
        return True
