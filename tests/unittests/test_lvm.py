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

# Unittests for the system storage manager lvm backend

import unittest
from ssmlib import main
from ssmlib import problem
from ssmlib.backends import lvm
from tests.unittests.common import *


class LvmFunctionCheck(MockSystemDataSource):

    def setUp(self):
        super(LvmFunctionCheck, self).setUp()
        self._addDevice('/dev/sda', 11489037516)
        self._addDevice('/dev/sdb', 234566451)
        self._addDevice('/dev/sdc', 2684354560)
        self._addDevice('/dev/sdc1', 894784853, 1)
        self._addDevice('/dev/sdc2', 29826161, 2)
        self._addDevice('/dev/sdc3', 1042177280, 3)
        self._addDevice('/dev/sdd', 11673)
        self._addDevice('/dev/sde', 1042177280)
        main.SSM_DEFAULT_BACKEND = 'lvm'

    def mock_run(self, cmd, *args, **kwargs):

        # Convert all parts of cmd into string
        for i, item in enumerate(cmd):
            if type(item) is not str:
                cmd[i] = str(item)

        self.run_data.append(" ".join(cmd))
        output = ""
        if cmd[1] == 'pvs':
            for dev, data in self.dev_data.iteritems():
                if 'pool_name' in data:
                    output += "{0}|{1}|{2}|{3}\n".format(dev, data['pool_name'],
                            data['dev_free'], data['dev_used'])
        elif cmd[1] == 'vgs':
            for pool, data in self.pool_data.iteritems():
                output += "{0}|{1}|{2}|{3}|{4}\n".format(pool, data['dev_count'],
                        data['pool_size'], data['pool_free'], data['vol_count'])
        elif cmd[1] == 'lvs':
            for vol, data in self.vol_data.iteritems():
                output += "{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}\n".format(data['pool_name'],
                        data['vol_size'], data['stripes'], data['stripesize'],
                        data['type'], data['dev_name'].split("/")[-1],
                        data['origin'], data['attr'])
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output)

    def test_lvm_create(self):
        default_pool = lvm.SSM_LVM_DEFAULT_POOL

        # Create volume using single device from non existent default pool
        self._checkCmd("ssm create", ['/dev/sda'],
            "lvm lvcreate {0} -l 100%PVS -n lvol001 /dev/sda".format(default_pool))
        self._cmdEq("lvm vgcreate {0} /dev/sda".format(default_pool), -2)

        # Specify backnend
        self._checkCmd("ssm -b lvm create", ['/dev/sda'],
            "lvm lvcreate {0} -l 100%PVS -n lvol001 /dev/sda".format(default_pool))
        self._cmdEq("lvm vgcreate {0} /dev/sda".format(default_pool), -2)

        main.SSM_DEFAULT_BACKEND = "btrfs"
        self._checkCmd("ssm --backend lvm create", ['/dev/sda'],
            "lvm lvcreate {0} -l 100%PVS -n lvol001 /dev/sda".format(default_pool))
        self._cmdEq("lvm vgcreate {0} /dev/sda".format(default_pool), -2)
        main.SSM_DEFAULT_BACKEND = "lvm"

        self._checkCmd("ssm create", ['--name myvolume', '--fstype ext4', '/dev/sda'])
        self._cmdEq("mkfs.ext4 /dev/{0}/myvolume".format(default_pool))
        self._cmdEq("lvm lvcreate {0} -l 100%PVS -n myvolume /dev/sda".format(default_pool), -2)
        self._cmdEq("lvm vgcreate {0} /dev/sda".format(default_pool), -3)

        self._checkCmd("ssm -f create", ['--fstype ext4', '/dev/sda'])
        self._cmdEq("mkfs.ext4 -F /dev/{0}/lvol001".format(default_pool))
        self._cmdEq("lvm lvcreate {0} -l 100%PVS -n lvol001 /dev/sda".format(default_pool), -2)
        self._cmdEq("lvm vgcreate -f {0} /dev/sda".format(default_pool), -3)

        self._checkCmd("ssm -v create", ['--name myvolume', '--fstype xfs', '/dev/sda'])
        self._cmdEq("mkfs.xfs /dev/{0}/myvolume".format(default_pool))
        self._cmdEq("lvm lvcreate -v {0} -l 100%PVS -n myvolume /dev/sda".format(default_pool), -2)
        self._cmdEq("lvm vgcreate -v {0} /dev/sda".format(default_pool), -3)

        self._checkCmd("ssm -v -f create", ['--name myvolume', '--fstype xfs', '/dev/sda'])
        self._cmdEq("mkfs.xfs -f /dev/{0}/myvolume".format(default_pool))
        self._cmdEq("lvm lvcreate -v {0} -l 100%PVS -n myvolume /dev/sda".format(default_pool), -2)
        self._cmdEq("lvm vgcreate -v -f {0} /dev/sda".format(default_pool), -3)

        self._checkCmd("ssm create", ['-s 2.6T', '/dev/sda'],
            "lvm lvcreate {0} -L 2791728742.40K -n lvol001 /dev/sda".format(default_pool))
        self._cmdEq("lvm vgcreate {0} /dev/sda".format(default_pool), -2)

        self._checkCmd("ssm create", ['-r 0', '-s 2.6T', '-I 16', '/dev/sda'],
            "lvm lvcreate {0} -L 2791728742.40K -n lvol001 -I 16 -i 1 /dev/sda".format(default_pool))
        self._cmdEq("lvm vgcreate {0} /dev/sda".format(default_pool), -2)

        self._checkCmd("ssm create", ['-r 0', '-s 2.6T', '-I 16', '/dev/sda'],
            "lvm lvcreate {0} -L 2791728742.40K -n lvol001 -I 16 -i 1 /dev/sda".format(default_pool))
        self._cmdEq("lvm vgcreate {0} /dev/sda".format(default_pool), -2)

        # Number of stripes must not exceed number of devices
        self.assertRaises(problem.GeneralError, main.main, "ssm create -r 0 -s 2.6T -I 16 -i 4 /dev/sda")

        # Create volume using single device from non existent my_pool
        self._checkCmd("ssm create", ['--pool my_pool', '/dev/sda'],
            "lvm lvcreate my_pool -l 100%PVS -n lvol001 /dev/sda")
        self._cmdEq("lvm vgcreate my_pool /dev/sda", -2)

        self._checkCmd("ssm create", ['-r 0', '-p my_pool', '-s 2.6T', '-I 16',
            '-i 2', '/dev/sda /dev/sdb'],
            "lvm lvcreate my_pool -L 2791728742.40K -n lvol001 -I 16 -i 2 /dev/sda /dev/sdb")
        self._cmdEq("lvm vgcreate my_pool /dev/sda /dev/sdb", -2)

        # Create volume using multiple devices
        self._checkCmd("ssm create", ['/dev/sda /dev/sdc1'],
            "lvm lvcreate {0} -l 100%PVS -n lvol001 /dev/sda /dev/sdc1".format(default_pool))
        self._cmdEq("lvm vgcreate {0} /dev/sda /dev/sdc1".format(default_pool), -2)


        # Create volume using single devices from existing pool
        self._addPool(default_pool, ['/dev/sdb', '/dev/sdd'])

        self._checkCmd("ssm create", ['-r 0', '-s 2.6T', '-I 16',
            '-n myvolume', '/dev/sda'],
            "lvm lvcreate {0} -L 2791728742.40K -n myvolume -I 16 -i 1 /dev/sda". format(default_pool))
        self._cmdEq("lvm vgextend {0} /dev/sda".format(default_pool), -2)

        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        self._checkCmd("ssm create", ['-r 0', '-p my_pool', '-s 2.6T', '-I 16',
            '-n myvolume', '/dev/sda'],
            "lvm lvcreate my_pool -L 2791728742.40K -n myvolume -I 16 -i 1 /dev/sda")
        self._cmdEq("lvm vgextend my_pool /dev/sda", -2)

        # Create volume using multiple devices which one of the is in already
        # in the pool
        self._checkCmd("ssm create", ['-n myvolume', '/dev/sda /dev/sdb'],
            "lvm lvcreate {0} -l 100%PVS -n myvolume /dev/sda /dev/sdb". format(default_pool))
        self._cmdEq("lvm vgextend {0} /dev/sda".format(default_pool), -2)

        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        self._checkCmd("ssm create", ['-p my_pool', '-n myvolume', '/dev/sdc2 /dev/sda'],
            "lvm lvcreate my_pool -l 100%PVS -n myvolume /dev/sdc2 /dev/sda")
        self._cmdEq("lvm vgextend my_pool /dev/sda", -2)

        self._checkCmd("ssm create", ['-n myvolume', '/dev/sda /dev/sdb /dev/sde'],
            "lvm lvcreate {0} -l 100%PVS -n myvolume /dev/sda /dev/sdb /dev/sde". format(default_pool))
        self._cmdEq("lvm vgextend {0} /dev/sda /dev/sde".format(default_pool), -2)

    def test_lvm_remove(self):
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
        self._cmdEq("lvm lvremove /dev/default_pool/vol002")
        # remove multiple volumes
        main.main("ssm remove /dev/default_pool/vol002 /dev/default_pool/vol003")
        self.assertEqual(self.run_data[-2], "lvm lvremove /dev/default_pool/vol002")
        self._cmdEq("lvm lvremove /dev/default_pool/vol003")
        # remove pool
        main.main("ssm remove my_pool")
        self._cmdEq("lvm vgremove my_pool")
        # remove multiple pools
        main.main("ssm remove my_pool default_pool")
        self.assertEqual(self.run_data[-2], "lvm vgremove my_pool")
        self._cmdEq("lvm vgremove default_pool")
        # remove device
        main.main("ssm remove /dev/sdc1")
        self._cmdEq("lvm vgreduce my_pool /dev/sdc1")
        # remove multiple devices
        main.main("ssm remove /dev/sdc1 /dev/sdb")
        self.assertEqual(self.run_data[-2], "lvm vgreduce my_pool /dev/sdc1")
        self._cmdEq("lvm vgreduce default_pool /dev/sdb")
        # remove combination
        main.main("ssm remove /dev/sdb my_pool /dev/default_pool/vol001")
        self.assertEqual(self.run_data[-3], "lvm vgreduce default_pool /dev/sdb")
        self.assertEqual(self.run_data[-2], "lvm vgremove my_pool")
        self._cmdEq("lvm lvremove /dev/default_pool/vol001")
        # remove all
        main.main("ssm remove --all")
        self.assertEqual(self.run_data[-2], "lvm vgremove default_pool")
        self._cmdEq("lvm vgremove my_pool")
        # remove force
        main.main("ssm -f remove /dev/default_pool/vol002")
        self._cmdEq("lvm lvremove -f /dev/default_pool/vol002")
        # remove verbose
        main.main("ssm -v remove /dev/default_pool/vol002")
        self._cmdEq("lvm lvremove -v /dev/default_pool/vol002")
        # remove verbose + force
        main.main("ssm -v -f remove /dev/default_pool/vol002")
        self._cmdEq("lvm lvremove -v -f /dev/default_pool/vol002")

    def test_lvm_snapshot(self):
        # Generate some storage data
        self._addPool('default_pool', ['/dev/sda', '/dev/sdb'])
        self._addPool('my_pool', ['/dev/sdc2', '/dev/sdc3', '/dev/sdc1'])
        self._addVol('vol001', 117283225, 1, 'default_pool', ['/dev/sda'])
        self._addVol('vol002', 237284225, 1, 'default_pool', ['/dev/sda'],
                    '/mnt/mount1')
        self._addVol('vol003', 1024, 1, 'default_pool', ['/dev/sdd'])
        self._addVol('vol004', 209715200, 2, 'default_pool', ['/dev/sda',
                     '/dev/sdb'], '/mnt/mount')

        # Create snapshot
        self._checkCmd("ssm snapshot --name new_snap", ['/dev/default_pool/vol001'],
            "lvm lvcreate --size 23456645.0K --snapshot --name new_snap /dev/default_pool/vol001")

        main.SSM_DEFAULT_BACKEND = "btrfs"
        self._checkCmd("ssm snapshot --name new_snap", ['/dev/default_pool/vol001'],
            "lvm lvcreate --size 23456645.0K --snapshot --name new_snap /dev/default_pool/vol001")
        main.SSM_DEFAULT_BACKEND = "lvm"

        # Create snapshot verbose
        self._checkCmd("ssm -v snapshot --name new_snap", ['/dev/default_pool/vol001'],
            "lvm lvcreate -v --size 23456645.0K --snapshot --name new_snap /dev/default_pool/vol001")
        # Create snapshot force
        self._checkCmd("ssm -f snapshot --name new_snap", ['/dev/default_pool/vol001'],
            "lvm lvcreate -f --size 23456645.0K --snapshot --name new_snap /dev/default_pool/vol001")
        # Create snapshot force verbose
        self._checkCmd("ssm -f -v snapshot --name new_snap", ['/dev/default_pool/vol001'],
            "lvm lvcreate -v -f --size 23456645.0K --snapshot --name new_snap /dev/default_pool/vol001")

        # Create snapshot with size and name specified
        self._checkCmd("ssm snapshot", ['--size 1G', '--name new_snap',
                                        '/dev/default_pool/vol001'],
            "lvm lvcreate --size 1048576.0K --snapshot --name new_snap /dev/default_pool/vol001")

    def test_lvm_resize(self):
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
            "lvm lvresize -L 5120.0k /dev/default_pool/vol003")

        # Specify backend
        self._checkCmd("ssm --backend lvm resize", ['--size +4m', '/dev/default_pool/vol003'],
            "lvm lvresize -L 5120.0k /dev/default_pool/vol003")

        main.SSM_DEFAULT_BACKEND = "btrfs"
        self._checkCmd("ssm resize", ['--size +4m', '/dev/default_pool/vol003'],
            "lvm lvresize -L 5120.0k /dev/default_pool/vol003")
        main.SSM_DEFAULT_BACKEND = "lvm"

        # Shrink volume
        self._checkCmd("ssm resize", ['-s-100G', '/dev/default_pool/vol002'],
            "lvm lvresize -L 132426625.0k /dev/default_pool/vol002")

        # Set volume size
        self._checkCmd("ssm resize", ['-s 10M', '/dev/my_pool/vol001'],
            "lvm lvresize -L 10240.0k /dev/my_pool/vol001")

        # Set volume and add devices
        self._checkCmd("ssm resize -s 12T /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "lvm lvresize -L 12884901888.0k /dev/default_pool/vol003")
        self.assertEqual(self.run_data[-2],
            "lvm vgextend default_pool /dev/sdc1 /dev/sde")

        # Set volume size with sufficient amount of space
        self._checkCmd("ssm resize -s 10G /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "lvm lvresize -L 10485760.0k /dev/default_pool/vol003")
        self.assertNotEqual(self.run_data[-2],
            "lvm vgextend default_pool /dev/sdc1 /dev/sde")

        # Set volume size without sufficient amount of space
        self._checkCmd("ssm resize -s 10T /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "lvm lvresize -L 10737418240.0k /dev/default_pool/vol003")
        self.assertNotEqual(self.run_data[-2],
            "lvm vgextend default_pool /dev/sdc1 /dev/sde")

        # Extend volume and add devices
        self._checkCmd("ssm resize -s +11T /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "lvm lvresize -L 11811161088.0k /dev/default_pool/vol003")
        self.assertEqual(self.run_data[-2],
            "lvm vgextend default_pool /dev/sdc1 /dev/sde")

        # Extend volume with ehough space in pool
        self._checkCmd("ssm resize -s +10G /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "lvm lvresize -L 10486784.0k /dev/default_pool/vol003")
        self.assertNotEqual(self.run_data[-2],
            "lvm vgextend default_pool /dev/sdc1 /dev/sde")

        # Extend volume without ehough space in pool
        self._checkCmd("ssm resize -s +20T /dev/default_pool/vol003 /dev/sdc1 /dev/sde",
            [], "lvm lvresize -L 21474837504.0k /dev/default_pool/vol003")
        self.assertEqual(self.run_data[-2],
            "lvm vgextend default_pool /dev/sdc1 /dev/sde")

        # Shrink volume with devices provided
        self._checkCmd("ssm resize -s-10G /dev/default_pool/vol002 /dev/sdc1 /dev/sde",
            [], "lvm lvresize -L 226798465.0k /dev/default_pool/vol002")
        self.assertNotEqual(self.run_data[-2],
            "lvm vgextend default_pool /dev/sdc1 /dev/sde")

        # Test that we do not use devices which are already used in different
        # pool
        self.assertRaises(Exception, main.main, "ssm resize -s +1.5T /dev/my_pool/vol001 /dev/sdb /dev/sda")

        # If the device we are able to use can cover the size, then
        # it will be resized successfully
        self._checkCmd("ssm resize -s +1.5T /dev/my_pool/vol001 /dev/sdb /dev/sda /dev/sdc1",
            [], "lvm lvresize -L 1613595352.0k /dev/my_pool/vol001")

        # Test resize on inactive volume
        self._addVol('vol004', 8192, 1, 'default_pool', ['/dev/sdd'], None, False)
        self._checkCmd("ssm resize", ['--size +4m', '/dev/default_pool/vol004'],
            "lvm lvresize -L 12288.0k /dev/default_pool/vol004")
        self.assertRaises(Exception, main.main, "ssm resize -s-2m /dev/default_pool/vol004")
        # We can force it though
        self._checkCmd("ssm -f resize", ['-s-2m', '/dev/default_pool/vol004'],
            "lvm lvresize -f -L 6144.0k /dev/default_pool/vol004")

    def test_lvm_add(self):
        default_pool = lvm.SSM_LVM_DEFAULT_POOL

        # Adding to non existent pool
        # Add device into default pool
        self._checkCmd("ssm add", ['/dev/sda'],
            "lvm vgcreate {0} /dev/sda".format(default_pool))

        # Specify backend
        self._checkCmd("ssm --backend lvm add", ['/dev/sda'],
            "lvm vgcreate {0} /dev/sda".format(default_pool))

        main.SSM_DEFAULT_BACKEND = "btrfs"
        self._checkCmd("ssm --backend lvm add", ['/dev/sda'],
            "lvm vgcreate {0} /dev/sda".format(default_pool))
        main.SSM_DEFAULT_BACKEND = "lvm"

        # Add more devices into default pool
        self._checkCmd("ssm add", ['/dev/sda /dev/sdc1'],
            "lvm vgcreate {0} /dev/sda /dev/sdc1".format(default_pool))
        # Add device into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda'],
            "lvm vgcreate my_pool /dev/sda")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda'],
            "lvm vgcreate my_pool /dev/sda")
        # Add more devices into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda /dev/sdc1'],
            "lvm vgcreate my_pool /dev/sda /dev/sdc1")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda /dev/sdc1'],
            "lvm vgcreate my_pool /dev/sda /dev/sdc1")
        # Add force
        self._checkCmd("ssm -f add", ['--pool my_pool', '/dev/sda'],
            "lvm vgcreate -f my_pool /dev/sda")
        # Add verbose
        self._checkCmd("ssm -v add", ['--pool my_pool', '/dev/sda'],
            "lvm vgcreate -v my_pool /dev/sda")
        # Add force and verbose
        self._checkCmd("ssm -v -f add", ['--pool my_pool', '/dev/sda'],
            "lvm vgcreate -v -f my_pool /dev/sda")

        # Adding to existing default pool
        self._addPool(default_pool, ['/dev/sdb', '/dev/sdd'])
        # Add device into default pool
        self._checkCmd("ssm add", ['/dev/sda'],
            "lvm vgextend {0} /dev/sda".format(default_pool))
        # Add more devices into default pool
        self._checkCmd("ssm add", ['/dev/sda /dev/sdc1'],
            "lvm vgextend {0} /dev/sda /dev/sdc1".format(default_pool))

        # Adding to existing defined pool
        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        # Add device into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda'],
            "lvm vgextend my_pool /dev/sda")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda'],
            "lvm vgextend my_pool /dev/sda")
        # Add more devices into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda /dev/sdc1'],
            "lvm vgextend my_pool /dev/sda /dev/sdc1")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda /dev/sdc1'],
            "lvm vgextend my_pool /dev/sda /dev/sdc1")
        # Add force
        self._checkCmd("ssm -f add", ['--pool my_pool', '/dev/sda'],
            "lvm vgextend -f my_pool /dev/sda")
        # Add verbose
        self._checkCmd("ssm -v add", ['--pool my_pool', '/dev/sda'],
            "lvm vgextend -v my_pool /dev/sda")
        # Add force and verbose
        self._checkCmd("ssm -v -f add", ['--pool my_pool', '/dev/sda'],
            "lvm vgextend -v -f my_pool /dev/sda")

        # Add two devices into existing pool (one of the devices already is in
        # the pool
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sdc2 /dev/sda'],
            "lvm vgextend my_pool /dev/sda")
        self._checkCmd("ssm add", ['/dev/sda /dev/sdb'],
            "lvm vgextend {0} /dev/sda".format(default_pool))

    def test_lvm_mount(self):
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
