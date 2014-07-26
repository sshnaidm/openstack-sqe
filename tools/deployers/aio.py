from deploy import Standalone

__author__ = 'sshnaidm'


class AIO(Standalone):
    def __init__(self, *args):
        super(AIO, self).__init__(*args)
        self.env = {"vendor": "cisco",
                    "scenario": "all_in_one"}
        self.scenario = "all_in_one"
        self.aio = None
        if self.conf_yaml:
            self.aio = self.conf_yaml['servers']['aio-server'][0]

    def parse_file(self):
        self.host = self.aio["ip"]
        self.user = self.conf.user or self.aio["user"]
        self.password = self.conf.password or self.aio["password"]

    def env_update(self):
        if self.conf_yaml:
            self.env.update({
                "default_interface": self.aio["internal_interface"],
                "external_interface": self.aio["external_interface"]})
        else:
            self.env.update({
                "default_interface": self.conf.default_interface,
                "external_interface": self.conf.external_interface
            })
