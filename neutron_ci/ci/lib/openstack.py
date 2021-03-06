import os
import re
from heatclient.v1.client import Client as HeatClient
from keystoneclient.v2_0.client import Client as KeystoneClient
from glanceclient.v2.client import Client as GlanceClient
from glanceclient.common import utils as glance_utils
from ci.lib import utils


class OpenStack(object):

    def __init__(self, auth_url, username, password, tenant_name):
        self.credentials = {
            'auth_url': auth_url,
            'username': username,
            'password': password,
            'tenant_name': tenant_name
        }

        self._heat_client = None
        self._keystone_client = None
        self._glance_client = None

    @property
    def heat(self):
        if not self._heat_client:
            endpoints = self.keystone.service_catalog.get_endpoints()
            endpoint = endpoints['orchestration'][0]['publicURL']
            self._heat_client = HeatClient(endpoint, **self.credentials)
        return self._heat_client

    @property
    def glance(self):
        if not self._glance_client:
            endpoints = self.keystone.service_catalog.get_endpoints()
            endpoint = endpoints['image'][0]['publicURL']
            self._glance_client = GlanceClient(endpoint, **self.credentials)
        return self._glance_client

    @property
    def keystone(self):
        if not self._keystone_client:
            self._keystone_client = KeystoneClient(**self.credentials)
            self.credentials.update(
                {'token': self._keystone_client.auth_token})
        return self._keystone_client

    def launch_stack(self, name, template_path, parameters):
        with open(template_path) as f:
            template = f.read()
            stack = self.heat.stacks.create(**{
                'stack_name': name,
                'template': template,
                'parameters': parameters
            })['stack']
            get_the_stack = lambda: self.heat.stacks.get(stack['id'])
            utils.wait_until(
                lambda: get_the_stack().status == 'CREATE_COMPLETE')
            stack = get_the_stack()
            return (stack, {o['output_key']: o['output_value']
                            for o in stack.outputs})

    def find_image(self, name_regexp):
        pattern = re.compile(name_regexp)
        for img in self.glance.images.list():
            if pattern.match(img['name']):
                return img

    def download_image(self, image, path):
        temp_path = path + '.tmp'
        body = self.glance.images.data(image['id'])
        glance_utils.save_image(body, temp_path)
        os.rename(temp_path, path)
