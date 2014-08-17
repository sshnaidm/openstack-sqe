# Copyright 2014 Cisco Systems, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Dane LeBlanc, Nikolay Fedotov, Cisco Systems, Inc.

import socket
import netifaces


class Node(object):

    def __init__(self, default_nic='eth0'):
        self._default_nic = default_nic

    @property
    def hostname(self):
        return socket.gethostname()

    @property
    def ip(self):
        ips = netifaces.ifaddresses(self._default_nic)
        return ips[netifaces.AF_INET][0]['addr']
