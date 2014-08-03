import argparse
import glob
import keystoneclient.v2_0.client
import novaclient.client
import neutronclient.v2_0.client
import glanceclient
import requests
import re
import os
import sys
import urllib
import ConfigParser

__author__ = 'sshnaidm'

env_re = re.compile("export (OS_[A-Z0-9_]+=.*$)")
token_re = re.compile("name='csrfmiddlewaretoken' value='([^']+)'")


NOVACLIENT_VERSION = '2'
CINDERCLIENT_VERSION = '1'

DEFAULT_USER = "admin"
DEFAULT_PASS = "Cisco123"
DEFAULT_REGION = "RegionOne"
DEMO_USER = "demo"
DEMO_PASS = "secret"
DEMO_TENANT = "demo"
ALT_USER = "alt_demo"
ALT_PASS = "secret"
ALT_TENANT = "alt_demo"
DEFAULT_IPV4_INT = "192.168.10"
DEFAULT_IPV6_INT = "fd00::"

CIRROS_URL = "http://172.29.173.233/cirros-0.3.2-x86_64-disk.img"
CIRROS_UEC_URL = "http://download.cirros-cloud.net/0.3.2/cirros-0.3.2-x86_64-uec.tar.gz"
UBUNTU_URL = "http://172.29.173.233/cirros-0.3.2-x86_64-disk.img"

class OS:

    def _get_identity_client(self, credentials):
            return keystoneclient.v2_0.client.Client(
                username=credentials["OS_USERNAME"],
                password=credentials["OS_PASSWORD"],
                tenant_name=credentials["OS_TENANT_NAME"],
                auth_url=credentials["OS_AUTH_URL"])

    def _get_network_client(self, credentials):
            return neutronclient.v2_0.client.Client(
                username=credentials["OS_USERNAME"],
                password=credentials["OS_PASSWORD"],
                tenant_name=credentials["OS_TENANT_NAME"],
                auth_url=credentials["OS_AUTH_URL"])

    def _get_image_client(self, credentials):
            keystone_cl = self._get_identity_client(credentials)
            token = keystone_cl.auth_token
            endpoint = keystone_cl.service_catalog.url_for(service_type="image")
            return glanceclient.Client('1', endpoint=endpoint, token=token)

    def _get_compute_client(self, credentials):
            client_args = (credentials["OS_USERNAME"], credentials["OS_PASSWORD"],
                           credentials["OS_TENANT_NAME"], credentials["OS_AUTH_URL"])
            return novaclient.client.Client(NOVACLIENT_VERSION,
                                            *client_args,
                                            region_name=credentials["OS_REGION_NAME"],
                                            no_cache=True,
                                            http_log_debug=True)

class OSWebCreds:
    def __init__(self, ip, user, password):
        self.ip = ip
        self.user = user
        self.password = password

    def get_file_from_url(self):
        PARAMS = {
            "region": "http://%s:5000/v2.0",
            "username": self.user,
            "password": self.password,
        }
        s = requests.Session()
        local_params = dict(PARAMS, region=PARAMS['region'] % self.ip)
        url = "http://" + self.ip + "/horizon"
        s = requests.Session()
        login_page = s.get(url)
        token = token_re.search(login_page.content).group(1)
        local_params.update({"csrfmiddlewaretoken":token})
        login_url = "http://" + self.ip + "/horizon/auth/login/"
        s2 = s.post(login_url, data=local_params)
        rc_url = "http://" + self.ip + "/horizon/project/access_and_security/api_access/openrc/"
        rc_file = s.get(rc_url)
        return rc_file

    def parse_rc(self, x):
        export_lines = (i for i in x.split("\n") if env_re.search(i) and not "PASSWORD" in i)
        os_vars = (env_re.search(i).group(1) for i in export_lines)
        os_dict = dict(((z.replace("'", "").replace('"', '') for z in  i.split("=")) for i in os_vars))
        return os_dict

    def creds(self):
        rc_file = self.get_file_from_url()
        rc_dict = self.parse_rc(rc_file.content)
        if rc_dict:
            return dict(rc_dict, OS_PASSWORD=self.password, OS_REGION_NAME=DEFAULT_REGION)
        else:
            return None


class Tempest:
    def __init__(self, openrc):
        self.creds = openrc
        openstack = OS()
        self.nova = openstack._get_compute_client(self.creds)
        self.neutron = openstack._get_network_client(self.creds)
        self.keystone = openstack._get_identity_client(self.creds)
        self.glance = openstack._get_image_client(self.creds)
        self.ipv = openrc["ipv"]
        self.external_net = openrc["external_net"]
        self.tmp_dir = "/tmp/"
        self.locks_dir = os.path.join(os.path.dirname(__file__), "locks")

    def config(self):
        pass

    def unconfig(self):
        cur_dir = os.path.join(os.path.dirname(__file__))
        img_dir = os.path.join(cur_dir, "prepare_for_tempest_dir")
        if os.path.exists(img_dir):
            for i in os.listdir(img_dir):
                os.remove(os.path.join(img_dir,i))
        print "Deleting cirros-0.3.1-x86_64-disk.img ...."
        for i in glob.glob("./cirros-*img"):
            os.remove(i)
        os.remove(os.path.join(cur_dir, "trusty-server-cloudimg-amd64-disk1.img"))
        print "Deleting glance images ....."
        for img in self.glance.images.list():
            self.glance.images.delete(img)
        print "Deleting demo tenants ....."
        for t in self.keystone.tenants.list():
            if t.name == DEMO_TENANT or t.name == ALT_TENANT:
                self.keystone.tenants.delete(t)
        print "Deleting demo users ....."
        for u in self.keystone.users.list():
            if u.name == DEMO_USER or u.name == ALT_USER:
                self.keystone.users.delete(u)
        print "Deleting floating ips ....."
        for i in self.neutron.list_floatingips()['floatingips']:
            self.neutron.delete_floatingip(i['id'])
        print "Clearing gateway from routers ...."
        for i in self.neutron.list_routers()['routers']:
            self.neutron.remove_gateway_router(i['id'])
        print "Deleting router ports ...."
        for i in [port for port in self.neutron.list_ports()['ports']]:
            if i['device_owner'] == 'network:router_interface':
                self.neutron.remove_interface_router(i['device_id'], {"port_id": i['id']})
        print "Deleting routers ...."
        for i in self.neutron.list_routers()['routers']:
            self.neutron.delete_router(i['id'])
        for i in self.neutron.list_networks()['networks']:
            self.neutron.delete_network(i)
        for i in self.neutron.list_subnets()['subnets']:
            self.neutron.delete_subnet(i)
        for i in os.listdir(self.tmp_dir):
            if "cirros-0.3.1-x86_64-uec" in i:
                os.remove(i)

    def create_config(self):
        cur_dir = os.path.join(os.path.dirname(__file__))
        img_dir = os.path.join(cur_dir, "prepare_for_tempest_dir")
        print "Reinitialize the dir..."
        if os.path.exists(img_dir):
            for i in os.listdir(img_dir):
                os.remove(os.path.join(img_dir,i))
        else:
            os.makedirs(img_dir)
        if not os.path.exists(self.locks_dir):
            os.makedirs(img_dir)
        print "Downloading cirros-0.3.2-x86_64-disk.img ...."
        img_path = os.path.join(img_dir, "cirros-0.3.2-x86_64-disk.img")
        urllib.urlretrieve(CIRROS_URL, img_path)
        img1 = self.glance.images.create(
            data=img_path,
            name="cirros-0.3.2",
            disk_format="qcow2",
            container_format="bare",
            is_public=True)
        img2 = self.glance.images.create(
            data=img_path,
            name="ubuntu",
            disk_format="qcow2",
            container_format="bare",
            is_public=True)
        demo_tenant = self.keystone.tenants.create(DEMO_TENANT)
        demo_user = self.keystone.users.create(
            name=DEMO_USER,
            password=DEMO_PASS,
            email=DEMO_USER+"@spam.com",
            tenant_id=demo_tenant.id)
        alt_tenant = self.keystone.tenants.create(ALT_TENANT)
        alt_user = self.keystone.users.create(
            name=ALT_USER,
            password=ALT_PASS,
            email=ALT_USER+"@spam.com",
            tenant_id=alt_tenant.id)
        tenant_ids = dict((i.name, i.id) for i in self.keystone.tenants.list())
        if "openstack" in tenant_ids:
            admin_tenant = ("openstack", tenant_ids["openstack"])
        elif "admin" in tenant_ids:
            admin_tenant = ("admin", tenant_ids["admin"])
        else:
            _admin_tenant = self.keystone.tenants.create("admin")
            admin_tenant = ("admin", _admin_tenant.id)
        try:
            self.keystone.users.create(
                name=DEFAULT_USER,
                password=DEFAULT_PASS,
                email=DEFAULT_USER+"@spam.com",
                tenant_id=admin_tenant[1])
        except Exception as e:
            print e
        admin = next((i for i in self.keystone.users.list() if i.name == "admin"), None)
        # if not successful creating admin - set its password
        admin = self.keystone.users.update_password(admin.id, DEFAULT_PASS)
        admin_role = next((i for i in self.keystone.roles.list() if i.name == "admin"), None)
        if admin is None or admin_role is None:
            print "Can not get admin details!"
            sys.exit(1)
        try:
            self.keystone.roles.add_user_role(
                user=admin.id,
                role=admin_role.id,
                tenant=admin_tenant[1])
        except Exception as e:
            print e
        self.keystone.roles.add_user_role(
            user=admin.id,
            role=admin_role.id,
            tenant=demo_tenant.id)
        public_net = self.neutron.create_network({
            'network':
                {'name': "public",
                 'admin_state_up': True,
                 "router:external": True
                }})
        if self.ipv == 4:
            sub_public = self.neutron.create_subnet({
                'subnet':
                    {'name':"sub",
                     'network_id': public_net['network']['id'],
                     'ip_version': 4,
                     'cidr': self.external_net + '.0/24',
                     'dns_nameservers': [self.external_net + ".1", '8.8.8.8']
                    }})
        else:
            sub_public = self.neutron.create_subnet({
                'subnet':
                    {'name':"sub",
                     'network_id': public_net['network']['id'],
                     'ip_version': 4,
                     'cidr': self.external_net + '/64',
                     'dns_nameservers': [self.external_net + "1"]
                    }})
        private_net = self.neutron.create_network({
            'network':
                {'name': "net10",
                 'admin_state_up': True,
                 "shared": True
                }})
        if self.ipv == 4:
            sub_private = self.neutron.create_subnet({
                'subnet':
                    {'name':"sub",
                     'network_id': private_net['network']['id'],
                     'ip_version': 4,
                     'cidr': DEFAULT_IPV4_INT + '.0/24',
                     'dns_nameservers': [self.external_net + ".1", '8.8.8.8']
                    }})
        else:
            sub_private = self.neutron.create_subnet({
                'subnet':
                    {'name':"sub",
                     'network_id': private_net['network']['id'],
                     'ip_version': 4,
                     'cidr': DEFAULT_IPV6_INT + '/64',
                     'dns_nameservers': [self.external_net + "1"]
                    }})
        router = self.neutron.create_router({"router": {"name": "router1" }})
        self.neutron.add_interface_router(
            router['router']['id'],
            {"subnet_id": sub_private['subnet']['id']})
        self.neutron.add_gateway_router(
            router['router']['id'],
            {"network_id": public_net['network']['id']})
        if not os.path.exists(self.tmp_dir + "cirros-0.3.2-x86_64-uec.tar.gz"):
            urllib.urlretrieve(CIRROS_UEC_URL, self.tmp_dir + "cirros-0.3.2-x86_64-uec.tar.gz")
        return {
            "image_ref1": img1.id,
            "image_ref2": img2.id,
            "admin_tenant": admin_tenant,
            "admin": admin,


        }

    def create_config_file(self):
        data =  self.create_config()

        if 'WORKSPACE' in os.environ:
            tempest_dir = os.path.join(os.environ['WORKSPACE'], "tempest/.venv/bin")
        else:
            tempest_dir = os.path.join(os.path.dirname(__file__), "..", "..", "tempest/.venv/bin")
        parser = ConfigParser.SafeConfigParser(defaults={
            "debug": "True",
            "log_file": "tempest.log",
            "use_stderr": "False",
            "lock_path": self.locks_dir
        })
        parser.add_section("cli")
        parser.set('cli', "cli_dir", tempest_dir)
        parser.add_section("compute")
        parser.set("compute", "ssh_connect_method", "floating")
        parser.set("compute", "flavor_ref", "1")
        parser.set("compute", "flavor_ref_alt", "2")
        parser.set("compute", "image_alt_ssh_user", "cirros")
        parser.set("compute", "image_ssh_user", "cirros")
        parser.set("compute", "image_ref", data["image_ref1"])
        parser.set("compute", "image_ref_alt", data["image_ref2"])
        parser.set("compute", "ssh_timeout", "196")
        parser.set("compute", "ip_version_for_ssh", str(self.ipv))
        parser.set("compute", "network_for_ssh", "private")
        parser.set("compute", "ssh_user", "cirros")
        parser.set("compute", "allow_tenant_isolation", "True")
        parser.set("compute", "build_timeout", "300")
        parser.set("compute", "run_ssh", "False")
        parser.add_section("compute-admin")
        parser.set("compute-admin", "tenant_name", data["admin_tenant"][0])
        parser.set("compute-admin", "password", DEFAULT_PASS)
        parser.set("compute-admin", "username", data["admin"].username)
        parser.add_section("compute-feature-enabled")
        parser.set("compute-feature-enabled", "block_migration_for_live_migration", "False")
        parser.set("compute-feature-enabled", "change_password", "False")
        parser.set("compute-feature-enabled", "live_migration", "False")
        parser.set("compute-feature-enabled", "resize", "True")
        parser.set("compute-feature-enabled", "api_v3", "False")







    def run(self):
        pass


def parse_config(o):
    config = {}
    if 'OS_AUTH_URL' in os.environ:
        config["auth_url"] = os.environ['OS_AUTH_URL']
        config["tenant_id"] = os.environ['OS_TENANT_ID']
        config["tenant_name"] = os.environ['OS_TENANT_NAME']
        config["username"] = os.environ['OS_USERNAME']
        config["password"] = os.environ['OS_PASSWORD']
        config["region"] = os.environ['OS_REGION_NAME']
    elif o.openrc:
        text = o.openrc.read()
        o.openrc.close()
        export_lines = (i for i in text.split("\n") if env_re.search(i))
        os_vars = (env_re.search(i).group(1) for i in export_lines)
        config = dict(((z.replace("'", "").replace('"', '') for z in  i.split("=")) for i in os_vars))
    elif o.ip:
        if o.user and o.password:
            web = OSWebCreds(o.ip, o.user, o.password)
            config = web.creds()
        else:
            web = OSWebCreds(o.ip, DEFAULT_USER, DEFAULT_PASS)
            config = web.creds()
        if config is None:
            print "Can not download WEB credentials!"
            sys.exit(1)
    else:
        print "No credentials are provided!"
        sys.exit(1)
    config["ipv"] = 4 if o.ipv == 4 else 6
    cur_dir = os.path.join(os.path.dirname(__file__))
    if os.path.exists(os.path.join(cur_dir, "external_net")):
        with open(os.path.join(cur_dir, "external_net")) as f:
            config["external_net"] = f.read()
    else:
        if o.ipv == 4:
            config["external_net"] = "10.10.10"
        else:
            config["external_net"] = "2002::"
    return config


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-o', action='store', dest='openrc', type=argparse.FileType('r'), default=None,
                    help='Openrc configuration file')
    parser.add_argument('-i', action='store', dest='ip',
                    help='IP address of Openstack instalaltion for downloading credentials')
    parser.add_argument('-u', action='store', dest='user', default="admin",
                    help='Admin username of Openstack instalaltion for downloading credentials')
    parser.add_argument('-p', action='store', dest='password', default="Cisco123",
                    help='Admin password of Openstack instalaltion for downloading credentials')
    parser.add_argument('-a', action='store', dest='ipv', type=int, default=4, choices=[4, 6],
                    help='IP version for configuration: 4 or 6')
    parser.add_argument('-n', action='store_true', dest='unconfig', default=False,
                    help="Remove tempest configuration from Openstack only, don't configure")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')

    opts = parser.parse_args()
    options = parse_config(opts)
    print options
    tempest = Tempest(options)
    tempest.unconfig()
    if not opts.unconfig:
        tempest.config()

if __name__ == "__main__":
    main()
