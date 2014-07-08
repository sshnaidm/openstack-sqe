#!/usr/bin/python
import libvirt
import argparse
import random
import yaml
import os
import re
import sys
import logging
import subprocess

from xml.etree import ElementTree as et
from tempfile import mkstemp
from libvirt import libvirtError

__author__ = 'sshnaidm'


def rand_mac():
    mac = [0x52, 0x54, 0x00,
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff)]
    return ':'.join(["%02x" % x for x in mac])

## TODO: remove GLOBALS
name_woext = "trusty-server-cloudimg-amd64-disk1"
EXTERNAL_NET = "external"
DOMAIN_NAME = "domain.name"


with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates", "box.yaml")) as f:
    conf = yaml.load(f)
with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates", "env.yaml")) as f:
    env = yaml.load(f)

with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates", "vm.yaml")) as f:
    vmconf = yaml.load(f)
with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates", "network.yaml")) as f:
    netconf = yaml.load(f)

# For silent libvirt:
def handler(ctxt, err):
    global errno
    errno = err
libvirt.registerErrorHandler(handler, 'context')
conn = libvirt.open('qemu+ssh://root@localhost/system')


def run_cmd(cmd):
    """
        Return the exit status and output to stdout and stderr.
    """
    logging.debug("Running command: %s" % " ".join(cmd))
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            close_fds=True)
    ret = proc.wait()
    print >> sys.stderr, "\n".join(proc.stdout.readlines()), "\n".join(proc.stderr.readlines())
    return ret, proc.stdout.readlines(), proc.stderr.readlines()


def find_vm(name):
        try:
            return [i.name() for i in conn.listAllDomains() if name in i.name()]
        except Exception as e:
            print >> sys.stderr, "Exception when finding VMs:", e
            return []

def delete_vm(conn, name):
    try:
        vm = conn.lookupByName(name)
    except libvirtError:
        print >> sys.stderr, "Domain {name} not found, nothing to delete".format(name=name)
        return
    try:
        vm.destroy()
    except libvirtError:
        pass
    vm.undefine()
    print >> sys.stderr, "Domain {name} deleted".format(name=name)


class VM:
    pool = {}

    def __init__(self, id, hostname, name, mac):
        boot_net_name = 'boot'
        self.id = id
        self.hostname = hostname
        self.name = name
        self.storage = VMStorage(id)
        self.ram = 4
        self.cpu = 1
        self.nets = [boot_net_name]
        self.mac = mac
        self.net_xml = vmconf["mac-interface"].format(
            mac=self.mac,
            net_boot_name= self.id + "-net-" + boot_net_name
        )
        self.disk = None
        self.xml_def = None

    def create(self, name):
        self.net_xml += "\n".join(
            [vmconf["interface"].format(net_name=self.id + "-net-" + i)
                for i in self.nets])
        self.xml = self.xml_def.format(
            name=self.name,
            ram=self.ram * 1024 * 1024,
            disk=self.disk,
            networks=self.net_xml,
        )
        self.vm = conn.defineXML(self.xml)
        self.vm.create()
        self.pool[name] = self.vm

    def delete(self):
        try:
            self.vm.destroy()
        except libvirtError:
            pass
        self.vm.undefine()
        print >> sys.stderr, "Domain {name} deleted".format(name=self.name)

    def shutdown(self):
        try:
            self.vm.shutdown()
        except libvirtError:
            pass



class AioVM(VM):

    def __init__(self, lab_id, mac, hostname="all-in-one"):
        VM.__init__(id=lab_id, hostname=hostname, name=lab_id + "-aio-server", mac=mac)
        self.disk = self.storage.create_disk(1)
        self.ram = 8
        self.nets += ["admin", "external"]
        self.xml_def = vmconf["aio-server"]["xml"]

    def setup(self):
        self.create()


class BuildVM(VM):
    def __init__(self, lab_id, mac, hostname="build-server"):
        VM.__init__(id=lab_id, hostname=hostname, name=lab_id + "-build-server")
        self.disk = self.storage.create_disk(1)
        self.ram = 8
        self.nets += ["admin", "external"]
        self.xml_def = vmconf["build-server"]["xml"]

    def setup(self):
        self.create()

class ControlVM:
    pass


class ComputeVM:
    pass


class SwiftStorageVM:
    pass


class SwiftProxyVM:
    pass


class LoadBalVM:
    pass



def pool_found(self):
        try:
            conn.storagePoolLookupByName(self.pool_name)
            return True
        except libvirtError:
            return False


class VMStorage:
    disks = []

    def __init__(self, lab_id, img_path):
        self.pool_name = "default-" + lab_id
        self.path = img_path


    def create_pool(self):
        if pool_found():
            self.delete_pool()

        pool_xml = conf["params"]["pool"]["xml"].format(
            name=self.pool_name, path=self.path)
        self.pool = conn.storagePoolDefineXML(pool_xml)
        self.pool.create()
        self.pool.setAutostart(True)

    def delete_pool(self):
        try:
            pool = conn.storagePoolLookupByName(self.pool_name)
        except libvirtError:
            print >> sys.stderr, "Pool not found, nothing to delete"
            return
        try:
            pool.destroy()
        except libvirtError:
            print >> sys.stderr, "Pool wans't active, just undefine it"
        pool.undefine()

    def imgs_dir_setup(self):
        if not os.path.exists(self.path):
            try:
                os.mkdir(self.path)
            except Exception as e:
                print "Can't create directory for images '%s'\nException:" % self.path, e
                sys.exit(1)

    def delete_imgs(self):
        if os.path.exists(self.path):
            for i in os.listdir(self.path):
                os.remove(os.path.join(self.path, i))
        else:
            print >> sys.stderr, "Path %s doesn't exist!" % self.path

    def create_disk(self, count):


        pass


    def main_disk_create(name="", size=0, config=None, conn=None, img_path="", boot_type="net", user_seed_yaml=None,
                     img_uncomp_path=None, lab_id="lab1"):
        path = os.path.join(img_path, name + ".qcow2")
        size_bytes = size*1024*1024*1024
        if boot_type == "net":
            vol_xml = config["params"]["vol"]["xml"].format(name=name, size=size_bytes, path=path)
            pool = conn.storagePoolLookupByName("default-" + lab_id)
            vol = pool.createXML(vol_xml, 1)
            return config["params"]["vol"]["virt_disk"].format(output_file=path)
        elif boot_type == "cloudimg":
            seed_disk = os.path.join(img_path, name + "-seed.qcow2")
            _, tmp_file = mkstemp(prefix="useryaml_")
            with open(tmp_file, "w") as f:
                f.write("#cloud-config\n" + user_seed_yaml)
            run_cmd(["qemu-img", "create", "-f", "qcow2", "-b", img_uncomp_path, path, "%sG" % size])
            run_cmd(["cloud-localds", seed_disk, tmp_file])
            os.remove(tmp_file)
            return config["params"]["vol"]["cloudimg_disk"].format(output_file=path, seed_disk=seed_disk)

    def setup(self):
        self.imgs_dir_setup()
        self.create_pool()

    def remove(self):
        self.delete_pool()
        self.delete_imgs()



class Lab:
    def __init__(self,
                 lab_id,
                 config,
                 lab_img_path):
        self.id = lab_id
        self.config = config
        self.boxes = {}
        self.path = os.path.join(lab_img_path, lab_id)
        self.macs = [rand_mac() for _ in xrange(sum(self.config.values()))]
        self.roles = ("aio", "build", "control", "compute", "swift_storage", "swift_proxy", "load_balancer")

        self.network = None

    # config = {
    # "swiftproxy": 4.
    # "control": 3,
    # "compute": 1,
    # "build" : 1,
    # "aio": 0,
    # }

    def nets_create(self):
        self.network =  NetworkPool(self.id, self.rmac)
        self.network.setup()

    def nets_delete(self):
        self.network.remove()


    def define_vms(self):
        # sets = {
        #     "build": BuildVM,
        #     "aio": AioVM,
        #     "control": ControlVM,
        #     "compute": ComputeVM,
        #     "swift_storage": SwiftStorageVM,
        #     "swift_proxy": SwiftProxyVM,
        #     "load_balancer": LoadBalVM,
        # }
        sets = dict(zip(self.roles, (BuildVM,
                                     AioVM,
                                     ControlVM,
                                     ComputeVM,
                                     SwiftStorageVM,
                                     SwiftProxyVM,
                                     LoadBalVM)))
        rmac = dict([(i, [self.macs.pop() for _ in xrange(self.config[i])]) for i in self.roles if i in self.config])
        ip_start = env[self.id]["ip_start"]
        dhcp = {}
        dns = {}
        for role in self.roles:
            if role in self.config and self.config[role]:
                self.boxes[role] = []
                macs = iter(rmac[role])
                for num in xrange(self.config[role]):
                    vm = sets[role](self.id, macs.next())
                    self.boxes[role] += [vm]


    def vms_create(self):
        for key in self.boxes:
            for vm in key:
                vm.setup()


    def delete_vms(self):
        for k,v in self.boxes:
            for vm in v:
                vm.delete()


    def vm_storage_setup(self):
        storage = VMStorage(lab_id=self.id)
        storage.setup()

    def vm_storage_delete(self):
        storage = VMStorage(lab_id=self.id)
        storage.remove()

    def clean(self):
        old_vms = find_vm(self.id)
        for vm in old_vms:
            delete_vm(vm)
        self.vm_storage_delete()

    def setup(self):
        self.clean()
        self.vm_storage_setup()
        self.vms_create()

    def destroy(self):
        self.delete_vms()
        self.vm_storage_delete()

    def shutdown(self):
        for k,v in self.boxes:
            for vm in v:
                vm.shutdown()



def delete_net(self, net_name):
    try:
        net = conn.networkLookupByName(net_name)
    except libvirtError:
        print >> sys.stderr, "Net %s wasn't found, nothing to delete" % net_name
        return
    try:
        net.destroy()
    except libvirtError:
        print >> sys.stderr, "Net %s wasn't active, nothing to delete" % net_name
        return
    net.undefine()

class Network:
    pool = {}

    def __init__(self,
                 lab_id,
                 name,
                 net_ip,
                 dns=None,
                 dhcp=None,
                 nat=False):
        self.name = name
        self.lab_id = lab_id
        self.ip_start = env[lab_id]['ip_start']
        self.net_ip = net_ip
        self.xml = netconf["template"]["xml"]
        self.nat = nat
        self.dhcp = dhcp
        self.dns = dns

    def define_xml(self):
        if self.nat:
            nat = ("<forward mode='nat'>\n"
            "  <nat>\n"
            "    <port start='1024' end='65535'/>\n"
            "  </nat>\n"
            "</forward>\n")
        else:
            nat = ""
        if self.dhcp:
            dhcp=("<dhcp>\n"
                  "<range start='{net_ip}.2' end='{net_ip}.250' />\n".format(net_ip=self.net_ip))
            for i in self.dhcp:
                dhcp += '<host mac="{server_mac}" name="{server_name}.{domain}" ip="{server_ip}"/>\n'.format(
                    server_mac=self.dhcp[i]["mac"],
                    server_name=self.dhcp[i]["hostname"],
                    domain=DOMAIN_NAME,
                    server_ip=self.net_ip + "." + self.dhcp[i]["ip"]
                )
            dhcp += "</dhcp>\n"
        else:
            dhcp = ""
        if self.dns:
            dns="<dns>\n"
            for i in self.dns:
                dns += ("<host ip='{net_ip}.2'>\n"
                "<hostname>{hostname}</hostname>\n"
                "<hostname>{hostname}.{domain}</hostname>\n"
                "</host>\n".format(
                    net_ip=self.net_ip,
                    hostname=self.dns[i]["hostname"],
                    domain=DOMAIN_NAME
                ))
            dns += "<\dns>\n"
        else:
            dns = ""
        return self.xml.format(
            name=self.lab_id + "-net-" + self.name,
            nat=nat,
            dns=dns,
            dhcp=dhcp
        )

    def setup(self):
        xml = self.define_xml()
        net = conn.networkDefineXML(xml)
        net.create()
        net.setAutostart(True)
        self.pool[self.name] = net


    def remove(self):
        for i in self.pool:
            delete_net(self.pool[i])






def net_create(conn, xml):
    net = conn.networkDefineXML(xml)
    net.create()
    net.setAutostart(True)
    return net


def net_undefine(conn, net_name):
    try:
        net = conn.networkLookupByName(net_name)
    except libvirtError:
        print >> sys.stderr, "Net %s wasn't found, nothing to delete" % net_name
        return
    try:
        net.destroy()
    except libvirtError:
        print >> sys.stderr, "Net %s wasn't active, nothing to delete" % net_name
        return
    net.undefine()


def pool_delete(conn, name):
    try:
        pool = conn.storagePoolLookupByName(name)
    except libvirtError:
        print >> sys.stderr, "Pool not found, nothing to delete"
        return
    try:
        pool.destroy()
    except libvirtError:
        print >> sys.stderr, "Pool wans't active, just undefine it"
    pool.undefine()


def pool_create(conn, xml):
    pool = conn.storagePoolDefineXML(xml)
    pool.create()
    pool.setAutostart(True)
    return pool




def convert_image(path, new_path):
    ret, ignore, stderr = run_cmd(["qemu-img", "convert", "-O",
                                   "qcow2", path, new_path])
    print >> sys.stderr, "\n".join(ignore), "\n".join(stderr)
    if ret == 127:
        ret, ignore, stderr = run_cmd(["kvm-img", "convert", "-O",
                                       "qcow2", path, new_path])
    if ret != 0:
        raise RuntimeError("Disk conversion failed with "
                           "exit status %d: %s" % (ret, "".join(stderr)))
    #if len(stderr):
    #    print >> sys.stderr, stderr


def main_disk_create(name="", size=0, config=None, conn=None, img_path="", boot_type="net", user_seed_yaml=None,
                     img_uncomp_path=None, lab_id="lab1"):
    path = os.path.join(img_path, name + ".qcow2")
    size_bytes = size*1024*1024*1024
    if boot_type == "net":
        vol_xml = config["params"]["vol"]["xml"].format(name=name, size=size_bytes, path=path)
        #_, tmp_file = mkstemp(prefix="disk_vol_")
        #with open(tmp_file, "w") as f:
        #    f.write(vol_xml)
        #run_cmd(["virsh", "vol-create",  "--pool", "default-" + lab_id, "--file", tmp_file])
        pool = conn.storagePoolLookupByName("default-" + lab_id)
        vol = pool.createXML(vol_xml, 1)
        #os.remove(tmp_file)
        return config["params"]["vol"]["virt_disk"].format(output_file=path)
    elif boot_type == "cloudimg":
        seed_disk = os.path.join(img_path, name + "-seed.qcow2")
        #img_uncomp_path=os.path.join(IMG_PATH, "lab-backing.qcow2")
        _, tmp_file = mkstemp(prefix="useryaml_")
        with open(tmp_file, "w") as f:
            f.write("#cloud-config\n" + user_seed_yaml)
        run_cmd(["qemu-img", "create", "-f", "qcow2", "-b", img_uncomp_path, path, "%sG" % size])
        run_cmd(["cloud-localds", seed_disk, tmp_file])
        os.remove(tmp_file)
        return config["params"]["vol"]["cloudimg_disk"].format(output_file=path, seed_disk=seed_disk)


def create_vm(conn, xml):
    vm = conn.defineXML(xml)
    vm.create()
    return vm


def findvm(conn, name):
    return [i.name() for i in conn.listAllDomains() if name in i.name()]


def findnet(conn, name):
    return [i.name() for i in conn.listAllNetworks() if name in i.name()]


def delete_vm(conn, name):
    try:
        vm = conn.lookupByName(name)
    except libvirtError:
        print >> sys.stderr, "Domain {name} not found, nothing to delete".format(name=name)
        return
    try:
        vm.destroy()
    except libvirtError:
        pass
    vm.undefine()
    print >> sys.stderr, "Domain {name} deleted".format(name=name)


def remove_all_imgs(lab_img_path):
    if os.path.exists(lab_img_path):
        for i in os.listdir(lab_img_path):
            os.remove(os.path.join(lab_img_path, i))
    else:
        try:
            os.mkdir(lab_img_path)
        except Exception as e:
            print "Can't create directory for images '%s'\nException:" % lab_img_path, e
            sys.exit(1)


def create_seed_yaml(config, box=None):
    if not box:
        return None
    user_seed_yaml_string = config['params'][box]['user-yaml']
    user_seed_yaml = yaml.load(user_seed_yaml_string)
    user_seed_yaml['users'][1]['ssh-authorized-keys'] = config['params']['id_rsa_pub']
    user_seed_yaml['users'][1]['passwd'] = ("$6$rounds=4096$A0eKrix5oH$4F70Syi4jfhMCRygdOUC.d.qItQ57KsmW8"
                                            "CHhs42r/bPm7ySXdYLoHCdpg3SLlWZlv9FnRAUhgp8C23DiVZr9.")
    user_seed_yaml['write_files'][0]['content'] = "\n".join(config['params']['id_rsa_pub'])
    return yaml.dump(user_seed_yaml)


def create_host_seed_yaml(config, box, btype):
    user_seed_yaml_string = config['params'][btype]['user-yaml']
    user_seed_yaml = yaml.load(user_seed_yaml_string)
    user_seed_yaml['users'][1]['ssh-authorized-keys'] = config['params']['id_rsa_pub']
    user_seed_yaml['users'][1]['passwd'] = ("$6$rounds=4096$A0eKrix5oH$4F70Syi4jfhMCRygdOUC.d.qItQ57KsmW8"
                                            "CHhs42r/bPm7ySXdYLoHCdpg3SLlWZlv9FnRAUhgp8C23DiVZr9.")
    user_seed_yaml['write_files'][0]['content'] = "\n".join(config['params']['id_rsa_pub'])
    ints = []
    last_octet = box['ip'].split(".")[-1]
    #sorted_nets = sorted(networks.keys(), key=lambda x: int(networks[x]["net-ip"].split(".")[2]))
    sorted_nets = config['params']['networks']
    parsed = et.fromstring(config['params'][btype]['xml'])
    used_nets = [i.attrib['network'] for i in parsed.findall(".//interface[@type='network']/source")]
    index_net = 1
    for k, net in enumerate(sorted_nets[1:]):
        if "{net_" + net['role'] + "_name}" in used_nets:
            if net['role'] != EXTERNAL_NET:
                ints.append([
                    config['params']['static_interface_template'].format(
                        int_name="eth"+str(index_net),
                        net_ip=net['net-ip'],
                        int_ip=net['net-ip'] + "." + last_octet,
                        dns="8.8.8.8"),
                    "/etc/network/interfaces.d/eth{int_num}.cfg".format(int_num=index_net),
                    "eth{int_num}".format(int_num=index_net)
                ])
            else:
                ints.append([
                    config['params']['manual_interface_template'].format(
                        int_name="eth"+str(index_net),),
                    "/etc/network/interfaces.d/eth{int_num}.cfg".format(int_num=index_net),
                    "eth{int_num}".format(int_num=index_net)
                    ])
            index_net += 1
        else:
            continue
    for interface in ints:
        user_seed_yaml["write_files"].append({
            "content": interface[0],
            "path": interface[1],
            })
    hosts_file = config['params']['hosts_template'].format(
        server_name=box["hostname"],
        domain_name=DOMAIN_NAME,
    )
    user_seed_yaml["write_files"].append({
        "content": hosts_file,
        "path": "/etc/hosts",
        })
    ## I'm really tired to investigate why this doesn't work!!!!
    #hostname_file = config['params']['hostname_template'].format(
    #    server_name=box["hostname"],
    #)
    #user_seed_yaml["write_files"].append({
    #    "content": hostname_file,
    #    "path": "/etc/hostname",
    #    })
    full_cmd = []
    for cmd in user_seed_yaml['runcmd']:
        if "hostname" in cmd:
            full_cmd.append("/bin/hostname " + box["hostname"])
            full_cmd.append("/bin/echo " + box["hostname"] + " > /etc/hostname")
        elif "ifdown" in cmd:
            for interf in ints:
                int_name = interf[2]
                full_cmd.append("/sbin/ifdown {int} && /sbin/ifup {int}".format(int=int_name))
            full_cmd.append("/etc/init.d/networking restart")
        else:
            full_cmd.append(cmd)
    user_seed_yaml['runcmd'] = full_cmd
    return yaml.dump(user_seed_yaml)


def delete_all(conn=None, lab_id=None, lab_img_path=None, conf=None):
    if lab_img_path:
        remove_all_imgs(lab_img_path)
    if conf:
        basic_name = lab_id + "-"
        vms = findvm(conn, basic_name)
        for vm_name in vms:
            delete_vm(conn, vm_name)
        nets = findnet(conn, basic_name)
        for net in nets:
            net_undefine(conn, net)
        pool_delete(conn, "default-" + lab_id)


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-u', action='store', dest='user',
                        help='User to run the script with')
    parser.add_argument('-a', action='store', dest='host', default=None,
                        help='Host for action')
    parser.add_argument('-b', action='store', dest='boot', default="cloudimg",
                        choices=['net', 'cloudimg'], help='Boot')
    parser.add_argument('-k', action='store', dest='computes', type=int, default=1,
                        help='How many compute servers')
    parser.add_argument('-n', action='store', dest='controls', type=int, default=1,
                        help='How many control servers')
    parser.add_argument('-l', action='store', dest='labid', default="lab1",
                        help='Lab ID in configuration, default=lab1')
    parser.add_argument('-g', action='store', dest='cpus', type=int, default=1,
                        help='How many cpu for compute servers')
    parser.add_argument('-d', action='store', dest='img_dir', default="/opt/imgs",
                        help='Where to store all images and disks, full abs path')
    parser.add_argument('-z', action='store', dest='ubuntu_img_dir',
                        default="/opt/iso/trusty-server-cloudimg-amd64-disk1.img",
                        help='Where to find downloaded cloud image, full abs path')
    parser.add_argument('-o', action='store_true', dest='aio_mode', default=False,
                        help='Create only "all in one" setup')
    parser.add_argument('-x', action='store_true', dest='undefine_all', default=False,
                        help='Undefine everything with this lab_id')

    opts = parser.parse_args()
    user = opts.user
    host = opts.host
    control_servers_len = opts.controls
    compute_servers_len = opts.computes
    lab_id = opts.labid
    compute_cpus = opts.cpus
    img_path = opts.img_dir
    lab_img_path = os.path.join(img_path, lab_id)
    ubuntu_img_path = opts.ubuntu_img_dir
    aio_mode = opts.aio_mode
    conn = libvirt.open('qemu+ssh://{user}@{host}/system'.format(user=user, host=host))

    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates", "box.yaml")) as f:
        conf = yaml.load(f)
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates", "env.yaml")) as f:
        env = yaml.load(f)

    if opts.labid:
        delete_all(conn=conn, lab_id=lab_id, lab_img_path=lab_img_path, conf=conf)
        if opts.undefine_all:
            return
    else:
        print >> sys.stderr, "Please provide lab id"
        sys.exit(1)

    ip_start = env[lab_id]['ip_start']
    net_start = env[lab_id]['net_start']
    if aio_mode:
        lab_boxes = {
            "aio-servers": [],
        }
        control_servers_len = compute_servers_len = 0
    else:
        lab_boxes = {
            "compute-servers": [],
            "build-server": [],
            "control-servers": [],
        }

    ######### NETWORKS

    networks = conf['params']['networks']
    for num, net in enumerate(networks):
        net['net-ip'] = "192.168." + str(net_start + num)
        net['name'] = lab_id + "-" + net['name']
        if net['role'] == EXTERNAL_NET:
            external_net_subnet = net['net-ip']

    dhcp_hostline = '<host mac="{server_mac}" name="{server_name}.domain.name" ip="{server_ip}" />'
    dhcp_records = ''
    mac = rand_mac()
    ip = networks[0]["net-ip"] + "." + str(ip_start)
    if "build-server" in lab_boxes:
        dhcp_records = dhcp_hostline.format(
            server_mac=mac,
            server_name="build-server",
            server_ip=ip)
        lab_boxes["build-server"].append({
            "hostname": "build-server",
            "name": lab_id + "-build-server",
            "ip": ip,
            "mac": mac
            })
    if "aio-servers" in lab_boxes:
        dhcp_records = dhcp_hostline.format(
            server_mac=mac,
            server_name="all-in-one",
            server_ip=ip)
        lab_boxes["aio-servers"].append({
            "hostname": "all-in-one",
            "name": lab_id + "-aio-server",
            "ip": ip,
            "mac": mac
            })
    for i in xrange(control_servers_len):
        mac = rand_mac()
        ip = networks[0]["net-ip"] + "." + str(ip_start + i + 1)
        dhcp_records += "\n" + dhcp_hostline.format(
            server_mac=mac,
            server_name="control-server%.2d" % i,
            server_ip=ip)
        lab_boxes["control-servers"].append({
            "hostname": "control-server%.2d" % i,
            "name": lab_id + "-control-server%.2d" % i,
            "ip": ip,
            "mac": mac})
    ip_start += control_servers_len
    for i in xrange(compute_servers_len):
        mac = rand_mac()
        ip = networks[0]["net-ip"] + "." + str(ip_start + i + 1)
        dhcp_records += "\n" + dhcp_hostline.format(
            server_mac=mac,
            server_name="compute-server%.2d" % i,
            server_ip=ip)
        lab_boxes["compute-servers"].append({
            "hostname": "compute-server%.2d" % i,
            "name": lab_id + "-compute-server%.2d" % i,
            "ip": ip,
            "mac": mac})

    for net in networks:
        net_xml = net['xml'].format(name=net['name'], net_ip=net["net-ip"], dhcp_records=dhcp_records)
        net_create(conn, net_xml)

    ############ BOXES ############
    remove_all_imgs(lab_img_path)
    pool_name = "default-" + lab_id
    if opts.boot == "net":
        if pool_found(conn, pool_name):
            pool_delete(conn, pool_name)
        pool_create(conn, conf['params']['pool']['xml'].format(
            name=pool_name, path=lab_img_path))

    new_img_path = os.path.join(lab_img_path, lab_id + "-backing.img")
    convert_image(ubuntu_img_path, new_img_path)
    final_result = {"servers": None}

    # create aio server if configured
    if aio_mode:
        aio = lab_boxes['aio-servers'][0]
        yaml_config = create_host_seed_yaml(conf, box=aio, btype="aio-server")
        conf_yaml = yaml.load(yaml_config)
        disk = main_disk_create(name=aio["name"],
                                size=10,  # in GB
                                config=conf,
                                conn=conn,
                                boot_type=opts.boot,
                                img_path=lab_img_path,
                                user_seed_yaml=yaml_config,
                                img_uncomp_path=new_img_path,
                                lab_id=lab_id)
        vm_xml = conf["params"]["aio-server"]["xml"].format(
            name=aio["name"],
            ram=8*1024*1024,
            disk=disk,
            compute_server_cpu=compute_cpus,
            net_boot_name=conf["params"]["networks"][0]["name"],
            mac=aio["mac"],
            net_admin_name=conf["params"]["networks"][1]["name"],
            net_external_name=conf["params"]["networks"][4]["name"],
        )
        create_vm(conn, vm_xml)
        conn.close()
        eth_default = re.search("(eth\d+)",
                                [z for z in conf_yaml["write_files"]
                                    if 'inet static' in z['content']][0]['content']).group(1)
        eth_external = re.search("(eth\d+)",
                                 [z for z in conf_yaml["write_files"]
                                  if 'inet manual' in z['content']][0]['content']).group(1)
        default_net_subnet = re.search("network ([^\s]+)",
                                       [z for z in conf_yaml["write_files"]
                                        if 'inet static' in z['content']][0]['content']).group(1)
        final_result["servers"] = {
            "aio": {
                "ip": aio["ip"],
                "mac": aio["mac"],
                "vm_name": aio["name"],
                "user": "root",
                "password": "ubuntu",
                "external_interface": eth_external,
                "default_interface": eth_default,
                "external_net": external_net_subnet + ".0",
                "default_net": default_net_subnet,
            }
        }
        print yaml.dump(final_result)
        # workaround for tempest nets configurator
        with open("external_net", "w") as f:
            f.write(external_net_subnet)
        print >> sys.stderr, "Created AIO box", aio["name"], "with ip", aio["ip"]
        return

    # create build server
    build = lab_boxes["build-server"][0]
    yaml_config = create_host_seed_yaml(conf, box=build, btype="build-server")
    conf_yaml = yaml.load(yaml_config)
    disk = main_disk_create(name=build["name"],
                            size=10,  # in GB
                            config=conf,
                            conn=conn,
                            boot_type="cloudimg",
                            img_path=lab_img_path,
                            user_seed_yaml=yaml_config,
                            img_uncomp_path=new_img_path,
                            lab_id=lab_id)
    vm_xml = conf["params"]["build-server"]["xml"].format(
        name=lab_boxes["build-server"][0]["name"],
        ram=8*1024*1024,
        disk=disk,
        net_boot_name=conf["params"]["networks"][0]["name"],
        build_server_mac=lab_boxes["build-server"][0]["mac"],
        net_admin_name=conf["params"]["networks"][1]["name"],
        net_external_name=conf["params"]["networks"][4]["name"],
    )
    create_vm(conn, vm_xml)
    eth_external = re.search("(eth\d+)",
                                 [z for z in conf_yaml["write_files"]
                                  if 'inet manual' in z['content']][0]['content']).group(1)
    final_result["servers"] = {
        "build-server": {
            "ip": build["ip"],
            "mac": build["mac"],
            "hostname": build["hostname"],
            "vm_name": build["name"],
            "user": "root",
            "password": "ubuntu",
            "default_interface": "eth1",
            "external_interface": eth_external,
            "external_net": external_net_subnet + ".0",
        }
    }
    print >> sys.stderr, "Created build-server", lab_boxes["build-server"][0]["name"], \
        "with ip", lab_boxes["build-server"][0]["ip"]

    with open("external_net", "w") as f:
            f.write(external_net_subnet)

    ### create other servers
    for compute in lab_boxes["compute-servers"]:
        yaml_config = create_host_seed_yaml(conf, box=compute, btype="compute-server")
        disk = main_disk_create(name=compute["name"],
                                size=10,  # in GB
                                config=conf,
                                conn=conn,
                                boot_type=opts.boot,
                                img_path=lab_img_path,
                                user_seed_yaml=yaml_config,
                                img_uncomp_path=new_img_path,
                                lab_id=lab_id)
        vm_xml = conf["params"]["compute-server"]["xml"].format(
            name=compute["name"],
            ram=4*1024*1024,
            disk=disk,
            compute_server_cpu=compute_cpus,
            net_boot_name=conf["params"]["networks"][0]["name"],
            mac=compute["mac"],
            net_admin_name=conf["params"]["networks"][1]["name"],
            net_public_name=conf["params"]["networks"][2]["name"],
            net_internal_name=conf["params"]["networks"][3]["name"],
            net_external_name=conf["params"]["networks"][4]["name"],
        )
        create_vm(conn, vm_xml)
        compute_box_config = {
            "ip": compute["ip"],
            "mac": compute["mac"],
            "hostname": compute["hostname"],
            "vm_name": compute["name"],
            "user": "root",
            "password": "ubuntu",
            "admin_interface": "eth1",
            "public_interface": "eth2",
            "internal_interface": "eth3",
            "external_interface": "eth4",
        }
        if "compute-servers" in final_result["servers"]:
            final_result["servers"]["compute-servers"].append(compute_box_config)
        else:
            final_result["servers"]["compute-servers"] = [compute_box_config]
        print >> sys.stderr, "Created compute-server", compute["name"], "with ip", compute["ip"]

    for control in lab_boxes["control-servers"]:
        yaml_config = create_host_seed_yaml(conf, box=control, btype="control-server")
        disk = main_disk_create(
                                name=control["name"],
                                size=10,
                                config=conf,
                                conn=conn,
                                boot_type=opts.boot,
                                img_path=lab_img_path,
                                user_seed_yaml=yaml_config,
                                img_uncomp_path=new_img_path,
                                lab_id=lab_id)
        vm_xml = conf["params"]["control-server"]["xml"].format(
            name=control["name"],
            ram=4*1024*1024,
            disk=disk,
            compute_server_cpu=compute_cpus,
            net_boot_name=conf["params"]["networks"][0]["name"],
            mac=control["mac"],
            net_admin_name=conf["params"]["networks"][1]["name"],
            net_public_name=conf["params"]["networks"][2]["name"],
            net_internal_name=conf["params"]["networks"][3]["name"],
            net_external_name=conf["params"]["networks"][4]["name"],
        )
        create_vm(conn, vm_xml)
        control_box_config = {
            "ip": control["ip"],
            "mac": control["mac"],
            "hostname": control["hostname"],
            "vm_name": control["name"],
            "user": "root",
            "password": "ubuntu",
            "admin_interface": "eth1",
            "public_interface": "eth2",
            "internal_interface": "eth3",
            "external_interface": "eth4",
        }
        if "control-servers" in final_result["servers"]:
            final_result["servers"]["control-servers"].append(control_box_config)
        else:
            final_result["servers"]["control-servers"] = [control_box_config]
        print >> sys.stderr, "Created control-server", control["name"], "with ip", control["ip"]
    print yaml.dump(final_result)
    conn.close()


if __name__ == "__main__":
    main()
