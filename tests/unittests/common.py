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

# Common classes for unit testing

import os
import sys
import unittest
import argparse
from ssmlib import main
from ssmlib import misc


class MyStdout(object):
    def __init__(self):
        self.output = ""
        self.stdout = sys.stdout

    def write(self, s):
        self.output += s


class BaseStorageHandleInit(unittest.TestCase):
    """
    Initialize StorageHandle class and some mock functions.
    """

    def setUp(self):
        self.storage = main.StorageHandle()
        self.run_data = []
        self.run_orig = misc.run
        misc.run = self.mock_run
        main.SSM_NONINTERACTIVE = True

    def mock_run(self, cmd, *args, **kwargs):
        self.run_data.append(" ".join(cmd))
        output = ""
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output)

    def tearDown(self):
        self.storage = None
        self.run_data = []
        misc.run = self.run_orig
        main.SSM_NONINTERACTIVE = False


class MockSystemDataSource(unittest.TestCase):
    def setUp(self):
        self.directories = []
        self.run_data = []
        self.run_orig = misc.run
        misc.run = self.mock_run
        self.get_partitions_orig = misc.get_partitions
        misc.get_partitions = self.mock_get_partitions
        self.is_bdevice_orig = main.is_bdevice
        main.is_bdevice = self.mock_is_bdevice
        self.check_create_item_orig = main.StorageHandle.check_create_item
        main.StorageHandle.check_create_item = self.mock_check_create_item
        self.get_mounts_orig = misc.get_mounts
        misc.get_mounts = self.mock_get_mounts
        self.temp_mount_orig = misc.temp_mount
        misc.temp_mount = self.mock_temp_mount
        self.check_binary_orig = misc.check_binary
        misc.check_binary = self.mock_check_binary
        self.send_udev_event_orig = misc.send_udev_event
        misc.send_udev_event = self.mock_send_udev_event
        self.dev_data = {}
        self.vol_data = {}
        self.pool_data = {}
        self.mount_data = {}
        self._mpoint = False
        main.SSM_NONINTERACTIVE = True

    def tearDown(self):
        self.directories = []
        self.run_data = []
        self.dev_data = {}
        self.pool_data = {}
        self.vol_data = {}
        self.mount_data = {}
        misc.run = self.run_orig
        misc.get_partitions = self.get_partitions_orig
        main.is_bdevice = self.is_bdevice_orig
        misc.get_mounts = self.get_mounts_orig
        main.StorageHandle.check_create_item = self.check_create_item_orig
        misc.temp_mount = self.temp_mount_orig
        misc.check_binary = self.check_binary_orig
        misc.send_udev_event = self.send_udev_event_orig
        main.SSM_NONINTERACTIVE = False

    def _cmdEq(self, out, index=-1):
        self.assertEqual(self.run_data[index], out)

    def _checkCmd(self, command, args, expected=None):
        self.run_data = []
        for case in misc.permutations(args):
            cmd = command + " " + " ".join(case)
            main.main(cmd)
            if expected:
                self._cmdEq(expected)

    def mock_run(self, cmd, *args, **kwargs):
        self.run_data.append(" ".join(cmd))
        output = ""
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output)

    def mock_check_binary(self, name):
        return True

    def mock_temp_mount(self, device, options=None):
        return "/tmp/mount"

    def mock_get_partitions(self):
        partitions = []
        for name, data in self.dev_data.iteritems():
            partitions.append([data['major'], data['minor'], data['dev_size'],
                              data['dev_name'].rpartition("/")[2]])
        return partitions

    def mock_get_mounts(self, regex=None):
        return self.mount_data

    def mock_is_bdevice(self, path):
        if path in self.dev_data:
            return path
        else:
            err = "'{0}' is not valid block device".format(path)
            raise argparse.ArgumentTypeError(err)

    def mock_check_create_item(self, path):
        if not self._mpoint:
            if path in self.directories:
                self._mpoint = path
                return
        return main.is_bdevice(path)

    def mock_send_udev_event(self, device, event):
        pass

    def _removeMount(self, device):
        del self.mount_data[device]

    def _addDir(self, dirname):
        self.directories.append(dirname)

    def _addDevice(self, dev_name, dev_size, minor=0):
        self.dev_data[dev_name] = {'dev_name': dev_name, 'dev_size': dev_size,
                'major': '8', 'minor': str(minor)}

    def _addPool(self, pool_name, devices):
        if pool_name in self.pool_data:
            pool_data = self.pool_data[pool_name]
            pool_size = float(pool_data['pool_size'])
            pool_free = float(pool_data['pool_free'])
            pool_used = float(pool_data['pool_used'])
            dev_count = int(pool_data['dev_count'])
        else:
            pool_size = pool_free = pool_used = 0.0
            dev_count = 0

        for dev in devices:
            dev_data = self.dev_data[dev]
            pool_size += float(dev_data['dev_size'])
            pool_free += float(dev_data['dev_size'])
            dev_data['pool_name'] = str(pool_name)
            dev_data['dev_free'] = dev_data['dev_size']
            dev_data['dev_used'] = '0.0'

        dev_count += len(devices)
        self.pool_data[pool_name] = {'pool_name': pool_name,
                'pool_size': str(pool_size), 'pool_used': str(pool_used),
                'dev_count': str(dev_count), 'pool_free': str(pool_size),
                'vol_count': '0'}

    def _addVol(self, vol_name, vol_size, stripes, pool_name, devices,
                mount=None):
        pool_data = self.pool_data[pool_name]
        pool_free = float(pool_data['pool_free']) - vol_size
        pool_used = float(pool_data['pool_used']) + vol_size
        if mount:
            self.pool_data[pool_name]['mount'] = mount
            self._addDir(mount)
            self.mount_data[devices[0]] = {'dev': devices[0], 'mp': mount}

        space_per_dev = vol_size / stripes

        size = vol_size
        for dev in devices:
            dev_data = self.dev_data[dev]
            if 'dev_free' not in dev_data:
                self._addPool(pool_name, [dev])
            if stripes > 1:
                dev_data['pool_name'] = pool_name
                dev_data['dev_used'] = str(float(dev_data['dev_used']) +
                                                space_per_dev)
                dev_data['dev_free'] = str(float(dev_data['dev_free']) -
                                                space_per_dev)
                size -= space_per_dev
            else:
                dev_data['pool_name'] = pool_name
                if size > float(dev_data['dev_size']):
                    use = float(dev_data['dev_size'])
                else:
                    use = size
                dev_data['dev_used'] = str(float(dev_data['dev_used']) +
                                                space_per_dev)
                dev_data['dev_free'] = str(float(dev_data['dev_free']) -
                                                 space_per_dev)
                size -= use
        if size > 1:
            raise Exception("Error in the test in _addVol")
        if stripes > 1:
            vol_type = "striped"
            stripesize = 32
        else:
            vol_type = "linear"
            stripesize = 0
        vol_name = "/dev/{0}/{1}".format(pool_name, vol_name)
        self.vol_data[vol_name] = {'dm_name': vol_name,
                'real_dev': vol_name, 'stripes': stripes, 'dev_name': vol_name,
                'stripesize': 0, 'pool_name': pool_name, 'vol_size': vol_size,
                'dev_size': vol_size, 'type': vol_type, 'origin': "",
                'mount': mount}
