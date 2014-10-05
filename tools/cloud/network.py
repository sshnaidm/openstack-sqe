import os
import random
import yaml

from cloudtools import conn, make_network_name
from config import opts, DOMAIN_NAME, DNS, TEMPLATE_PATH, ip_order

with open(os.path.join(TEMPLATE_PATH, "network.yaml")) as f:
    netconf = yaml.load(f)
with open(os.path.join(TEMPLATE_PATH, "lab.yaml")) as f:
    env = yaml.load(f)
with open(os.path.join(TEMPLATE_PATH, "host_template.yaml")) as f:
    hostconf = yaml.load(f)


def rand_net():
    return "".join([str(random.randint(1,9)) for i in xrange(4)])

def rand_mac():
    mac = [0x52, 0x54, 0x00,
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff)]
    return ':'.join(["%02x" % x for x in mac])

NET6 = "2001:dead:badd:%s::" % rand_net()

class Network(object):
    pool = {}
    hosts = []

    def __init__(self, lab_id, config, name, net_shift, **kwargs):
        self.xml = netconf["template"]
        self.lab_id = lab_id
        self.name = make_network_name(lab_id, name)
        self.config = config
        self.net_shift = net_shift
        self.ipv = None
        for key in kwargs:
            setattr(self, key, kwargs.get(key))
        self.denition = None
        lab_ip = env[self.lab_id]["net_start"]
        self.net_ip = ".".join(lab_ip.split(".")[:2] + [str(int(lab_ip.split(".")[-1]) + self.net_shift)] + ["0"])
        self.net_ip_base = ".".join(self.net_ip.split(".")[:-1])
        self.interface = None
        self.ipv6 = False
        self.dns_host_template = netconf["template"]["dns_host"]

    def dhcp_definition(self):
        hosts_def = {}
        ip_start = env[self.lab_id]["ip_start"]
        servers_count = sum([self.config['servers'][i]['params']['count'] for i in self.config['servers']])
        ips = [self.net_ip_base + "." + str(ip_start + i) for i in xrange(servers_count)]
        ip_iter = iter(ips)
        for server in sorted(self.config['servers'], key=lambda k: ip_order.index(k) if k in ip_order else -1):
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
            [self.dns_host_template.format(
                net_ip=self.net_ip_base,
                host_ip=self.dns[i],
                host=i,
                domain=DOMAIN_NAME)
             for i in self.dns])
        return netconf["template"]["dns_def"].format(
            dns_records=dns_hosts
        )

    def dhcp6_definition(self):
        return netconf["template"]["dhcp_def6"].format(
            dhcp_records="",
            start_ip=NET6 + "::500",
            end_ip=NET6 + "::800"
        )

    def define(self):
        dhcp_text = self.dhcp_definition() if getattr(self, "dhcp", None) else ""
        dhcp6_text = self.dhcp6_definition() if getattr(self, "dhcp6", None) else ""
        dns_text = self.dns_definition() if getattr(self, "dns", None) else ""
        nat_text = netconf["template"]["nat"] if getattr(self, "nat", None) else ""
        if self.ipv == 64:
            template = netconf["template"]["xml64"]
        else:
            template = netconf["template"]["xml"]
        return template.format(
            name=self.name,
            net_ip=self.net_ip_base,
            domain=DOMAIN_NAME,
            dhcp=dhcp_text,
            dhcp6=dhcp6_text,
            dns=dns_text,
            nat=nat_text,
            prefix="64",
            gateway=NET6
        )

    def define_interface(self):
        distr_prefix = opts.distro + "_"
        if getattr(self, "external", None):
            self.interface = hostconf[distr_prefix + 'manual_interface_template'].format(
                int_name="{int_name}")
        elif getattr(self, "dhcp", None):
            self.interface = hostconf[distr_prefix + 'dhcp_interface'].format(
                int_name="{int_name}")
        else:
            gateway = ""
            if getattr(self, "nat", None):
                gateway = hostconf[distr_prefix + 'gateway_template'].format(net_ip=self.net_ip_base)
            self.interface = hostconf[distr_prefix + 'static_interface_template'].format(
                int_name="{int_name}",
                int_ip="{int_ip}",
                net_ip=self.net_ip_base,
                gateway=gateway,
                dns=DNS)

    @staticmethod
    def network_combine(net, ip):
        return ".".join(net.split(".")[:3] + [ip])

    def create(self):
        xml = self.define()
        self.define_interface()
        net = conn.networkDefineXML(xml)
        net.create()
        net.setAutostart(True)
        self.pool[self.name] = [net, self]



class Network6(Network):
    def __init__(self, *args, **kwargs):
        super(Network6, self).__init__(*args, **kwargs)
        self.ipv6 = True
        self.net_ip_base = "2001:dead:beaf:%s" % rand_net()
        self.net_ip = self.net_ip_base + "::"
        self.prefix = "64"
        self.gw = self.net_ip + "1"
        self.dns_host_template = netconf["template"]["dns6_host"]
        #if getattr(self, "dhcp", None):
        #    raise NotImplementedError("IPv6 DHCP is not implemented yet!")

    def define_hosts(self):
        ip_start = env[self.lab_id]["ip_start"]
        servers_count = sum([self.config['servers'][i]['params']['count'] for i in self.config['servers']])
        ips = [self.net_ip_base + "::" + str(ip_start + i) for i in xrange(servers_count)]
        ip_iter = iter(ips)
        hosts_def = {}
        for server in sorted(self.config['servers'], key=lambda k: ip_order.index(k) if k in ip_order else -1):
            params = self.config['servers'][server]['params']
            hosts_def[server] = []
            for num in xrange(params['count']):
                if params['count'] == 1:
                    hostname = server if not params['hostname'] else params['hostname']
                else:
                    hostname = server + "%.2d" % num if not params['hostname'] else params['hostname']
                ip = ip_iter.next()
                ip_base = ip.split(":")[-1]
                hosts_def[server] += [
                    {"hostname": hostname,
                     "mac": rand_mac(),
                     "ip": ip,
                     "ip_base": ip_base,
                     "domain": DOMAIN_NAME}
                ]
        self.hosts.append(hosts_def)

    def dhcp_definition(self):
        return netconf["template"]["dhcp_def6"].format(
            dhcp_records="",
            start_ip=self.net_ip_base + "::500",
            end_ip=self.net_ip_base + "::800"
        )

    def define(self):
        dhcp_text = self.dhcp_definition() if getattr(self, "dhcp", None) else ""
        dns_text = self.dns_definition() if getattr(self, "dns", None) else ""
        nat_text = netconf["template"]["nat"] if getattr(self, "nat", None) else ""
        self.define_hosts()

        return netconf["template"]["xml6"].format(
            name=self.name,
            gateway=self.gw,
            prefix=self.prefix,
            domain=DOMAIN_NAME,
            dhcp=dhcp_text,
            dns=dns_text,
            nat=nat_text
        )

    def define_interface(self):
        distr_prefix = opts.distro + "_"
        if getattr(self, "external", None):
            self.interface = hostconf[distr_prefix + 'manual_interface_template6'].format(
                int_name="{int_name}")
        else:
            self.interface = hostconf[distr_prefix + 'static_interface_template6'].format(
                int_name="{int_name}",
                int_ip="{int_ip}",
                prefix=self.prefix,
                gateway=self.gw,
                dns=self.gw)

    @staticmethod
    def network_combine(net, ip):
        return net + ip
