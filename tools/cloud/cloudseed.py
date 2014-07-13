import os
import yaml
import crypt

from network import Network, DOMAIN_NAME
from config import TEMPLATE_PATH
from tempfile import NamedTemporaryFile
from cloudtools import run_cmd

with open(os.path.join(TEMPLATE_PATH, "host_template.yaml")) as f:
    hostconf = yaml.load(f)


class SeedStorage:
    def __init__(self, server, config, path, num, full_conf):
        self.server = server
        self.index = num
        self.yaml = config[self.server]["user-yaml"]
        self.path = path
        self.full_conf = full_conf

    def define(self):
        ydict = yaml.load(self.yaml)
        ydict['users'][1]['ssh-authorized-keys'] = hostconf['id_rsa_pub']
        ydict['users'][1]['passwd'] = crypt.crypt(ydict['users'][1]['passwd'], "$6$rounds=4096")
        ydict['write_files'][0]['content'] = "\n".join(hostconf['id_rsa_pub'])
        nets = self.full_conf[self.server]['networks']
        ifupdown = []
        for num, net in enumerate(nets):
            interface = Network.pool[net][1].interface
            interface_ip = Network.network_combine(
                Network.pool[net][1].net_ip,
                Network.hosts[0][self.server][self.index]['ip_base']
            )
            ydict["write_files"].append({
                "content": interface.format(int_name="eth" + str(num), int_ip=interface_ip),
                "path": "/etc/network/interfaces.d/eth{int_num}.cfg".format(int_num=num),
            })
            ifupdown.append("eth{int_num}".format(int_num=num))
        hostname = Network.hosts[0][self.server][self.index]['hostname']
        hosts_file = hostconf['hosts_template'].format(
            server_name=hostname,
            domain_name=DOMAIN_NAME)
        ydict["write_files"].append({"content": hosts_file, "path": "/etc/hosts"})
        cmds = []
        for cmd in ydict['runcmd']:
            if "hostname" in cmd:
                cmds.append("/bin/hostname " + hostname)
                cmds.append("/bin/echo " + hostname + " > /etc/hostname")
            elif "ifdown" in cmd:
                for i in ifupdown:
                    cmds.append("/sbin/ifdown {int} && /sbin/ifup {int}".format(int=i))
                cmds.append("/etc/init.d/networking restart")
            else:
                cmds.append(cmd)
        ydict['runcmd'] = cmds
        return yaml.dump(ydict)

    def create(self):
        c_localds = os.path.join(os.path.dirname(__file__), "cloud-localds")
        cloud_init = self.define()
        with NamedTemporaryFile() as temp:
            temp.write("#cloud-config\n" + cloud_init)
            run_cmd([c_localds, "-d", "qcow2", self.path, temp.name])


class SeedStorageRedHat(SeedStorage):
    pass
