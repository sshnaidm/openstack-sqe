import yaml
import os
from StringIO import StringIO

from config import DOMAIN_NAME, CONFIG_PATH, opts
from deploy import Standalone
from common import run_services, track_cobbler
from utils import change_ip_to, dump, warn_if_fail
from StringIO import StringIO
from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get



__author__ = 'sshnaidm'



class Role2(Standalone):
    def __init__(self, *args):
        super(Role2, self).__init__(*args)
        self.env = {"vendor": "cisco",
                    "scenario": "2_role"}
        self.scenario = "2_role"
        self.build = None
        self.cls = Role2Deploy
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
        servers = self.conf_yaml["servers"]["control-server"] + self.conf_yaml["servers"]["compute-server"]
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


class Role2Deploy:


    @staticmethod
    def prepare_2role_files(config, paths, use_sudo_flag):

        def prepare_common(config, common_file):
            """ Prepare user.common.file """
            conf = yaml.load(common_file)
            conf["controller_public_address"] = config['servers']['control-server'][0]['ip']
            conf["controller_admin_address"] = config['servers']['control-server'][0]['ip']
            conf["controller_internal_address"] = config['servers']['control-server'][0]['ip']
            conf["coe::base::controller_hostname"] = "control-server00"
            conf["domain_name"] = "domain.name"
            conf["ntp_servers"] = ["ntp.esl.cisco.com"]
            conf["external_interface"] = "eth4"
            conf["nova::compute::vncserver_proxyclient_address"] = "%{ipaddress_eth0}"
            conf["build_node_name"] = "build-server"
            conf["controller_public_url"] = change_ip_to(
                conf["controller_public_url"],
                config['servers']['control-server'][0]['ip'])
            conf["controller_admin_url"] = change_ip_to(
                conf["controller_admin_url"],
                config['servers']['control-server'][0]['ip'])
            conf["controller_internal_url"] = change_ip_to(
                conf["controller_internal_url"],
                config['servers']['control-server'][0]['ip'])
            conf["cobbler_node_ip"] = config['servers']['build-server'][0]['ip']
            conf["node_subnet"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".0"
            conf["node_gateway"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".1"
            conf["swift_internal_address"] = config['servers']['control-server'][0]['ip']
            conf["swift_public_address"] = config['servers']['control-server'][0]['ip']
            conf["swift_admin_address"] = config['servers']['control-server'][0]['ip']
            conf['mysql::server::override_options']['mysqld']['bind-address'] = config['servers']['control-server'][0]['ip']
            conf['internal_ip'] = "%{ipaddress_eth0}"
            conf['public_interface'] = "eth0"
            conf['private_interface'] = "eth0"
            conf['install_drive'] = "/dev/vda"
            conf['ipv6_ra'] = 1
            conf['packages'] = conf['packages'] + " radvd"
            conf['service_plugins'] += ["neutron.services.metering.metering_plugin.MeteringPlugin"]
            return dump(conf)

        def prepare_cobbler(config, cob_file):
            """
                Function creates cobbler configuration

            :param config:  configuration of lab boxes
            :param cob_file: the provided cobbler.yaml from distro
            :return: text dump of new cobbler.yaml file
            """
            new_conf = {}
            name = "trusty"
            with open(os.path.join(CONFIG_PATH, "cobbler.yaml")) as f:
                text_cobbler = f.read()
            text_cobbler = text_cobbler.format(
                int_ipadd="{$eth0_ip-address}",
                ip_gateway=".".join((config['servers']['build-server'][0]["ip"].split(".")[:3])) + ".1",
                ip_dns=".".join((config['servers']['build-server'][0]["ip"].split(".")[:3])) + ".1"
            )

            for c in config['servers']['control-server']:
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
            for c in config['servers']['compute-server']:
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
            for c in config["servers"]["control-server"]:
                roles[c["hostname"]] = "controller"
            for c in config["servers"]["compute-server"]:
                roles[c["hostname"]] = "compute"
            return dump(roles)

        def prepare_build(config, build_file):
            return build_file

        map = {
            "user.common.yaml": prepare_common,
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
    def prepare_new_2role_files(config, path, use_sudo_flag):
        """ Prepare hostname specific files in puppet/data/hiera_data/hostname """

        def write(text, path, filename, sudo):
            fd = StringIO(text)
            warn_if_fail(put(fd, os.path.join(path, filename), use_sudo=sudo))
            warn_if_fail(put(fd, os.path.join(path, filename.replace("-", "_")), use_sudo=sudo))

        file_name = config["servers"]["build-server"]["hostname"] + ".yaml"
        b_text = "apache::default_vhost: true"
        write(b_text, path, file_name, use_sudo_flag)

    @staticmethod
    def prepare_all_files(self, config, use_sudo_flag):
        self.prepare_2role_files(config,
                      paths=(
                      "/etc/puppet/data/hiera_data/user.common.yaml",
                      "/etc/puppet/data/cobbler/cobbler.yaml",
                      "/etc/puppet/data/role_mappings.yaml",
                      "/etc/puppet/data/hiera_data/hostname/build_server.yaml"
                      ),
                      use_sudo_flag=use_sudo_flag)
        self.prepare_new_2role_files(
            config,
            path="/etc/puppet/data/hiera_data/hostname",
            use_sudo_flag=use_sudo_flag
        )

