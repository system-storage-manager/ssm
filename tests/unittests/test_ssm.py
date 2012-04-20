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
import itertools
from ssmlib import main
from ssmlib import misc

from tests.unittests.common import *

class SimpleStorageHandleSanityCheck(BaseStorageHandleInit):
    '''
    Simple sanity ckecks for StorageHandle class and some of its methods.
    '''

    def test_constructor(self):
        # Check initial variables
        self.assertFalse(self.storage.force)
        self.assertFalse(self.storage.verbose)
        self.assertFalse(self.storage.yes)
        self.assertIsNone(self.storage.config)
        self.assertIsNone(self.storage._mpoint)
        self.assertIsNone(self.storage._dev)
        self.assertIsNone(self.storage._pool)
        self.assertIsNone(self.storage._volumes)

    def test_create_fs(self):
        for fs in main.EXTN:
            self.storage.set_globals(True, True, False, "my_new_config")
            self.storage._create_fs(fs, "/dev/foo/bar")
            self.assertEqual('mkfs.{0} -v -F /dev/foo/bar'.format(fs),
                    self.run_data[-1])
            self.storage.set_globals(False, False, False, "my_new_config")
            self.storage._create_fs(fs, "/dev/foo/bar")
            self.assertEqual('mkfs.{0} /dev/foo/bar'.format(fs),
                    self.run_data[-1])
            self.storage.set_globals(True, False, False, "my_new_config")
            self.storage._create_fs(fs, "/dev/foo/bar")
            self.assertEqual('mkfs.{0} -F /dev/foo/bar'.format(fs),
                    self.run_data[-1])
            self.storage.set_globals(False, True, False, "my_new_config")
            self.storage._create_fs(fs, "/dev/foo/bar")
            self.assertEqual('mkfs.{0} -v /dev/foo/bar'.format(fs),
                    self.run_data[-1])
        self.storage.set_globals(True, True, False, "my_new_config")
        self.storage._create_fs("xfs", "/dev/foo/bar")
        self.assertEqual('mkfs.xfs -f /dev/foo/bar', self.run_data[-1])
        self.storage.set_globals(False, False, False, "my_new_config")
        self.storage._create_fs("xfs", "/dev/foo/bar")
        self.assertEqual('mkfs.xfs /dev/foo/bar', self.run_data[-1])
        self.storage.set_globals(True, False, False, "my_new_config")
        self.storage._create_fs("xfs", "/dev/foo/bar")
        self.assertEqual('mkfs.xfs -f /dev/foo/bar', self.run_data[-1])
        self.storage.set_globals(False, True, False, "my_new_config")
        self.storage._create_fs("xfs", "/dev/foo/bar")
        self.assertEqual('mkfs.xfs /dev/foo/bar', self.run_data[-1])


class StorageHandleSanityCheck(BaseStorageHandleInit):
    '''
    Sanity checks for StorageHandle class and other classes used via
    StorageHandle class.
    '''

    def setUp(self):
        super(StorageHandleSanityCheck, self).setUp()
        self.storage.set_globals(True, True, True, "my_config")
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
        self.assertTrue(self.storage.force)
        self.assertTrue(self.storage.verbose)
        self.assertTrue(self.storage.yes)
        self.assertEqual(self.storage.config, "my_config")

        # Check if we have right instances
        self.assertIsInstance(self.dev, main.Devices)
        self.assertIsInstance(self.vol, main.Volumes)
        self.assertIsInstance(self.pool, main.Pool)

        # Check initial variables
        for source in self.dev, self.vol, self.pool:
            self.assertTrue(source.force)
            self.assertTrue(source.verbose)
            self.assertTrue(source.yes)
            self.assertIsInstance(source._data, dict)
            self.assertGreater(len(source._data), 0)
            self.assertIsInstance(source.header, list)
            self.assertGreater(len(source.header), 0)
            self.assertIsInstance(source.attrs, list)
            self.assertGreater(len(source.attrs), 0)
            self.assertIsInstance(source.types, list)
            self.assertGreater(len(source.types), 0)
            for item  in source._data.itervalues():
                self.assertTrue(item.force)
                self.assertTrue(item.verbose)
                self.assertTrue(item.yes)

    def test_set_globals_propagation(self):
        self.storage.set_globals(False, False, False, "my_new_config")
        # Check initial variables
        self.assertFalse(self.storage.force)
        self.assertFalse(self.storage.verbose)
        self.assertFalse(self.storage.yes)
        self.assertEqual(self.storage.config, "my_new_config")

        # Check initial variables
        for source in self.dev, self.vol, self.pool:
            self.assertFalse(source.force)
            self.assertFalse(source.verbose)
            self.assertFalse(source.yes)
            self.assertIsInstance(source._data, dict)
            self.assertGreater(len(source._data), 0)
            self.assertIsInstance(source.header, list)
            self.assertGreater(len(source.header), 0)
            self.assertIsInstance(source.attrs, list)
            self.assertGreater(len(source.attrs), 0)
            self.assertIsInstance(source.types, list)
            self.assertGreater(len(source.types), 0)
            for item  in source._data.itervalues():
                self.assertFalse(item.force)
                self.assertFalse(item.verbose)
                self.assertFalse(item.yes)

    def test_backend_generic_methods(self):
        for source in self.dev, self.vol, self.pool:
            obj = dir(source)
            self.assertIn("__iter__", obj)
            self.assertIn("__contains__", obj)
            self.assertIn("__getitem__", obj)
            self.assertIn("filesystems", obj)
            self.assertIn("ptable", obj)
            self.assertIn("set_globals", obj)
            for bknd in source._data.itervalues():
                obj = dir(bknd)
                self.assertIn("__iter__", obj)
                self.assertIn("__getitem__", obj)
                self.assertIn("__init__", obj)

    def test_volumes_specific_methods(self):
        for bknd in self.vol._data.itervalues():
            obj = dir(bknd)
            self.assertIn("remove", obj)

    def test_pool_specific_methods(self):
        for bknd in self.pool._data.itervalues():
            obj = dir(bknd)
            self.assertIn("reduce", obj)
            self.assertIn("remove", obj)
            self.assertIn("create", obj)
            self.assertIn("new", obj)
            self.assertIn("extend", obj)


class SimpleSsmSanityCheck(unittest.TestCase):
    '''
    Simple sanity check of ssm module.
    '''

    def test_existing_objects(self):
        obj = dir(main)
        self.assertIn("StorageHandle", obj)
        self.assertIn("FsInfo", obj)
        self.assertIn("DeviceInfo", obj)
        self.assertIn("SUPPORTED_FS", obj)
        self.assertIn("DEFAULT_DEVICE_POOL", obj)
        self.assertIn("Storage", obj)
        self.assertIn("Pool", obj)
        self.assertIn("Devices", obj)
        self.assertIn("Volumes", obj)

    def test_fsinfo_methods(self):
        obj = dir(main.FsInfo)
        self.assertIn("extN_get_info", obj)
        self.assertIn("extN_fsck", obj)
        for fs in set(main.SUPPORTED_FS) - set(main.EXTN):
            if fs == 'btrfs':
                continue
            self.assertIn("{0}_get_info".format(fs), obj)
            self.assertIn("{0}_fsck".format(fs), obj)

    def test_storage_handle_methods(self):
        obj = dir(main.StorageHandle)
        self.assertIn("dev", obj)
        self.assertIn("pool", obj)
        self.assertIn("vol", obj)
        self.assertIn("check", obj)
        self.assertIn("resize", obj)
        self.assertIn("create", obj)
        self.assertIn("list", obj)
        self.assertIn("add", obj)
        self.assertIn("remove", obj)
        self.assertIn("mirror", obj)
        self.assertIn("snapshot", obj)
        self.assertIn("set_globals", obj)


class SsmFunctionCheck(MockSystemDataSource):
    '''
    Prepare data for ssm function check.
    '''

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
            if arg == None:
                cmd[i] = ''
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

    def test_create(self):

        out = MyStdout()
        sys.stdout = out

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

        self._checkCmd("ssm -f create", ['/dev/sda'],
            "force pool create {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("force pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm -v create", ['/dev/sda'],
            "verbose pool create {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("verbose pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm -f -v create", ['/dev/sda'],
            "force verbose pool create {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("force verbose pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm create", ['-s 2.6T', '/dev/sda'],
            "pool create {0} 2791728742.40 /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm create", ['-s 2.6T', '-I 16', '/dev/sda'],
            "pool create {0} 2791728742.40 16 /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm create", ['-s 2.6T', '-I 16', '-i 4', '/dev/sda'],
            "pool create {0} 2791728742.40 4 16 /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._checkCmd("ssm create", ['-s 2.6T', '-I 16', '-i 4', '-n myvolume',
            '/dev/sda'],
            "pool create {0} 2791728742.40 myvolume 4 16 /dev/sda".format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool new {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        # Create volume using single device from non existent my_pool
        self._checkCmd("ssm create", ['--pool my_pool', '/dev/sda'],
            "pool create my_pool /dev/sda")
        self._cmdEq("pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm -f create", ['--pool my_pool', '/dev/sda'],
            "force pool create my_pool /dev/sda")
        self._cmdEq("force pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm -v create", ['--pool my_pool', '/dev/sda'],
            "verbose pool create my_pool /dev/sda")
        self._cmdEq("verbose pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm -v -f create", ['--pool my_pool', '/dev/sda'],
            "force verbose pool create my_pool /dev/sda")
        self._cmdEq("force verbose pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm create", ['--pool my_pool', '-s 2.6T', '/dev/sda'],
            "pool create my_pool 2791728742.40 /dev/sda")
        self._cmdEq("pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm create", ['-p my_pool', '-s 2.6T', '-I 16',
            '/dev/sda'], "pool create my_pool 2791728742.40 16 /dev/sda")
        self._cmdEq("pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm create", ['-p my_pool', '-s 2.6T', '-I 16',
            '-i 4', '/dev/sda'], "pool create my_pool 2791728742.40 4 16 /dev/sda")
        self._cmdEq("pool new my_pool /dev/sda", -2)

        self._checkCmd("ssm create", ['-p my_pool', '-s 2.6T', '-I 16',
            '-i 4', '-n myvolume', '/dev/sda'],
            "pool create my_pool 2791728742.40 myvolume 4 16 /dev/sda")
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
        self._checkCmd("ssm create", ['-s 2.6T', '-I 16',
            '-i 4', '-n myvolume', '/dev/sda'],
            "pool create {0} 2791728742.40 myvolume 4 16 /dev/sda". format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool extend {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        self._checkCmd("ssm create", ['-p my_pool', '-s 2.6T', '-I 16',
            '-i 4', '-n myvolume', '/dev/sda'],
            "pool create my_pool 2791728742.40 myvolume 4 16 /dev/sda")
        self._cmdEq("pool extend my_pool /dev/sda", -2)

        # Create volume using multiple devices which one of the is in already
        # in the pool
        self._checkCmd("ssm create", ['-s 2.6T', '-I 16',
            '-i 4', '-n myvolume', '/dev/sda /dev/sdb'],
            "pool create {0} 2791728742.40 myvolume 4 16 /dev/sda /dev/sdb". format(main.DEFAULT_DEVICE_POOL))
        self._cmdEq("pool extend {0} /dev/sda".format(main.DEFAULT_DEVICE_POOL), -2)

        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        self._checkCmd("ssm create", ['-p my_pool', '-s 2.6T', '-I 16',
            '-i 4', '-n myvolume', '/dev/sdc2 /dev/sda'],
            "pool create my_pool 2791728742.40 myvolume 4 16 /dev/sdc2 /dev/sda")
        self._cmdEq("pool extend my_pool /dev/sda", -2)

        sys.stdout = out.stdout

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
            "vol snapshot /dev/default_pool/vol004 41943040.0 False")
        # Create snapshot verbose
        self._checkCmd("ssm -v snapshot", ['/dev/default_pool/vol004'],
            "verbose vol snapshot /dev/default_pool/vol004 41943040.0 False")
        # Create snapshot force
        self._checkCmd("ssm -f snapshot", ['/dev/default_pool/vol004'],
            "force vol snapshot /dev/default_pool/vol004 41943040.0 False")
        # Create snapshot force verbose
        self._checkCmd("ssm -f -v snapshot", ['/dev/default_pool/vol004'],
            "force verbose vol snapshot /dev/default_pool/vol004 41943040.0 False")

        # Create snapshot with size specified
        self._checkCmd("ssm snapshot --size 1G", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 1048576.0 True")
        # Create snapshot with destination specified
        self._checkCmd("ssm snapshot --dest /mnt/test", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test 41943040.0 False")
        # Create snapshot with the name specified
        self._checkCmd("ssm snapshot --name test", ['/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 test 41943040.0 False")
        # Create snapshot with both destination and size specified
        self._checkCmd("ssm snapshot",
            ['--size 1G', '--dest /mnt/test' ,'/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test 1048576.0 True")
        # Create snapshot with both name and size specified
        self._checkCmd("ssm snapshot",
            ['--size 1G', '--name test' ,'/dev/default_pool/vol004'],
            "vol snapshot /dev/default_pool/vol004 test 1048576.0 True")

        # Repeat the test with specifying mount point instead of volume

        # Create snapshot
        self._checkCmd("ssm snapshot", ['/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 41943040.0 False")
        # Create snapshot with size specified
        self._checkCmd("ssm snapshot --size 1G", ['/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 1048576.0 True")
        # Create snapshot with destination specified
        self._checkCmd("ssm snapshot --dest /mnt/test", ['/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test 41943040.0 False")
        # Create snapshot with the name specified
        self._checkCmd("ssm snapshot --name test", ['/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 test 41943040.0 False")
        # Create snapshot with both destination and size specified
        self._checkCmd("ssm snapshot",
            ['--size 1G', '--dest /mnt/test' ,'/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 /mnt/test 1048576.0 True")
        # Create snapshot with both name and size specified
        self._checkCmd("ssm snapshot",
            ['--size 1G', '--name test' ,'/mnt/test'],
            "vol snapshot /dev/default_pool/vol004 test 1048576.0 True")



class MyInfo(object):
    def __init__(self, data=None, force=False, verbose=False, yes=False):
        self.data = data or {}
        self.force = force
        self.verbose = verbose
        self.yes = yes
        self.type = 'backend'

    @property
    def y(self):
        return 'yes' if self.yes else ''

    @property
    def f(self):
        return 'force' if self.force else ''

    @property
    def v(self):
        return 'verbose' if self.verbose else ''

    def __iter__(self):
        for item in sorted(self.data.iterkeys()):
            yield item

    def __getitem__(self, key):
        if key in self.data.iterkeys():
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
               stripes='', stripesize=''):
        if type(devs) is not list:
            devices = [devs]
        misc.run([self.f, self.v, self.y, 'pool create', pool, size, name,
            stripes, stripesize, " ".join(devs)])
        if not name:
            name = "lvol001"
        return "/dev/{0}/{1}".format(pool, name)


class VolumeInfo(MyInfo):
    def __init__(self, *args, **kwargs):
        super(VolumeInfo, self).__init__(*args, **kwargs)
        self.data.update(misc.run(['volumedata']))

    def remove(self, volume):
        misc.run([self.f, self.v, self.y, 'vol remove', volume])

    def snapshot(self, volume, destination, name, size, user_set_size):
        misc.run([self.f, self.v, self.y, 'vol snapshot', volume, destination,
                name, str(size), str(user_set_size)])


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
        _default_backend = PoolInfo(force=self.force, verbose=self.verbose,
                                   yes=self.yes)
        self._data = {'test': _default_backend}
        self.default = main.Item(_default_backend, main.DEFAULT_DEVICE_POOL)
        self.header = ['Pool', 'Devices', 'Free', 'Used', 'Total']
        self.attrs = ['pool_name', 'dev_count', 'pool_free', 'pool_used', 'pool_size']
        self.types = [str, str, float, float, float]


class Volumes(main.Storage):
    def __init__(self, *args, **kwargs):
        super(Volumes, self).__init__(*args, **kwargs)
        self._data = {'test': VolumeInfo(force=self.force, verbose=self.verbose,
                             yes=self.yes)}
        self.header = ['Volume', 'Volume size', 'FS', 'Free',
                       'Used', 'FS size', 'Type', 'Mount point']
        self.attrs = ['dev_name', 'dev_size', 'fs_type',
                      'fs_free', 'fs_used', 'fs_size', 'type', 'mount']
        self.types = [str, float, str, float, float, float, str, str]


class Devices(main.Storage):
    def __init__(self, *args, **kwargs):
        super(Devices, self).__init__(*args, **kwargs)
        self._data = {'dev': main.DeviceInfo(data=DevInfo().data,
                        force=self.force, verbose=self.verbose, yes=self.yes)}
        self.header = ['Device', 'Free', 'Used',
                       'Total', 'Pool', 'Mount point']
        self.attrs = ['dev_name', 'dev_free', 'dev_used', 'dev_size',
                      'pool_name', 'mount']
        self.types = [str, float, float, float, str, str]
