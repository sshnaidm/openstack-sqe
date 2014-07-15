import os
import yaml

from network import Network, Network6
from storage import Storage
from domain import VM

from cloudtools import erase_net, erase_pool, erase_vm, remove_all_imgs, conn


class Lab:
    nets = {}
    report = {}

    def __init__(self,
                 lab_id,
                 config,
                 lab_img_path,
                 boot,
                 cloud_disk,
                 ipv):
        self.id = lab_id
        self.boxes = {}
        self.path = os.path.join(lab_img_path, lab_id)
        self.boot = boot
        self.cloud_disk = cloud_disk
        self.topo = config
        self.ipv = ipv

    def create_networks(self):
        for num, net in enumerate(self.topo["networks"]):
            net_name = net.keys()[0]
            net_shift = num
            if self.ipv == 4:
                net_class = Network
            else:
                net_class = Network6
            n = net_class(
                lab_id=self.id,
                config=self.topo,
                name=net_name,
                net_shift=net_shift,
                **net.values()[0]
            )
            self.nets[net_name] = n.create()

    def create_storage(self):
        for box in self.topo["servers"]:
            storage = Storage(
                self.id,
                self.topo,
                self.path,
                self.boot,
                box,
                self.cloud_disk
            )
            storage.setup()

    def create_vms(self):
        for box in self.topo["servers"]:
            vm = VM(self.id, self.path, self.topo, box)
            vm.start()
        self.report["servers"] = VM.pool
        if "external_net" in self.report["servers"]:
            self.report["external_net"] = self.report["servers"].pop("external_net")

    def print_reports(self):
        print yaml.dump(self.report)
        if "external_net" in self.report:
            with open("external_net", "w") as f:
                f.write(".".join(self.report["external_net"].split(".")[:3]))


    def delete_networks(self):
        erase_net(lab=self.id)

    def delete_storage(self):
        erase_pool(lab=self.id)
        remove_all_imgs(self.path)

    def delete_vms(self):
        erase_vm(lab=self.id)

    def setup(self):
        self.create_networks()
        self.create_storage()
        self.create_vms()
        self.print_reports()

    def destroy(self):
        self.delete_networks()
        self.delete_storage()
        self.delete_vms()

    def shutdown(self):
        for box in self.boxes:
            box.shutdown()
