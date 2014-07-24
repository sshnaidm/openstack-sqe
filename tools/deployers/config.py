import argparse
import os
import yaml


DOMAIN_NAME = "domain.name"
APPLY_LIMIT = 3
CONFIG_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../libvirt-scripts", "templates")




class ConfigError(Exception):
    pass


__author__ = 'sshnaidm'


parser = argparse.ArgumentParser()
parser.add_argument('-u', action='store', dest='user',
                    help='User to run the script with')
parser.add_argument('-p', action='store', dest='password',
                    help='Password for user and sudo')
parser.add_argument('-a', action='store', dest='aio_ip', default=None,
                    help='IP of host in case of AIO setup')
parser.add_argument('-g', action='store', dest='gateway', default=None,
                    help='Gateway to connect to host')
parser.add_argument('-q', action='store_true', default=False, dest='quiet',
                    help='Make all silently')
parser.add_argument('-k', action='store', dest='ssh_key_file', default=None,
                    help='SSH key file, default is from repo')
parser.add_argument('-e', action='store_true', dest='use_cobbler', default=False,
                    help='Use cobbler for deploying control and compute nodes')
parser.add_argument('-f', action='store_true', dest='force', default=False,
                    help='Force SSH client run. Use it if dont work in AIO setup only.')
parser.add_argument('-w', action='store_true', dest='only_build', default=False,
                    help='Configure only build server')
parser.add_argument('-j', action='store_true', dest='proxy', default=False,
                    help='Use cisco proxy if installing from Cisco local network')
parser.add_argument('-c', action='store', dest='config_file', default=None, type=argparse.FileType('r'),
                    help='Configuration file, default is None')
parser.add_argument('-s', action='store', dest='scenario', default="all-in-one",
                    choices=["all-in-one", "2role", "fullha", "devstack"],
                    help="Scenario to deploy. By default it's AIO")
parser.add_argument('-x', action='store', default="eth1", dest='external_interface',
                    help='External interface: eth0, eth1... default=eth1')
parser.add_argument('-y', action='store', default="eth0", dest='default_interface',
                    help='Default interface: eth0, eth1... default=eth0')
parser.add_argument('-m', action='store_true', default=False, dest='patch',
                    help='If apply patches in Devstack scenario')

parser.add_argument('--version', action='version', version='%(prog)s 2.0')

opts = parser.parse_args()
if opts.quiet:
        verb_mode = ['output', 'running', 'warnings']
else:
    verb_mode = []
path2ssh = os.path.join(os.path.dirname(__file__), "..", "libvirt-scripts", "id_rsa")
ssh_key_file = opts.ssh_key_file if opts.ssh_key_file else path2ssh
if not opts.config_file and opts.scenario not in ("all-in-one", "devstack"):
    raise ConfigError("Config file is requried if not AIO scenario or devstack")
if opts.config_file:
    try:
        opts.config_file = yaml.load(opts.config_file)
    except Exception as e:
        raise ConfigError("Config file is not of YAML format!\n%s" % str(e))
