import os
import yaml

from network import Network
from storage import Storage
from cloudtools import conn
from config import TEMPLATE_PATH

with open(os.path.join(TEMPLATE_PATH, "network.yaml")) as f:
    netconf = yaml.load(f)
with open(os.path.join(TEMPLATE_PATH, "vm.yaml")) as f:
    vmconf = yaml.load(f)


class VM:
    pool = {}
    def __init__(self, lab_id, path, config, box):
        self.path = path
        self.lab_id = lab_id
        self.box = box
        self.conf = config["servers"][box]
        self.full_conf = config
        self.names = [self.lab_id + "-" + self.box + "%.2d" % num if self.conf['params']['count'] != 1 \
                          else self.lab_id + "-" + self.box for num in xrange(self.conf['params']['count'])]


    def network(self, index):
        xml = ""
        for net in self.conf['params']['networks']:
            net_dhcp = [i for i in self.full_conf['networks'] if net in i][0][net]["dhcp"] # True or False
            if net_dhcp:
                xml += netconf['template']["interface_dhcp"].format(
                    net_name=net,
                    mac=Network.hosts[0][self.box][index]["mac"]
                )
            else:
                xml += netconf['template']["interface"].format(net_name=net)

    def storage(self, index):
        return Storage.disks[self.names[index]]


    def define(self):
        return [vmconf[self.box]["xml"].format(
            name=self.names[num],
            ram=self.conf['params']["ram"],
            cpu=self.conf['params']["cpu"],
            network=self.network(num),
            disk=self.storage(num),
        ) for num in xrange(self.conf['params']['count'])]


    def start(self):
        vm_xmls = self.define()
        for vm_xml in vm_xmls:
            vm = conn.defineXML(vm_xml)
            vm.create()

