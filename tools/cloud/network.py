import os
import random
import yaml

from cloudtools import conn, make_network_name
from config import opts, DOMAIN_NAME, DNS, TEMPLATE_PATH

with open(os.path.join(TEMPLATE_PATH, "network.yaml")) as f:
    netconf = yaml.load(f)
with open(os.path.join(TEMPLATE_PATH, "lab.yaml")) as f:
    env = yaml.load(f)
with open(os.path.join(TEMPLATE_PATH, "host_template.yaml")) as f:
    hostconf = yaml.load(f)


def rand_mac():
    mac = [0x52, 0x54, 0x00,
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff)]
    return ':'.join(["%02x" % x for x in mac])


class Network:
    pool = {}
    hosts = []

    def __init__(self, lab_id, config, name, net_shift, **kwargs):
        self.xml = netconf["template"]
        self.lab_id = lab_id
        self.name = make_network_name(lab_id, name)
        self.config = config
        for key in kwargs:
            setattr(self, key, kwargs.get(key))
        self.denition = None
        lab_ip = env[self.lab_id]["net_start"]
        self.net_ip = ".".join(lab_ip.split(".")[:2] + [str(int(lab_ip.split(".")[-1]) + net_shift)] + ["0"])
        self.net_ip_base = ".".join(self.net_ip.split(".")[:-1])
        self.interface = None

    def dhcp_definition(self):
        hosts_def = {}
        ip_start = env[self.lab_id]["ip_start"]
        servers_count = sum([self.config['servers'][i]['params']['count'] for i in self.config['servers']])
        ips = [self.net_ip_base + "." + str(ip_start + i) for i in xrange(servers_count)]
        ip_iter = iter(ips)
        for server in sorted(self.config['servers']):
            params = self.config['servers'][server]['params']
            hosts_def[server] = []
            for num in xrange(params['count']):
                if params['count'] == 1:
                    hostname = server if not params['hostname'] else params['hostname']
                else:
                    hostname = server + "%.2d" % num if not params['hostname'] else params['hostname']
                ip = ip_iter.next()
                ip_base = ip.split(".")[-1]
                hosts_def[server] += [
                    {"hostname": hostname,
                     "mac": rand_mac(),
                     "ip": ip,
                     "ip_base": ip_base,
                     "domain": DOMAIN_NAME}
                ]
        dhcp_hosts = "\n".join([
            netconf["template"]["dhcp_host"].format(**kwargs)
            for host in hosts_def.values()
            for kwargs in host])
        self.hosts.append(hosts_def)
        return netconf["template"]["dhcp_def"].format(
            dhcp_records=dhcp_hosts,
            net_ip=self.net_ip_base
        )

    def dns_definition(self):
        dns_hosts = "\n".join(
            [netconf["template"]["dns_host"].format(
                net_ip=self.net_ip_base,
                host_ip=self.dns[i],
                host=i,
                domain=DOMAIN_NAME)
             for i in self.dns])
        return netconf["template"]["dns_def"].format(
            dns_records=dns_hosts
        )

    def define(self):
        dhcp_text = self.dhcp_definition() if self.dhcp else ""
        dns_text = self.dns_definition() if self.dns else ""
        nat_text = netconf["template"]["nat"] if self.nat else ""
        return netconf["template"]["xml"].format(
            name=self.name,
            net_ip=self.net_ip_base,
            domain=DOMAIN_NAME,
            dhcp=dhcp_text,
            dns=dns_text,
            nat=nat_text
        )

    def define_interface(self):
        distr_prefix = opts.distro + "_"
        if self.external:
            self.interface = hostconf[distr_prefix + 'manual_interface_template'].format(
                int_name="{int_name}")
        elif self.dhcp:
            self.interface = hostconf[distr_prefix + 'dhcp_interface'].format(
                int_name="{int_name}")
        else:
            self.interface = hostconf[distr_prefix + 'static_interface_template'].format(
                int_name="{int_name}",
                int_ip="{int_ip}",
                net_ip=self.net_ip_base,
                dns=DNS)

    @staticmethod
    def network_combine(net, ip):
        return net + "." + ip

    def create(self):
        xml = self.define()
        self.define_interface()
        net = conn.networkDefineXML(xml)
        net.create()
        net.setAutostart(True)
        self.pool[self.name] = [net, self]


class Network6(Network):
    pass