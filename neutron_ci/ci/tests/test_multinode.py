import os
import StringIO
import logging
from fabric.context_managers import settings
from fabric.operations import put, run, get, local

import urlparse
from ci import ZUUL_URL, ZUUL_PROJECT, ZUUL_REF, \
    NEXUS_VLAN_START, NEXUS_VLAN_END, BUILD_LOG_PATH, \
    NEXUS_IP, NEXUS_USER, NEXUS_PASSWORD, \
    PARENT_FOLDER_PATH, WORKSPACE
from ci.lib.devstack import DevStack
from ci.lib.test_case import MultinodeTestCase
from ci.lib.utils import makedirs


TEST_LIST_FILE = os.path.join(PARENT_FOLDER_PATH, 'cisco_plugin_tests.txt')
Q_PLUGIN_EXTRA_CONF_FILES = 'ml2_conf_cisco.ini'
LOCALCONF_CONTROLLER = '''
[[local|localrc]]
NEUTRON_REPO={neutron_repo}
NEUTRON_BRANCH={neutron_branch}

HOST_IP={CONTROL_HOST_IP}

MULTI_HOST=1

disable_service n-net heat h-api h-api-cfn h-api-cw h-eng cinder c-api c-sch c-vol n-novnc horizon
enable_service neutron
enable_service tempest
enable_service q-svc
enable_service q-agt
enable_service q-dhcp
enable_service q-l3
enable_service q-meta
enable_service n-cpu
enable_service q-vpn
enable_service q-lbaas

MYSQL_PASSWORD=nova
RABBIT_PASSWORD=nova
SERVICE_TOKEN=nova
SERVICE_PASSWORD=nova
ADMIN_PASSWORD=nova

LIBVIRT_TYPE=qemu
NOVA_USE_QUANTUM_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
Q_PLUGIN=ml2
Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,cisco_nexus
Q_ML2_PLUGIN_TYPE_DRIVERS=vlan
Q_PLUGIN_EXTRA_CONF_PATH=({Q_PLUGIN_EXTRA_CONF_PATH})
Q_PLUGIN_EXTRA_CONF_FILES=({Q_PLUGIN_EXTRA_CONF_FILES})
ML2_VLAN_RANGES=physnet1:{vlan_start}:{vlan_end}
PHYSICAL_NETWORK=physnet1
OVS_PHYSICAL_BRIDGE=br-eth1
TENANT_VLAN_RANGE={vlan_start}:{vlan_end}
ENABLE_TENANT_VLANS=True
ENABLE_TENANT_TUNNELS=False
Q_ML2_TENANT_NETWORK_TYPE=vlan
LOGFILE=/opt/stack/screen-logs/stack.sh.log
SCREEN_LOGDIR=/opt/stack/screen-logs
VERBOSE=True
DEBUG=True
USE_SCREEN=True
API_RATE_LIMIT=False
RECLONE=True
'''

LOCALCONF_COMPUTE = '''
[[local|localrc]]
NEUTRON_REPO={neutron_repo}
NEUTRON_BRANCH={neutron_branch}

HOST_IP={COMPUTE_HOST_IP}
SERVICE_HOST={CONTROL_HOST_IP}
MYSQL_HOST={CONTROL_HOST_IP}
RABBIT_HOST={CONTROL_HOST_IP}
GLANCE_HOSTPORT={CONTROL_HOST_IP}:9292

MULTI_HOST=1

MYSQL_PASSWORD=nova
RABBIT_PASSWORD=nova
SERVICE_TOKEN=nova
SERVICE_PASSWORD=nova
ADMIN_PASSWORD=nova

ENABLED_SERVICES=n-cpu,neutron,n-api,q-agt

LIBVIRT_TYPE=qemu
NOVA_USE_QUANTUM_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
Q_PLUGIN=ml2
Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,cisco_nexus
Q_ML2_PLUGIN_TYPE_DRIVERS=vlan
Q_PLUGIN_EXTRA_CONF_PATH=({Q_PLUGIN_EXTRA_CONF_PATH})
Q_PLUGIN_EXTRA_CONF_FILES=({Q_PLUGIN_EXTRA_CONF_FILES})
ML2_VLAN_RANGES=physnet1:{vlan_start}:{vlan_end}
PHYSICAL_NETWORK=physnet1
OVS_PHYSICAL_BRIDGE=br-eth1
TENANT_VLAN_RANGE={vlan_start}:{vlan_end}
ENABLE_TENANT_VLANS=True
ENABLE_TENANT_TUNNELS=False
Q_ML2_TENANT_NETWORK_TYPE=vlan
LOGFILE=/opt/stack/screen-logs/stack.sh.log
SCREEN_LOGDIR=/opt/stack/screen-logs
VERBOSE=True
DEBUG=True
USE_SCREEN=True
RECLONE=True
'''

ML2_CONF_INI = '''
[ml2_cisco]
managed_physical_network = physnet1

[ml2_mech_cisco_nexus:{router_ip}]
{map}
ssh_port=22
username={username}
password={password}
'''


logger = logging.getLogger(__name__)


class ML2MutinodeTest(MultinodeTestCase):

    @classmethod
    def setUpClass(cls):
        MultinodeTestCase.setUpClass()

        parameters = {
            'neutron_repo': urlparse.urljoin(ZUUL_URL, ZUUL_PROJECT),
            'neutron_branch': ZUUL_REF,
            'CONTROL_HOST_IP': cls.VMs['control'].ip,
            'COMPUTE_HOST_IP': cls.VMs['compute'].ip,
            'Q_PLUGIN_EXTRA_CONF_PATH': '/home/ubuntu/devstack',
            'Q_PLUGIN_EXTRA_CONF_FILES': Q_PLUGIN_EXTRA_CONF_FILES,
            'vlan_start': NEXUS_VLAN_START,
            'vlan_end': NEXUS_VLAN_END
        }

        cls.controller = DevStack(
            host_string=cls.VMs['control'].ip,
            clone_path='/home/ubuntu/devstack',
            local_conf=LOCALCONF_CONTROLLER.format(**parameters))
        cls.compute = DevStack(
            host_string=cls.VMs['compute'].ip,
            clone_path='/home/ubuntu/devstack',
            local_conf=LOCALCONF_COMPUTE.format(**parameters))

    def test_tempest(self):
        self.controller.clone()
        self.compute.clone()

        # Create ml2 config for cisco plugin. Put it to controller node
        with settings(host_string=self.VMs['control'].ip):
            map = [vm.name + '=' + vm.port for vm in self.VMs.itervalues()]
            ml2_conf_io = StringIO.StringIO()
            ml2_conf_io.write(
                ML2_CONF_INI.format(
                    map=os.linesep.join(map),
                    router_ip=NEXUS_IP,
                    username=NEXUS_USER,
                    password=NEXUS_PASSWORD))
            put(ml2_conf_io, os.path.join(self.controller._clone_path,
                                          Q_PLUGIN_EXTRA_CONF_FILES))

        self.assertFalse(self.controller.stack())
        self.assertFalse(self.compute.stack())

        # Add port to data network bridge
        for ip in (self.VMs['control'].ip, self.VMs['compute'].ip):
            with settings(host_string=ip):
                run('sudo ovs-vsctl add-port br-eth1 eth1')

        self.assertFalse(self.controller.run_tempest(TEST_LIST_FILE))

    @classmethod
    def tearDownClass(cls):
        # download devstack logs
        control_path = os.path.join(BUILD_LOG_PATH, 'logs-control')
        makedirs(control_path)
        cls.controller.get_locals(control_path)
        cls.controller.get_screen_logs(control_path)
        cls.controller.get_tempest_unitxml(BUILD_LOG_PATH)
        cls.controller.get_tempest_html(BUILD_LOG_PATH)

        compute_path = os.path.join(BUILD_LOG_PATH, 'logs-compute')
        makedirs(compute_path)
        cls.compute.get_locals(compute_path)
        cls.compute.get_screen_logs(compute_path)
