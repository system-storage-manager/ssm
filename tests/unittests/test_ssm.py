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

# Unittests for the system storage manager

import os
import re
import sys
import stat
import time
import doctest
import unittest
import argparse
from ssmlib import main
from ssmlib import misc
from ssmlib import problem

from tests.unittests.common import *

class SimpleStorageHandleSanityCheck(BaseStorageHandleInit):
    """
    Simple sanity checks for StorageHandle class and some of its methods.
    """

    def test_constructor(self):
        # Check initial variables
        self.assertFalse(self.storage.options.force)
        self.assertFalse(self.storage.options.verbose)
        self.assertFalse(self.storage.options.yes)
        self.assertFalse(self.storage.options.interactive)
        self.assertFalse(self.storage.options.debug)
        self.assert_(self.storage.options.config is None)
        self.assert_(self.storage._mpoint is None)
        self.assert_(self.storage._dev is None)
        self.assert_(self.storage._pool is None)
        self.assert_(self.storage._volumes is None)

    def test_create_fs(self):
        options = main.Options()
        for fs in main.EXTN:
            options.force = True
            options.verbose = True
            options.yes = False
            options.config = "my_new_config"
            options.interactive = False
            self.storage.set_globals(options)
            self.storage._create_fs(fs, "/dev/foo/bar")
            self.assertEqual('mkfs.{0} -v -F /dev/foo/bar'.format(fs),
                    self.run_data[-1])
            options.force = False
            options.verbose = False
            self.storage.set_globals(options)
            self.storage._create_fs(fs, "/dev/foo/bar")
            self.assertEqual('mkfs.{0} /dev/foo/bar'.format(fs),
                    self.run_data[-1])
            options.force = True
            self.storage.set_globals(options)
            self.storage._create_fs(fs, "/dev/foo/bar")
            self.assertEqual('mkfs.{0} -F /dev/foo/bar'.format(fs),
                    self.run_data[-1])
            options.force = False
            options.verbose = True
            self.storage.set_globals(options)
            self.storage._create_fs(fs, "/dev/foo/bar")
            self.assertEqual('mkfs.{0} -v /dev/foo/bar'.format(fs),
                    self.run_data[-1])
        options.force = True
        options.verbose = True
        self.storage.set_globals(options)
        self.storage._create_fs("xfs", "/dev/foo/bar")
        self.assertEqual('mkfs.xfs -f /dev/foo/bar', self.run_data[-1])
        options.force = False
        options.verbose = False
        self.storage.set_globals(options)
        self.storage._create_fs("xfs", "/dev/foo/bar")
        self.assertEqual('mkfs.xfs /dev/foo/bar', self.run_data[-1])
        options.force = True
        self.storage.set_globals(options)
        self.storage._create_fs("xfs", "/dev/foo/bar")
        self.assertEqual('mkfs.xfs -f /dev/foo/bar', self.run_data[-1])
        options.force = False
        options.verbose = True
        self.storage.set_globals(options)
        self.storage._create_fs("xfs", "/dev/foo/bar")
        self.assertEqual('mkfs.xfs /dev/foo/bar', self.run_data[-1])


class StorageHandleSanityCheck(BaseStorageHandleInit):
    """
    Sanity checks for StorageHandle class and other classes used via
    StorageHandle class.
    """

    def setUp(self):
        super(StorageHandleSanityCheck, self).setUp()
        options = main.Options()
        options.force = True
        options.verbose = True
        options.yes = True
        options.config = "my_config"
        options.interactive = True
        options.debug = True
        self.storage.set_globals(options)
        self.dev = self.storage.dev
        self.vol = self.storage.vol
        self.pool = self.storage.pool

    def tearDown(self):
        super(StorageHandleSanityCheck, self).tearDown()
        self.dev = None
        self.vol = None
        self.pool = None

    def test_storage_constructor(self):
        # Check initial variables
        self.assertTrue(self.storage.options.force)
        self.assertTrue(self.storage.options.verbose)
        self.assertTrue(self.storage.options.yes)
        self.assertTrue(self.storage.options.interactive)
        self.assertTrue(self.storage.options.debug)
        self.assertEqual(self.storage.options.config, "my_config")

        # Check if we have right instances
        self.assert_(isinstance(self.dev, main.Devices))
        self.assert_(isinstance(self.vol, main.Volumes))
        self.assert_(isinstance(self.pool, main.Pool))

        # Check initial variables
        for source in self.dev, self.vol, self.pool:
            self.assertTrue(source.options.force)
            self.assertTrue(source.options.verbose)
            self.assertTrue(source.options.yes)
            self.assertTrue(source.options.interactive)
            self.assertTrue(source.options.debug)
            self.assertEqual(source.options.config, "my_config")
            self.assert_(isinstance(source._data, dict))
            self.assert_(len(source._data) >  0)
            self.assert_(isinstance(source.header, list))
            self.assert_(len(source.header) >  0)
            self.assert_(isinstance(source.attrs, list))
            self.assert_(len(source.attrs) >  0)
            self.assert_(isinstance(source.types, list))
            self.assert_(len(source.types) >  0)
            for item  in source._data.values():
                self.assertTrue(item.options.force)
                self.assertTrue(item.options.verbose)
                self.assertTrue(item.options.yes)
                self.assertTrue(item.options.interactive)
                self.assertTrue(item.options.debug)
                self.assertEqual(item.options.config, "my_config")

    def test_set_globals_propagation(self):
        options = main.Options()
        options.force = False
        options.verbose = False
        options.yes = False
        options.config = "my_config"
        options.interactive = False
        options.debug = False
        self.storage.set_globals(options)
        # Check initial variables
        self.assertFalse(self.storage.options.force)
        self.assertFalse(self.storage.options.verbose)
        self.assertFalse(self.storage.options.yes)
        self.assertEqual(self.storage.options.config, "my_config")
        self.assertFalse(self.storage.options.interactive)
        self.assertFalse(self.storage.options.debug)

        # Check initial variables
        for source in self.dev, self.vol, self.pool:
            self.assertFalse(source.options.force)
            self.assertFalse(source.options.verbose)
            self.assertFalse(source.options.yes)
            self.assertFalse(source.options.interactive)
            self.assertFalse(source.options.debug)
            self.assertEqual(source.options.config, "my_config")
            self.assert_(isinstance(source._data, dict))
            self.assert_(len(source._data) > 0)
            self.assert_(isinstance(source.header, list))
            self.assert_(len(source.header) > 0)
            self.assert_(isinstance(source.attrs, list))
            self.assert_(len(source.attrs) > 0)
            self.assert_(isinstance(source.types, list))
            self.assert_(len(source.types) > 0)
            for item  in source._data.values():
                self.assertFalse(item.options.force)
                self.assertFalse(item.options.verbose)
                self.assertFalse(item.options.yes)
                self.assertFalse(item.options.interactive)
                self.assertFalse(item.options.debug)
                self.assertEqual(item.options.config, "my_config")

    def test_backend_generic_methods(self):
        for source in self.dev, self.vol, self.pool:
            obj = dir(source)
            self.assert_("__iter__" in obj)
            self.assert_("__contains__" in obj)
            self.assert_("__getitem__" in obj)
            self.assert_("filesystems" in obj)
            self.assert_("psummary" in obj)
            self.assert_("set_globals" in obj)
            # Variables
            self.assert_("_data" in obj)
            self.assert_("header" in obj)
            self.assert_("attrs" in obj)
            self.assert_("types" in obj)
            for bknd in source._data.values():
                obj = dir(bknd)
                self.assert_("__iter__" in obj)
                self.assert_("__getitem__" in obj)
                self.assert_("__init__" in obj)
                # Variables
                self.assert_("type" in obj)
                self.assert_("options" in obj)
                # DeviceInfo does not need default_pool_name
                if bknd.type != "device":
                    self.assert_("default_pool_name" in obj)

    def test_volumes_specific_methods(self):
        for bknd in self.vol._data.values():
            obj = dir(bknd)
            self.assert_("remove" in obj)

    def test_pool_specific_methods(self):
        for bknd in self.pool._data.values():
            obj = dir(bknd)
            self.assert_("reduce" in obj)
            self.assert_("remove" in obj)
            self.assert_("create" in obj)
            self.assert_("new" in obj)
            self.assert_("extend" in obj)


class SimpleSsmSanityCheck(unittest.TestCase):
    """
    Simple sanity check of ssm module.
    """

    def test_existing_objects(self):
        obj = dir(main)
        self.assert_("StorageHandle" in obj)
        self.assert_("FsInfo" in obj)
        self.assert_("DeviceInfo" in obj)
        self.assert_("SUPPORTED_FS" in obj)
        self.assert_("DEFAULT_DEVICE_POOL" in obj)
        self.assert_("Storage" in obj)
        self.assert_("Pool" in obj)
        self.assert_("Devices" in obj)
        self.assert_("Volumes" in obj)

    def test_fsinfo_methods(self):
        obj = dir(main.FsInfo)
        self.assert_("extN_get_info" in obj)
        self.assert_("extN_fsck" in obj)
        for fs in set(main.SUPPORTED_FS) - set(main.EXTN):
            if fs == 'btrfs':
                continue
            self.assert_("{0}_get_info".format(fs) in obj)
            self.assert_("{0}_fsck".format(fs) in obj)

    def test_storage_handle_methods(self):
        obj = dir(main.StorageHandle)
        self.assert_("dev" in obj)
        self.assert_("pool" in obj)
        self.assert_("vol" in obj)
        self.assert_("check" in obj)
        self.assert_("resize" in obj)
        self.assert_("create" in obj)
        self.assert_("list" in obj)
        self.assert_("add" in obj)
        self.assert_("remove" in obj)
        self.assert_("snapshot" in obj)
        self.assert_("mount" in obj)
        self.assert_("set_globals" in obj)

    def test_run(self):
        ret,out = misc.run(["echo", "x"])
        self.assertEqual('x\n', out)
        ret,out = misc.run(["cat"], stdin_data="foo".encode())
        self.assertEqual('foo', out)


class SsmFunctionCheck(MockSystemDataSource):
    """
    Prepare data for ssm function check.
    """

    def setUp(self):
        super(SsmFunctionCheck, self).setUp()
        self.volumes_orig = main.Volumes
        main.Volumes = Volumes
        self.pool_orig = main.Pool
        main.Pool = Pool
        self.devices_orig = main.Devices
        main.Devices = Devices
        self._addDevice('/dev/sda', 11489037516)
        self._addDevice('/dev/sdb', 234566451)
        self._addDevice('/dev/sdc', 2684354560)
        self._addDevice('/dev/sdc1', 894784853, 1)
        self._addDevice('/dev/sdc2', 29826161, 2)
        self._addDevice('/dev/sdc3', 1042177280, 3)
        self._addDevice('/dev/sdd', 11673)

    def tearDown(self):
        super(SsmFunctionCheck, self).tearDown()
        main.Volumes = self.volumes_orig
        main.Pool = self.pool_orig
        main.Devices = self.devices_orig

    def mock_run(self, cmd, *args, **kwargs):
        for i,arg in enumerate(cmd):
            if arg is None:
                cmd[i] = ''
            elif type(arg) is not str:
                # python 3 prints sometimes too many decimals in case of numbers
                # like 123.00000001, so cut it down to one, like python 2 did
                if isinstance(arg, float):
                    cmd[i] = "%.1f" % arg
                else:
                    cmd[i] = str(arg)

        self.run_data.append(re.sub('\s\s+',' '," ".join(cmd).strip()))
        output = ""
        if cmd[0] == 'pooldata':
            return self.pool_data
        elif cmd[0] == 'volumedata':
            return self.vol_data
        elif cmd[0] == 'devdata':
            return self.dev_data
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output)

    def test_resize(self):
        # Generate some storage data
        self._addPool('default_pool', ['/dev/sda', '/dev/sdb'])
        self._addPool('my_pool', ['/dev/sdc2', '/dev/sdc3'])
        self._addVol('vol001', 2982616, 1, 'my_pool', ['/dev/sdc2'],
                    '/mnt/test1')
        self._addVol('vol002', 237284225, 1, 'default_pool', ['/dev/sda'])
        self._addVol('vol003', 1024, 1, 'default_pool', ['/dev/sdd'])
        self._addDevice('/dev/sde', 11489037516)

        # Extend Volume
        self._checkCmd("ssm resize", ['--size +4m', '/dev/default_pool/vol003'],
            "vol resize /dev/default_pool/vol003 5120.0 False")
        self._checkCmd("ssm resize", ['--size +50%', '/dev/default_pool/vol003'],
            "vol resize /dev/default_pool/vol003 1536.0 False")
        self._checkCmd("ssm resize", ['--size +50%USED', '/dev/default_pool/vol002'],
            "vol resize /dev/default_pool/vol002 355926849.5 False")
        self._checkCmd("ssm resize", ['--size +50%free', '/dev/default_pool/vol002'],
            "vol resize /dev/default_pool/vol002 5980449420.5 False")

        # Shrink volume
        self._checkCmd("ssm resize", ['-s-100G', '/dev/default_pool/vol002'],
            "vol resize /dev/default_pool/vol002 132426625.0 False")
        self._checkCmd("ssm resize", ['-s-50%', '/dev/default_pool/vol003'],
            "vol resize /dev/default_pool/vol003 512.0 False")
        self._checkCmd("ssm resize", ['-s-50%USED', '/dev/default_pool/vol002'],
            "vol resize /dev/default_pool/vol002 118641600.5 False")
        self._checkCmd("ssm resize", ['-s-1%free', '/dev/default_pool/vol002'],
            "vol resize /dev/default_pool/vol002 122420921.09 False")

        # Set volume size
        self._checkCmd("ssm resize", ['-s 10M', '/dev/my_pool/vol001'],
            "vol resize /dev/my_pool/vol001 10240.0 False")
        self._checkCmd("ssm resize", ['--size 80%', '/dev/default_pool/vol003'],
            "vol resize /dev/default_pool/vol003 819.2 False")
        self._checkCmd("ssm resize", ['--size 50%used', '/dev/default_pool/vol002'],
            "vol resize /dev/default_pool/vol002 118642624.5 False")
        self._checkCmd("ssm resize", ['--size 50%FREE', '/dev/default_pool/vol002'],
            "vol resize /dev/default_pool/vol002 5743165195.5 False")

        # Set volume and add devices
        self._checkCmd("ssm resize -s 12T /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "vol resize /dev/default_pool/vol003 12884901888.0 False")
        self.assertEqual(self.run_data[-2],
            "pool extend default_pool /dev/sdc1 /dev/sde")
        self._checkCmd("ssm resize -s 1258291200% /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "vol resize /dev/default_pool/vol003 12884901888.0 False")
        self.assertEqual(self.run_data[-2],
            "pool extend default_pool /dev/sdc1 /dev/sde")

        # Set volume size
        self._checkCmd("ssm resize -s 10G /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "vol resize /dev/default_pool/vol003 10485760.0 False")
        self.assertNotEqual(self.run_data[-2],
            "pool extend default_pool /dev/sdc1 /dev/sde")

        # Extend volume size with adding more devices
        self._checkCmd("ssm resize -s +12t /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "vol resize /dev/default_pool/vol003 12884902912.0 False")
        self.assertEqual(self.run_data[-2],
            "pool extend default_pool /dev/sdc1 /dev/sde")
        self._checkCmd("ssm resize -s +1258291100% /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "vol resize /dev/default_pool/vol003 12884901888.0 False")
        self.assertEqual(self.run_data[-2],
            "pool extend default_pool /dev/sdc1 /dev/sde")

        # Shrink volume with devices provided
        self._checkCmd("ssm resize -s-10G /dev/default_pool/vol002 /dev/sdc1 /dev/sde",
            [], "vol resize /dev/default_pool/vol002 226798465.0 False")
        self.assertNotEqual(self.run_data[-2],
            "pool extend default_pool /dev/sdc1 /dev/sde")
        self.assertNotEqual(self.run_data[-2],
            "pool extend default_pool /dev/sdc1")
        self._checkCmd("ssm resize -s-50% /dev/default_pool/vol002 /dev/sdc1 /dev/sde",
            [], "vol resize /dev/default_pool/vol002 118642112.5 False")
        self.assertNotEqual(self.run_data[-2],
            "pool extend default_pool /dev/sdc1 /dev/sde")
        self.assertNotEqual(self.run_data[-2],
            "pool extend default_pool /dev/sdc1")

        # Test that we do not use devices which are already used in different
        # pool
        self.assertRaises(Exception, main.main, "ssm resize -s +1.5T /dev/my_pool/vol001 /dev/sdb /dev/sda")
        self.assertRaises(Exception, main.main, "ssm resize -s +200%FREE /dev/my_pool/vol001 /dev/sdb /dev/sda")

        # If the device we are able to use can cover the size, then
        # it will be resized successfully
        self._checkCmd("ssm resize -s +1.5T /dev/my_pool/vol001 /dev/sdb /dev/sda /dev/sdc1",
            [], "vol resize /dev/my_pool/vol001 1613595352.0 False")

    def test_create(self):
        # Create volume using single device from non existent default pool
        self._checkCmd("ssm create", ['/dev/sda'],
            "pool create {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm create", ['--name myvolume', '--fstype ext4', '/dev/sda'])
        self._cmdEq("mkfs.ext4 /dev/{0}/myvolume".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool create {0} myvolume /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)
        self._cmdEq("pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -3)

        self._checkCmd("ssm -f create", ['--fstype ext4', '/dev/sda'])
        self._cmdEq("mkfs.ext4 -F /dev/{0}/lvol001".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("force pool create {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)
        self._cmdEq("force pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -3)

        self._checkCmd("ssm -v create", ['--name myvolume', '--fstype xfs', '/dev/sda'])
        self._cmdEq("mkfs.xfs /dev/{0}/myvolume".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("verbose pool create {0} myvolume /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)
        self._cmdEq("verbose pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -3)

        self._checkCmd("ssm -v -f create", ['--name myvolume', '--fstype xfs', '/dev/sda'])
        self._cmdEq("mkfs.xfs -f /dev/{0}/myvolume".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("force verbose pool create {0} myvolume /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)
        self._cmdEq("force verbose pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -3)

        self._checkCmd("ssm create", ['-s 2.6T', '/dev/sda'],
            "pool create {0} 2791728742.4 /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm create", ['-r 0', '-s 2.6T', '-I 16', '/dev/sda'],
            "pool create {0} 2791728742.4 0 16 /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        # Number of stripes must not exceed number of devices
        self.assertRaises(problem.GeneralError, main.main, "ssm create -r 1 -s 2.6T -I 16 -i 4 /dev/sda")

        self._checkCmd("ssm create", ['-r 1', '-s 2.6T', '-I 16', '/dev/sda /dev/sdb'],
            "pool create {0} 2791728742.4 1 16 /dev/sda /dev/sdb".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool new {0} /dev/sda /dev/sdb".format(main.DEFAULT_DEVICE_POOL), -2)

        # Create volume using single device from non existent my_pool
        self._checkCmd("ssm create", ['--pool my_pool', '/dev/sda'],
            "pool create my_pool /dev/sda")
        self._cmdEq("pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm create", ['--pool my_pool', '-s 2.6T', '/dev/sda'],
            "pool create my_pool 2791728742.4 /dev/sda")
        self._cmdEq("pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm create", ['-r 10', '-p my_pool', '-s 2.6T', '-I 16',
            '/dev/sda'], "pool create my_pool 2791728742.4 10 16 /dev/sda")
        self._cmdEq("pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm create", ['-r 0', '-p my_pool', '-s 2.6T', '-I 16',
            '/dev/sda'], "pool create my_pool 2791728742.4 0 16 /dev/sda")
        self._cmdEq("pool new my_pool /dev/sda", -2)

        # Create volume using multiple devices
        self._checkCmd("ssm create", ['/dev/sda /dev/sdc1'],
            "pool create {0} /dev/sda /dev/sdc1".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool new {0} /dev/sda /dev/sdc1".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm create", ['--pool my_pool', '/dev/sda /dev/sdc1'],
            "pool create my_pool /dev/sda /dev/sdc1")
        self._cmdEq("pool new my_pool /dev/sda /dev/sdc1", -2)

        # Create volume using single device from existing pool
        self._addPool(main.DEFAULT_DEVICE_POOL, ['/dev/sdb', '/dev/sdd'])
        self._checkCmd("ssm create", ['-r 10', '-s 2.6T', '-I 16',
            '-n myvolume', '/dev/sda'],
            "pool create {0} 2791728742.4 myvolume 10 16 /dev/sda". format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool extend {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm create", ['-s 20%', '-n myvolume'],
            "pool create {0} 46915624.8 myvolume". format(main.DEFAULT_DEVICE_POOL))

        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        self._checkCmd("ssm create", ['-r 1', '-p my_pool', '-s 2.6T', '-I 16',
            '-n myvolume', '/dev/sda'],
            "pool create my_pool 2791728742.4 myvolume 1 16 /dev/sda")
        self._cmdEq("pool extend my_pool /dev/sda", -2)

        # Create volume using multiple devices which one of the is in already
        # in the pool
        self._checkCmd("ssm create", ['-r 0', '-s 2.6T', '-I 16',
            '-i 2', '-n myvolume', '/dev/sda /dev/sdb'],
            "pool create {0} 2791728742.4 myvolume 0 2 16 /dev/sda /dev/sdb". format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool extend {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        self._checkCmd("ssm create", ['-r 10', '-p my_pool', '-s 2.6T', '-I 16',
            '-i 2', '-n myvolume', '/dev/sdc2 /dev/sda'],
            "pool create my_pool 2791728742.4 myvolume 10 2 16 /dev/sdc2 /dev/sda")
        self._cmdEq("pool extend my_pool /dev/sda", -2)

        # Test volume creation by specifying percentage instead of a concrete
        # size
        self._checkCmd("ssm create -s 20% -n myvolume", [],
            "pool create {0} 46915624.8 myvolume".format(main.DEFAULT_DEVICE_POOL))
        self._checkCmd("ssm create -s 20%free -n myvolume", [],
            "pool create {0} 46915624.8 myvolume".format(main.DEFAULT_DEVICE_POOL))
        self._addVol('vol002', 1073741824, 1, main.DEFAULT_DEVICE_POOL, ['/dev/sdc'])
        self._checkCmd("ssm create -s 20% -n myvolume", [],
            "pool create {0} 583786536.8 myvolume".format(main.DEFAULT_DEVICE_POOL))
        self._checkCmd("ssm create -s 20%free -n myvolume", [],
            "pool create {0} 369038172.0 myvolume".format(main.DEFAULT_DEVICE_POOL))
        self._checkCmd("ssm create -s 20%used -n myvolume", [],
            "pool create {0} 214748364.8 myvolume".format(main.DEFAULT_DEVICE_POOL))

        # Test that we do not use devices which are already used in different
        # pool
        self.assertRaises(Exception, main.main, "ssm create -p new_pool /dev/sdc2 /dev/sdc3")
        self.assertRaises(Exception, main.main, "ssm create -p new_pool /dev/sdc2 /dev/sdc3 /dev/sda")
        # If the device we are able to use can cover the size, then
        # it will be created
        self._checkCmd("ssm create", ['-s 100M', '-p new_pool', '/dev/sdc2 /dev/sdc3 /dev/sda'],
            "pool create new_pool 102400.0 /dev/sda")

        #sys.stdout = out.stdout

    def test_add(self):
        # Adding to non existent pool
        # Add device into default pool
        self._checkCmd("ssm add", ['/dev/sda'],
            "pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        # Add more devices into default pool
        self._checkCmd("ssm add", ['/dev/sda /dev/sdc1'],
            "pool new {0} /dev/sda /dev/sdc1".format(main.DEFAULT_DEVICE_POOL))
        # Add device into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda'],
            "pool new my_pool /dev/sda")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda'],
            "pool new my_pool /dev/sda")
        # Add more devices into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda /dev/sdc1'],
            "pool new my_pool /dev/sda /dev/sdc1")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda /dev/sdc1'],
            "pool new my_pool /dev/sda /dev/sdc1")
        # Add force
        self._checkCmd("ssm -f add", ['--pool my_pool', '/dev/sda'],
            "force pool new my_pool /dev/sda")
        # Add verbose
        self._checkCmd("ssm -v add", ['--pool my_pool', '/dev/sda'],
            "verbose pool new my_pool /dev/sda")
        # Add force and verbose
        self._checkCmd("ssm -v -f add", ['--pool my_pool', '/dev/sda'],
            "force verbose pool new my_pool /dev/sda")

        # Adding to existing default pool
        self._addPool(main.DEFAULT_DEVICE_POOL, ['/dev/sdb', '/dev/sdd'])
        # Add device into default pool
        self._checkCmd("ssm add", ['/dev/sda'],
            "pool extend {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        # Add more devices into default pool
        self._checkCmd("ssm add", ['/dev/sda /dev/sdc1'],
            "pool extend {0} /dev/sda /dev/sdc1".format(main.DEFAULT_DEVICE_POOL))

        # Adding to existing defined pool
        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        # Add device into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda'],
            "pool extend my_pool /dev/sda")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda'],
            "pool extend my_pool /dev/sda")
        # Add more devices into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda /dev/sdc1'],
            "pool extend my_pool /dev/sda /dev/sdc1")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda /dev/sdc1'],
            "pool extend my_pool /dev/sda /dev/sdc1")
        # Add force
        self._checkCmd("ssm -f add", ['--pool my_pool', '/dev/sda'],
            "force pool extend my_pool /dev/sda")
        # Add verbose
        self._checkCmd("ssm -v add", ['--pool my_pool', '/dev/sda'],
            "verbose pool extend my_pool /dev/sda")
        # Add force and verbose
        self._checkCmd("ssm -v -f add", ['--pool my_pool', '/dev/sda'],
            "force verbose pool extend my_pool /dev/sda")

        # Add two devices into existing pool (one of the devices already is in
        # the pool
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sdc2 /dev/sda'],
            "pool extend my_pool /dev/sda")
        self._checkCmd("ssm add", ['/dev/sda /dev/sdb'],
            "pool extend {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL))

    def test_remove(self):
        # Generate some storage data
        self._addPool('default_pool', ['/dev/sda', '/dev/sdb'])
        self._addPool('my_pool', ['/dev/sdc2', '/dev/sdc3', '/dev/sdc1'])
        self._addVol('vol001', 117283225, 1, 'default_pool', ['/dev/sda'])
        self._addVol('vol002', 237284225, 1, 'default_pool', ['/dev/sda'])
        self._addVol('vol003', 1024, 1, 'default_pool', ['/dev/sdd'])
        self._addVol('vol004', 209715200, 2, 'default_pool', ['/dev/sda',
                     '/dev/sdb'])

        # remove volume
        main.main("ssm remove /dev/default_pool/vol002")
        self._cmdEq("vol remove /dev/default_pool/vol002")
        # remove multiple volumes
        main.main("ssm remove /dev/default_pool/vol002 /dev/default_pool/vol003")
        self._cmdEq("vol remove /dev/default_pool/vol002", -2)
        self._cmdEq("vol remove /dev/default_pool/vol003")
        # remove pool
        main.main("ssm remove my_pool")
        self._cmdEq("pool remove my_pool")
        # remove multiple pools
        main.main("ssm remove my_pool default_pool")
        self._cmdEq("pool remove my_pool", -2)
        self._cmdEq("pool remove default_pool")
        # remove device
        main.main("ssm remove /dev/sdc1")
        self._cmdEq("pool reduce my_pool /dev/sdc1")
        # remove multiple devices
        main.main("ssm remove /dev/sdc1 /dev/sdb")
        self._cmdEq("pool reduce my_pool /dev/sdc1", -2)
        self._cmdEq("pool reduce default_pool /dev/sdb")
        # remove combination
        main.main("ssm remove /dev/sdb my_pool /dev/default_pool/vol001")
        self._cmdEq("pool reduce default_pool /dev/sdb", -3)
        self._cmdEq("pool remove my_pool", -2)
        self._cmdEq("vol remove /dev/default_pool/vol001")
        # remove all
        main.main("ssm remove --all")
        self._cmdEq("pool remove default_pool", -2)
        self._cmdEq("pool remove my_pool")
        # remove force
        main.main("ssm -f remove /dev/default_pool/vol002")
        self._cmdEq("force vol remove /dev/default_pool/vol002")
        # remove verbose
        main.main("ssm -v remove /dev/default_pool/vol002")
        self._cmdEq("verbose vol remove /dev/default_pool/vol002")
        # remove verbose + force
        main.main("ssm -v -f remove /dev/default_pool/vol002")
        self._cmdEq("force verbose vol remove /dev/default_pool/vol002")

    def test_snapshot(self):
        # Generate some storage data
        self._addPool('default_pool', ['/dev/sda', '/dev/sdb'])
        self._addPool('my_pool', ['/dev/sdc2', '/dev/sdc3', '/dev/sdc1'])
        self._addVol('vol001', 117283225, 1, 'default_pool', ['/dev/sda'],
                    '/mnt/test1')
        self._addVol('vol002', 237284225, 1, 'default_pool', ['/dev/sda'])
        self._addVol('vol003', 1024, 1, 'default_pool', ['/dev/sdd'])
        self._addVol('vol004', 209715200, 2, 'default_pool', ['/dev/sda',
                     '/dev/sdb'], '/mnt/test')

        # Create snapshot
        self._checkCmd("ssm snapshot", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 None")
        # Create snapshot verbose
        self._checkCmd("ssm -v snapshot", ['/dev/default_pool/vol004'],
            "verbose vol snapshot /dev/default_pool/vol004 None")
        # Create snapshot force
        self._checkCmd("ssm -f snapshot", ['/dev/default_pool/vol004'],
            "force vol snapshot /dev/default_pool/vol004 None")
        # Create snapshot force verbose
        self._checkCmd("ssm -f -v snapshot", ['/dev/default_pool/vol004'],
            "force verbose vol snapshot /dev/default_pool/vol004 None")

        # Create snapshot with size specified
        self._checkCmd("ssm snapshot --size 1G", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 1048576.0")
        self._checkCmd("ssm snapshot --size 10%", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 20971520.0")
        self._checkCmd("ssm snapshot --size 10%used", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 56428367.4")
        self._checkCmd("ssm snapshot --size 10%free", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 1115933196.6")
        # Create snapshot with destination specified
        self._checkCmd("ssm snapshot --dest /mnt/test", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test None")
        # Create snapshot with the name specified
        self._checkCmd("ssm snapshot --name test", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 test None")
        # Create snapshot with both destination and size specified
        self._checkCmd("ssm snapshot",
            ['--size 1G', '--dest /mnt/test' ,'/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test 1048576.0")
        self._checkCmd("ssm snapshot",
            ['--size 10%', '--dest /mnt/test','/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test 20971520.0")
        self._checkCmd("ssm snapshot --dest /mnt/test --size 10%used",
            ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test 56428367.4")
        self._checkCmd("ssm snapshot --dest /mnt/test --size 10%free",
            ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test 1115933196.6")
        # Create snapshot with both name and size specified
        self._checkCmd("ssm snapshot",
            ['--size 1G', '--name test' ,'/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 test 1048576.0")
        self._checkCmd("ssm snapshot",
            ['--size 10%', '--name test','/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 test 20971520.0")

        # Repeat the test with specifying mount point instead of volume

        # Create snapshot
        self._checkCmd("ssm snapshot", ['/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 None")
        # Create snapshot with size specified
        self._checkCmd("ssm snapshot --size 1G", ['/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 1048576.0")
        self._checkCmd("ssm snapshot --size 10%", ['/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 20971520.0")
        # Create snapshot with destination specified
        self._checkCmd("ssm snapshot --dest /mnt/test", ['/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test None")
        # Create snapshot with the name specified
        self._checkCmd("ssm snapshot --name test", ['/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 test None")
        # Create snapshot with both destination and size specified
        self._checkCmd("ssm snapshot",
            ['--size 1G', '--dest /mnt/test' ,'/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test 1048576.0")
        # Create snapshot with both name and size specified
        self._checkCmd("ssm snapshot",
            ['--size 1G', '--name test' ,'/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 test 1048576.0")

    def test_mount(self):
        self._addDir("/mnt/test")
        self._addDir("/mnt/test1")
        self._addDir("/mnt/test2")
        # Generate some storage data
        self._addPool('default_pool', ['/dev/sda', '/dev/sdb'])
        self._addPool('my_pool', ['/dev/sdc2', '/dev/sdc3', '/dev/sdc1'])
        self._addVol('vol001', 117283225, 1, 'default_pool', ['/dev/sda'],
                    '/mnt/test1')
        self._addVol('vol002', 237284225, 1, 'my_pool', ['/dev/sda'])

        # Simple mount test
        main.main("ssm mount /dev/default_pool/vol001 /mnt/test")
        self._cmdEq("mount /dev/default_pool/vol001 /mnt/test")
        main.main("ssm mount -o discard /dev/default_pool/vol001 /mnt/test")
        self._cmdEq("mount -o discard /dev/default_pool/vol001 /mnt/test")
        main.main("ssm mount --options rw,discard,neco=44 /dev/my_pool/vol002 /mnt/test1")
        self._cmdEq("mount -o rw,discard,neco=44 /dev/my_pool/vol002 /mnt/test1")

        # Non existing volume
        main.main("ssm mount nonexisting /mnt/test1")
        self._cmdEq("mount nonexisting /mnt/test1")
        main.main("ssm mount -o discard,rw nonexisting /mnt/test1")
        self._cmdEq("mount -o discard,rw nonexisting /mnt/test1")


class MyInfo(object):
    def __init__(self, options, data=None):
        self.data = data or {}
        self.options = options
        self.type = 'backend'

    @property
    def y(self):
        return 'yes' if self.options.yes else ''

    @property
    def f(self):
        return 'force' if self.options.force else ''

    @property
    def v(self):
        return 'verbose' if self.options.verbose else ''

    def __iter__(self):
        for item in sorted(self.data):
            yield item

    def __getitem__(self, key):
        if key in self.data:
            return self.data[key]


class PoolInfo(MyInfo):
    def __init__(self, *args, **kwargs):
        super(PoolInfo, self).__init__(*args, **kwargs)
        self.exist = False
        self.data.update(misc.run(['pooldata']))

    def reduce(self, pool, devices):
        if type(devices) is not list:
            devices = [devices]
        cmd = [self.f, self.v, self.y, 'pool reduce', pool]
        cmd.extend(devices)
        misc.run(cmd)

    def remove(self, pool):
        misc.run([self.f, self.v, self.y, 'pool remove', pool])

    def new(self, pool, devices):
        if type(devices) is not list:
            devices = [devices]
        cmd = [self.f, self.v, self.y, 'pool new', pool]
        cmd.extend(devices)
        misc.run(cmd)

    def extend(self, pool, devices):
        if type(devices) is not list:
            devices = [devices]
        cmd = [self.f, self.v, self.y, 'pool extend', pool]
        cmd.extend(devices)
        misc.run(cmd)

    def create(self, pool, size='', name='', devs='',
               options=None):
        options = options or {}
        if type(devs) is not list:
            devices = [devs]
        if 'raid' in options:
            stripes = options['stripes']
            stripesize = options['stripesize']
            level = options['raid']
        else:
            stripes = stripesize = level = ""
        misc.run([self.f, self.v, self.y, 'pool create', pool, size, name,
            level, stripes, stripesize, " ".join(devs)])
        if not name:
            name = "lvol001"
        return "/dev/{0}/{1}".format(pool, name)


class VolumeInfo(MyInfo):
    def __init__(self, *args, **kwargs):
        super(VolumeInfo, self).__init__(*args, **kwargs)
        self.data.update(misc.run(['volumedata']))

    def remove(self, volume):
        misc.run([self.f, self.v, self.y, 'vol remove', volume])

    def resize(self, lv, size, resize_fs=True):
        misc.run([self.f, self.v, self.y, 'vol resize', lv, str(size),
                  str(resize_fs)])

    def snapshot(self, volume, destination, name, snap_size=None):
        # python 3 prints sometimes too many decimals in case of numbers
        # like 123.00000001, so cut it down to one, like python 2 did
        if snap_size:
            snap_size = "%.1f" % snap_size
        misc.run([self.f, self.v, self.y, 'vol snapshot', volume, destination,
                name, str(snap_size)])


class DevInfo(MyInfo):
    def __init__(self, *args, **kwargs):
        super(DevInfo, self).__init__(*args, **kwargs)
        #if len(misc.run(['devdata']) > 0):
        self.data.update(misc.run(['devdata']))

    def remove(self, devices):
        if type(devices) is not list:
            devices = [devices]
        misc.run([self.f, self.v, self.y, 'dev remove', devices])
        cmd.extend(devices)
        misc.run(cmd)


class Pool(main.Storage):
    def __init__(self, *args, **kwargs):
        super(Pool, self).__init__(*args, **kwargs)
        _default_backend = PoolInfo(options=self.options)
        self._data = {'test': _default_backend}
        self.default = main.Item(_default_backend, main.DEFAULT_DEVICE_POOL)
        self.header = ['Pool', 'Devices', 'Free', 'Used', 'Total']
        self.attrs = ['pool_name', 'dev_count', 'pool_free', 'pool_used', 'pool_size']
        self.types = [str, str, float, float, float]


class Volumes(main.Storage):
    def __init__(self, *args, **kwargs):
        super(Volumes, self).__init__(*args, **kwargs)
        self._data = {'test': VolumeInfo(options=self.options)}
        self.header = ['Volume', 'Volume size', 'FS', 'Free',
                       'Used', 'FS size', 'Type', 'Mount point']
        self.attrs = ['dev_name', 'dev_size', 'fs_type',
                      'fs_free', 'fs_used', 'fs_size', 'type', 'mount']
        self.types = [str, float, str, float, float, float, str, str]


class Devices(main.Storage):
    def __init__(self, *args, **kwargs):
        super(Devices, self).__init__(*args, **kwargs)
        self._data = {'dev': main.DeviceInfo(options=self.options,
                                data=DevInfo(options=self.options).data)}
        self.header = ['Device', 'Free', 'Used',
                       'Total', 'Pool', 'Mount point']
        self.attrs = ['dev_name', 'dev_free', 'dev_used', 'dev_size',
                      'pool_name', 'mount']
        self.types = [str, float, float, float, str, str]
