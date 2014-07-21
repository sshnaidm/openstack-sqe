__author__ = 'sshnaidm'

from common import install_openstack
import yaml

class Standalone:
    def __init__(self, conf, ssh_key, verb):
        self.conf = conf
        self.ssh_key = ssh_key
        self.verb = verb
        self.env = {}
        self.host = None
        self.user = None
        self.password = None
        self.conf_yaml = None
        self.scenario = None
        self.job = None
        if self.conf.config_file:
            self.conf_yaml = yaml.load(self.conf.config_file)

    def create_config(self):
        self.host = self.conf.host
        self.user = self.conf.user
        self.password = self.conf.password

    def parse_file(self):
        pass

    def env_update(self):
        pass

    def prerun(self):
        if self.conf_yaml:
            self.parse_file()
        else:
            self.create_config()
        self.env_update()
        self.job = {
            "host_string": self.host,
            "user": self.user,
            "password": self.password,
            "warn_only": True,
            "key_filename": self.ssh_key,
            "abort_on_prompts": True,
            "gateway": self.conf.gateway
        }

    def run_installer(self):
        install_openstack(self.job, self.env, self.verb, self.conf.force, self.conf_yaml, self.conf.use_cobbler,
                          self.conf.proxy, self.scenario)

    def postrun(self):
        pass

    def run(self):
        self.prerun()
        self.run_installer()
        self.postrun()
