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
        # Convert all parts of cmd into string
        for i, item in enumerate(cmd):
            if not isinstance(item, str):
                cmd[i] = str(item)

        self.run_data.append(" ".join(cmd))
        output = ""
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output, None)

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
        self.get_real_device_orig = misc.get_real_device
        misc.get_real_device = self.mock_get_real_device
        self.get_device_size_orig = misc.get_device_size
        misc.get_device_size = self.mock_get_device_size
        self.is_bdevice_orig = misc.is_bdevice
        misc.is_bdevice = self.mock_is_bdevice
        self.is_directory_orig = main.is_directory
        main.is_directory = self.mock_is_directory
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
        self.get_fs_type_orig = misc.get_fs_type
        misc.get_fs_type = self.mock_get_fs_type
        self.create_directory = main.create_directory
        main.create_directory = self.mock_create_directory
        self.main_os_statvfs = main.os.statvfs
        main.os.statvfs = self.mock_os_statvfs
        self.dev_data = {}
        self.vol_data = {}
        self.pool_data = {}
        self.mount_data = {}
        self.links = {}
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
        misc.get_real_device = self.get_real_device_orig
        misc.get_device_size = self.get_device_size_orig
        misc.is_bdevice = self.is_bdevice_orig
        main.is_directory = self.is_directory_orig
        misc.get_mounts = self.get_mounts_orig
        main.StorageHandle.check_create_item = self.check_create_item_orig
        misc.temp_mount = self.temp_mount_orig
        misc.check_binary = self.check_binary_orig
        misc.send_udev_event = self.send_udev_event_orig
        misc.get_fs_type = self.get_fs_type_orig
        main.SSM_NONINTERACTIVE = False

    def _cmdEq(self, expected, index=-1, expected_args=None):
        """ Note: Permutated arguments are joined 'as is', so if you want a
            space as a delimiter, it has to be part of the string
        """
        if expected_args:
            arg_permutations = list(misc.permutations(expected_args))
            args = None
            # Test cmdEq twice - once for reporting when we found
            # the equal permutation, and once at the end, if we
            # did not found any equal permutation to raise a failure.
            for arg in arg_permutations:
                args = "".join(arg).strip()
                if self.run_data[index] == expected + args:
                    self.assertEqual(self.run_data[index], expected + args)
                    return
            self.assertEqual(self.run_data[index], expected + args)
        else:
            self.assertEqual(self.run_data[index], expected)

    def _cmdNotEq(self, expected, index=-1, expected_args=None):
        """ Note: Permutated arguments are joined 'as is', so if you want a
            space as a delimiter, it has to be part of the string
        """
        if expected_args:
            arg_permutations = list(misc.permutations(expected_args))
            args = None
            # Test cmdEq twice - once for reporting when we found
            # the equal permutation to raise a failure, and once
            # at the end, if we did not found any equal permutation.
            for arg in arg_permutations:
                args = "".join(arg).strip()
                if self.run_data[-1] == expected + args:
                    self.assertNotEqual(self.run_data[index], expected + args)
                    return
                self.assertNotEqual(self.run_data[index], expected + args)
        else:
            self.assertNotEqual(self.run_data[index], expected)


    def _checkCmd(self, command, args, expected=None, NotEq=False, expected_args=None):
        """ Note: Permutated arguments are joined 'as is', so if you want a
            space as a delimiter, it has to be part of the string
        """
        self.run_data = []
        for case in misc.permutations(args):
            cmd = command + " " + " ".join(case)
            main.main(cmd)
            if expected:
                if NotEq:
                    self._cmdNotEq(expected, -1, expected_args)
                else:
                    self._cmdEq(expected, -1, expected_args)


    def mock_run(self, cmd, *args, **kwargs):
        self.run_data.append(" ".join(cmd))
        output = ""
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output)

    def mock_check_binary(self, name):
        return True

    def mock_os_statvfs(self, mountpoint):
        # keep the exception here - we do not need real data for now,
        # we need to only find out if this mock function was called,
        # and an exception works for that well.
        raise NotImplementedError("mock data not needed")

    def mock_temp_mount(self, device, options=None):
        return "/tmp/mount"

    def mock_get_partitions(self):
        partitions = []
        for (_, data) in self.dev_data.items():
            partitions.append([data['major'], data['minor'], data['dev_size'],
                               data['dev_name'], data['dev_name']])
        return partitions

    def mock_get_real_device(self, devname):
        for (dev, _) in self.dev_data.items():
            if dev == devname:
                return dev
        for name, target in self.links.items():
            if name == devname:
                return self.mock_get_real_device(target)
        return devname

    def mock_get_device_size(self, device):
        return self.dev_data[device]['dev_size']

    def mock_is_directory(self, string):
        if string in self.directories:
            return string
        else:
            err = "'{0}' does not exist.".format(string)
            raise argparse.ArgumentTypeError(err)

    def mock_get_mounts(self, regex=None):
        return self.mount_data

    def mock_is_bdevice(self, path):
        if path in self.dev_data:
            return path
        err = "'{0}' is not valid block device".format(path)
        raise argparse.ArgumentTypeError(err)

    def mock_check_create_item(self, path):
        if not self._mpoint:
            if path in self.directories:
                self._mpoint = path
                return
        return misc.is_bdevice(path)

    def mock_get_fs_type(self, device):
        if device in self.vol_data:
            if 'fstype' in self.vol_data[device]:
                return self.vol_data[device]['fstype']
            return None
        elif device in self.dev_data:
            if 'fstype' in self.dev_data[device]:
                return self.dev_data[device]['fstype']
            return None
        return None

    def mock_send_udev_event(self, device, event):
        pass

    def mock_create_directory(self, string):
        pass

    def _removeMount(self, device):
        del self.mount_data[device]

    def _addDir(self, dirname):
        self.directories.append(dirname)

    def _addLink(self, target, name):
        self.links[name] = target

    def _addDevice(self, dev_name, dev_size, minor=0):
        self.dev_data[dev_name] = {
            'dev_name': dev_name,
            'dev_size': dev_size,
            'major': '8',
            'minor': str(minor)
        }

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
        self.pool_data[pool_name] = {
            'pool_name': pool_name,
            'pool_size': str(pool_size),
            'pool_used': str(pool_used),
            'dev_count': str(dev_count),
            'pool_free': str(pool_free),
            'vol_count': '0'
        }

    def _mountVol(self, vol_name, pool_name, devices, mount):
        """ Mount a volume created with _addVol. Use the same argumets as for
            _addVol.
        """
        vol_path = "/dev/{0}/{1}".format(pool_name, vol_name)
        real_dev = self.vol_data[vol_path]['real_dev']
        self.vol_data[vol_path]['mount'] = mount
        self.pool_data[pool_name]['mount'] =  mount
        self._addDir(mount)
        self.mount_data[devices[0]] = {'dev': devices[0], 'mp': mount,
                                        'root': "/"}
        self.mount_data[vol_path] = {'dev': vol_path, 'mp': mount,
                                        'root': "/"}
        self.mount_data[real_dev] = {'dev': real_dev, 'mp': mount,
                                        'root': "/"}

    def _addVol(self, vol_name, vol_size, stripes, pool_name, devices,
                mount=None, active=True, fstype=None):
        pool_data = self.pool_data[pool_name]
        pool_free = float(pool_data['pool_free']) - vol_size
        pool_used = float(pool_data['pool_used']) + vol_size
        pool_data['pool_free'] = pool_free
        pool_data['pool_used'] = pool_used

        space_per_dev = vol_size // stripes

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
        vol_path = "/dev/{0}/{1}".format(pool_name, vol_name)
        attr = "-wi------"
        if active:
            tmp = list(attr)
            tmp[4] = 'a'
            attr = "".join(tmp)
        self.vol_data[vol_path] = {
            'dm_name': vol_path,
            'real_dev': vol_path,
            'stripes': stripes,
            'dev_name': vol_path,
            'stripesize': 0,
            'pool_name': pool_name,
            'vol_size': vol_size,
            'dev_size': vol_size,
            'type': vol_type,
            'origin': "",
            'mount': None,
            'attr': attr
        }
        if fstype:
            self.vol_data[vol_path]['fstype'] = fstype
        if mount:
            self._mountVol(vol_name, pool_name, devices, mount)
