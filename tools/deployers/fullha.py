import yaml
import os
from StringIO import StringIO

from config import DOMAIN_NAME, CONFIG_PATH, opts
from common import track_cobbler, run_services
from utils import change_ip_to, dump, warn_if_fail
from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from deploy import Standalone


__author__ = 'sshnaidm'


class FullHA(Standalone):

    def __init__(self, *args):
        Standalone.__init__(*args)
        self.env = {"vendor": "cisco",
                    "scenario": "full_ha"}
        self.scenario = "full_ha"
        self.build = None
        if self.conf_yaml:
            self.build = self.conf_yaml['servers']['build-server'][0]

    def parse_file(self):
        self.host = self.build["ip"]
        self.user = self.build["user"]
        self.password = self.build["password"]

    def postrun(self):
        job = {
            "host_string": None,
            "user": self.user,
            "password": self.password,
            "warn_only": True,
            "key_filename": self.ssh_key,
            "abort_on_prompts": True,
            "gateway": self.conf.gateway
        }
        servers = self.conf_yaml['servers']['control-servers'] + \
            self.conf_yaml["servers"]["compute-servers"] + \
            self.conf_yaml["servers"]["swift-storage"] + \
            self.conf_yaml["servers"]["swift-proxy"] + \
            self.conf_yaml["servers"]["load-balancer"]
        if opts.use_cobbler:
            job['host_string'] = self.conf_yaml["servers"]["build-server"][0]["ip"]
            track_cobbler(self.conf_yaml, job, servers)
        else:
            for host in servers:
                job['host_string'] = host["ip"]
                run_services(host,
                             job,
                             verbose=self.verb,
                             envs=self.env,
                             config=self.conf_yaml,
                             scenario=self.scenario
                             )



class FullHADeploy:

    @staticmethod
    def prepare_fullha_files(self, config, paths, use_sudo_flag):

        def prepare_fullha(config, ha_file):
            """ Prepare user.full_ha.file """
            conf = yaml.load(ha_file)
            net_ip = ".".join((config['servers']['control-servers'][0]['ip'].split(".")[:3]))
            vipc = net_ip + ".253"
            conf["coe::base::controller_hostname"] = "control-server"
            conf["horizon::keystone_url"] = change_ip_to(conf["horizon::keystone_url"], vipc)
            conf["controller_names"] = [c["hostname"] for c in config['servers']['control-servers']]
            conf["openstack-ha::load-balancer::controller_ipaddresses"] = [c["ip"]
                                                                           for c in config['servers']['control-servers']]
            conf["openstack-ha::load-balancer::swift_proxy_ipaddresses"] = [c["ip"]
                                                                           for c in config['servers']['swift-proxy']]
            conf["openstack-ha::load-balancer::swift_proxy_names"] = [c["hostname"]
                                                                           for c in config['servers']['swift-proxy']]
            vipsw = net_ip + ".252"
            conf["openstack::swift::proxy::swift_proxy_net_ip"] = "%{ipaddress_eth2}"
            conf["openstack::swift::proxy::swift_memcache_servers"] = [i["ip"] + ":11211"
                                                                       for i in config['servers']['swift-proxy']]
            conf["nova::memcached_servers"] = [i["ip"] + ":11211" for i in config['servers']['control-servers']]
            conf["rabbit_hosts"] = [i["hostname"] + ":5672" for i in config['servers']['control-servers']]
            conf["galera::galera_servers"] = [c["ip"] for c in config['servers']['control-servers']]
            conf["galera::galera_master"] = config['servers']['control-servers'][0]["hostname"] + "." + DOMAIN_NAME
            conf["galera_master_name"] = config['servers']['control-servers'][0]["hostname"]
            conf["galera_master_ipaddress"] = config['servers']['control-servers'][0]["ip"]
            conf["galera_backup_names"] = [i["hostname"] for i in config['servers']['control-servers'][1:]]
            conf["galera_backup_ipaddresses"] = [i["ip"] for i in config['servers']['control-servers'][1:]]
            conf["openstack::swift::storage-node::storage_devices"] = ["vdb", "vdc", "vdd"]
            return dump(conf)

        def prepare_common(config, common_file):
            """ Prepare user.common.file """
            conf = yaml.load(common_file)
            net_ip = ".".join((config['servers']['control-servers'][0]['ip'].split(".")[:3]))
            vipc = net_ip + ".253"
            conf["controller_public_address"] = vipc
            conf["controller_admin_address"] = vipc
            conf["controller_internal_address"] = vipc
            conf["coe::base::controller_hostname"] = "control-server"
            conf["domain_name"] = "domain.name"
            conf["ntp_servers"] = ["ntp.esl.cisco.com"]
            conf["external_interface"] = "eth4"
            conf["nova::compute::vncserver_proxyclient_address"] = "%{ipaddress_eth0}"
            conf["build_node_name"] = "build-server"
            conf["controller_public_url"] = change_ip_to(
                conf["controller_public_url"],
                vipc)
            conf["controller_admin_url"] = change_ip_to(
                conf["controller_admin_url"],
                vipc)
            conf["controller_internal_url"] = change_ip_to(
                conf["controller_internal_url"],
                vipc)
            conf["cobbler_node_ip"] = config['servers']['build-server']['ip']
            conf["node_subnet"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".0"
            conf["node_gateway"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".1"
            vipsw = ".".join((config['servers']['control-servers'][0]['ip'].split(".")[:3])) + ".252"
            conf["swift_internal_address"] = vipsw
            conf["swift_public_address"] = vipsw
            conf["swift_admin_address"] = vipsw
            conf['mysql::server::override_options']['mysqld']['bind-address'] = "0.0.0.0"
            #    config['servers']['control-servers'][0]['ip']
            conf['swift_storage_interface'] = "eth2"
            conf['swift_local_net_ip'] = "%{ipaddress_eth2}"
            conf['internal_ip'] = "%{ipaddress_eth0}"
            conf['public_interface'] = "eth0"
            conf['private_interface'] = "eth0"
            conf['install_drive'] = "/dev/vda"
            conf['mon_initial_members'] = config['servers']['control-servers'][0]["hostname"]
            conf['ceph_primary_mon'] = config['servers']['control-servers'][0]["hostname"]
            conf['ceph_monitor_address'] = config['servers']['control-servers'][0]["ip"]
            conf['ceph_cluster_interface'] = "eth0"
            conf['ceph_cluster_network'] = net_ip + ".0/24"
            conf['ceph_public_interface'] = "eth0"
            conf['ceph_public_network'] = net_ip + ".0/24"
            return dump(conf)

        def prepare_cobbler(config, cob_file):
            """ Prepare cobbler.yaml.file """
            new_conf = {}
            name = "trusty"
            with open(os.path.join(CONFIG_PATH, "cobbler.yaml")) as f:
                text_cobbler = f.read()
            text_cobbler = text_cobbler.format(
                int_ipadd="{$eth0_ip-address}",
                ip_gateway=".".join((config['servers']['build-server']["ip"].split(".")[:3])) + ".1",
                ip_dns=".".join((config['servers']['build-server']["ip"].split(".")[:3])) + ".1"
            )
            servers = config['servers']['control-servers'] + \
                config["servers"]["compute-servers"] + \
                config["servers"]["swift-storage"] + \
                config["servers"]["swift-proxy"] + \
                config["servers"]["load-balancer"]
            for c in servers:
                new_conf[c['hostname']] = {
                    "hostname": c['hostname'] + "." + DOMAIN_NAME,
                    "power_address": c["ip"],
                    "profile": "%s-x86_64" % name,
                    "interfaces": {
                        "eth0": {
                            "mac-address": c["mac"],
                            "dns-name": c['hostname'] + "." + DOMAIN_NAME,
                            "ip-address": c["ip"],
                            "static": "0"
                        }
                    }
                }

            return text_cobbler + "\n" + yaml.dump(new_conf)

        def prepare_role(config, role_file):
            """ Prepare role_mappings file """
            roles = {config["servers"]["build-server"]["hostname"]: "build"}
            for c in config["servers"]["control-servers"]:
                roles[c["hostname"]] = "controller"
            for c in config["servers"]["compute-servers"]:
                roles[c["hostname"]] = "compute"
            for c in config["servers"]["swift-storage"]:
                roles[c["hostname"]] = "swift_storage"
            for c in config["servers"]["swift-proxy"]:
                roles[c["hostname"]] = "swift_proxy"
            for c in config["servers"]["load-balancer"]:
                roles[c["hostname"]] = "load_balancer"
            return dump(roles)

        def prepare_build(config, build_file):
            return build_file

        map = {
            "user.common.yaml": prepare_common,
            "user.full_ha.yaml": prepare_fullha,
            "role_mappings.yaml": prepare_role,
            "cobbler.yaml": prepare_cobbler,
            "build_server.yaml": prepare_build
        }
        for path in paths:
            fd = StringIO()
            warn_if_fail(get(path, fd))
            old_file = fd.getvalue()
            file_name = os.path.basename(path)
            print " >>>> FABRIC OLD %s\n" % file_name, old_file
            new_file = map[file_name](config, old_file)
            print " >>>> FABRIC NEW %s\n" % file_name, new_file
            warn_if_fail(put(StringIO(new_file), path, use_sudo=use_sudo_flag))

    @staticmethod
    def prepare_new_fullha_files(self, config, path, use_sudo_flag):
        """ Prepare hostname specific files in puppet/data/hiera_data/hostname """

        def write(text, path, filename, sudo):
            fd = StringIO(text)
            warn_if_fail(put(fd, os.path.join(path, filename), use_sudo=sudo))
            warn_if_fail(put(fd, os.path.join(path, filename.replace("-", "_")), use_sudo=sudo))

        for compute in config["servers"]["compute-servers"]:
            file_name = compute["hostname"] + ".yaml"
            ceph = {}
            ceph["cephdeploy::has_compute"] = True
            ceph["cephdeploy::osdwrapper::disks"] = ["vdb", "vdc", "vdd"]
            write(dump(ceph), path, file_name, use_sudo_flag)
        for num, lb in enumerate(config["servers"]["load-balancer"]):
            if num == 0:
                lb_text = ("openstack-ha::load-balancer::controller_state: MASTER\n"
                           "openstack-ha::load-balancer::swift_proxy_state: BACKUP\n"
                )
            else:
                lb_text = ("openstack-ha::load-balancer::controller_state: BACKUP\n"
                           "openstack-ha::load-balancer::swift_proxy_state: MASTER\n"
                )
            file_name = lb["hostname"] + ".yaml"
            write(lb_text, path, file_name, use_sudo_flag)
        for num, sw in enumerate(config["servers"]["swift-storage"]):
            sw_text = (
                'openstack::swift::storage-node::swift_zone: {num}\n'
                'coe::network::interface::interface_name: "%{{swift_storage_interface}}"\n'
                'coe::network::interface::ipaddress: "%{{swift_local_net_ip}}"\n'
                'coe::network::interface::netmask: "%{{swift_storage_netmask}}"\n'.format(num=num+1)
            )
            file_name = sw["hostname"] + ".yaml"
            write(sw_text, path, file_name, use_sudo_flag)
        file_name = config["servers"]["build-server"]["hostname"] + ".yaml"
        b_text = "apache::default_vhost: true"
        write(b_text, path, file_name, use_sudo_flag)

    @staticmethod
    def prepare_all_files(self,config, use_sudo_flag):
        self.prepare_fullha_files(config,
                      paths=(
                      "/etc/puppet/data/hiera_data/user.common.yaml",
                      "/etc/puppet/data/hiera_data/user.full_ha.yaml",
                      "/etc/puppet/data/cobbler/cobbler.yaml",
                      "/etc/puppet/data/role_mappings.yaml",
                      "/etc/puppet/data/hiera_data/hostname/build_server.yaml"
                      ),
                      use_sudo_flag=use_sudo_flag)
        self.prepare_new_fullha_files(
            config,
            path="/etc/puppet/data/hiera_data/hostname",
            use_sudo_flag=use_sudo_flag
        )

