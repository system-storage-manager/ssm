#!/usr/bin/env python
#
# (C)2011 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# crypt module for System Storage Manager

import re
import os
from ssmlib import misc
from ssmlib import problem

__all__ = ["DmCryptVolume"]

try:
    SSM_CRYPT_DEFAULT_POOL = os.environ['SSM_CRYPT_DEFAULT_POOL']
except KeyError:
    SSM_CRYPT_DEFAULT_POOL = "crypt_pool"

try:
    DM_DEV_DIR = os.environ['DM_DEV_DIR']
except KeyError:
    DM_DEV_DIR = "/dev"


class DmCryptVolume(object):

    def __init__(self, options, data=None):
        self.type = 'crypt'
        self.data = data or {}
        self.output = None
        self.options = options
        self.mounts = misc.get_mounts('{0}/mapper'.format(DM_DEV_DIR))
        self.default_pool_name = SSM_CRYPT_DEFAULT_POOL
        self.problem = problem.ProblemSet(options)

        if not misc.check_binary('dmsetup') or \
           not misc.check_binary('cryptsetup'):
            return
        command = ['dmsetup', 'table']
        self.output = misc.run(command, stderr=False)[1]
        for line in self.output.split("\n"):
            if not line or line == "No devices found":
                break
            dm = {}
            array = line.split()
            dm['type'] = array[3]
            if dm['type'] != 'crypt':
                continue
            dm['vol_size'] = str(int(array[2]) / 2.0)
            devname = re.sub(":$", "",
                             "{0}/mapper/{1}".format(DM_DEV_DIR, array[0]))
            dm['dm_name'] = devname
            dm['pool_name'] = 'dm-crypt'
            dm['dev_name'] = misc.get_real_device(devname)
            dm['real_dev'] = dm['dev_name']
            if dm['real_dev'] in self.mounts:
                dm['mount'] = self.mounts[dm['real_dev']]['mp']

            # Check if the device really exists in the system. In some cases
            # (tests) DM_DEV_DIR can lie to us, if that is the case, simple
            # ignore the device.
            if not os.path.exists(devname):
                continue
            command = ['cryptsetup', 'status', devname]
            self._parse_cryptsetup(command, dm)
            self.data[dm['dev_name']] = dm

    def run_cryptsetup(self, command, stdout=True):
        if not misc.check_binary('cryptsetup'):
            self.problem.check(self.problem.TOOL_MISSING, 'cryptsetup')
        command.insert(0, "cryptsetup")
        return misc.run(command, stdout=stdout)

    def _parse_cryptsetup(self, cmd, dm):
        self.output = misc.run(cmd, stderr=False)[1]
        for line in self.output.split("\n"):
            if not line:
                break
            array = line.split()
            if array[0].strip() == 'cipher:':
                dm['cipher'] = array[1]
            elif array[0].strip() == 'keysize:':
                dm['keysize'] = array[1]
            elif array[0].strip() == 'device:':
                dm['crypt_device'] = array[1]

    def remove(self, dm):
        command = ['remove', dm]
        self.run_cryptsetup(command)

    def resize(self, dm, size, resize_fs=True):
        size = str(int(size) * 2)
        command = ['resize', '--size', size, dm]
        self.run_cryptsetup(command)

    def __iter__(self):
        for item in sorted(self.data.iterkeys()):
            yield item

    def __getitem__(self, key):
        if key in self.data.iterkeys():
            return self.data[key]
