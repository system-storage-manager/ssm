#!/usr/bin/env python
#
# (C)2012 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
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

# Unittests for the system storage manager btrfs backend


import unittest
from ssmlib import main
from ssmlib.backends import btrfs
from tests.unittests.common import *

class BtrfsFunctionCheck(MockSystemDataSource):

    def setUp(self):
        super(BtrfsFunctionCheck, self).setUp()
        self._addDevice('/dev/sda', 11489037516)
        self._addDevice('/dev/sdb', 234566451)
        self._addDevice('/dev/sdc', 2684354560)
        self._addDevice('/dev/sdc1', 894784853, 1)
        self._addDevice('/dev/sdc2', 29826161, 2)
        self._addDevice('/dev/sdc3', 1042177280, 3)
        self._addDevice('/dev/sdd', 11673)
        self._addDevice('/dev/sde', 1042177280)
        main.SSM_DEFAULT_BACKEND = 'btrfs'

    def mock_run(self, cmd, *args, **kwargs):
        self.run_data.append(" ".join(cmd))
        output = ""
        if cmd[:3] == ['btrfs', 'filesystem', 'show']:
            for pool, p_data in self.pool_data.iteritems():
                output += "Label: {0} uuid: some_random_uuid\n".format(pool)
                count = 0
                d_output = ""
                for dev, d_data in self.dev_data.iteritems():
                    if 'pool_name' not in d_data or \
                       d_data['pool_name'] != pool:
                           continue
                    count += 1
                    d_output += " devid {0} size {1} used {2} path {3}\n".format(
                            count, d_data['dev_size'], d_data['dev_used'], dev)
                output += " Total devices {0} FS bytes used 44.00KB\n".format(count)
                output += d_output
        elif cmd[:3] == ['btrfs', 'subvolume', 'list']:
            mpoint = cmd[3]
            for pool, p_data in self.pool_data.iteritems():
                if p_data['mount'] != mpoint:
                    continue
                count = 0
                for vol, v_data in self.vol_data.iteritems():
                    if v_data['pool_name'] != pool:
                        continue
                    count += 1
                    output += "ID {0} top level 5 path {1}\n".format(count,
                              v_data['dev_name'])
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output)

    def test_btrfs_create(self):
        default_pool = btrfs.SSM_BTRFS_DEFAULT_POOL

        # Create volume using single device from non existent default pool
        self._checkCmd("ssm create", ['/dev/sda'],
            "mkfs.btrfs -L {0} /dev/sda".format(default_pool))

        self._checkCmd("ssm -f create", ['/dev/sda'],
            "mkfs.btrfs -L {0} /dev/sda".format(default_pool))

        self._checkCmd("ssm -v create", ['/dev/sda'],
            "mkfs.btrfs -L {0} /dev/sda".format(default_pool))

        self._checkCmd("ssm -f -v create", ['/dev/sda'],
            "mkfs.btrfs -L {0} /dev/sda".format(default_pool))

        self._checkCmd("ssm create", ['-s 2.6T', '/dev/sda'],
            "mkfs.btrfs -L {0} -b 2858730232217 /dev/sda".format(default_pool))

        self._checkCmd("ssm create", ['-r 0', '-s 2.6T', '/dev/sda'],
            "mkfs.btrfs -L btrfs_pool -m raid0 -d raid0 -b 2858730232217 /dev/sda".format(default_pool))
        self._checkCmd("ssm create", ['-r 0', '-s 2.6T', '/dev/sda'],
            "mkfs.btrfs -L btrfs_pool -m raid0 -d raid0 -b 2858730232217 /dev/sda".format(default_pool))
        self._checkCmd("ssm create", ['-r 1', '-s 512k', '/dev/sda'],
            "mkfs.btrfs -L btrfs_pool -m raid1 -d raid1 -b 524288 /dev/sda".format(default_pool))
        self._checkCmd("ssm create", ['-r 10', '-s 10M', '/dev/sda'],
            "mkfs.btrfs -L btrfs_pool -m raid10 -d raid10 -b 10485760 /dev/sda".format(default_pool))

        # Create volume using single device from non existent my_pool
        self._checkCmd("ssm create", ['--pool my_pool', '/dev/sda'],
            "mkfs.btrfs -L my_pool /dev/sda")

        self._checkCmd("ssm create", ['-p my_pool', '-r 0', '-s 2.6T', '/dev/sda'],
            "mkfs.btrfs -L my_pool -m raid0 -d raid0 -b 2858730232217 /dev/sda")

        # Create volume using multiple devices
        self._checkCmd("ssm create /dev/sda /dev/sdb", [],
            "mkfs.btrfs -L {0} /dev/sda /dev/sdb".format(default_pool))

        # Create volume using single device from existing pool
        self._addPool(default_pool, ['/dev/sdb', '/dev/sdd'])
        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        self._checkCmd("ssm create", ['-n myvolume'],
            "btrfs subvolume create /tmp/mount/myvolume")

        self._checkCmd("ssm create", ['-p my_pool', '-n myvolume'],
            "btrfs subvolume create /tmp/mount/myvolume")

        self._addVol('vol002', 1172832, 1, 'my_pool', ['/dev/sdc2'], '/mnt/test')
        self._checkCmd("ssm create", ['-p my_pool', '-n myvolume'],
            "btrfs subvolume create /mnt/test/myvolume")

        # Create volume using multiple devices which one of the is in already
        # in the pool
        self._checkCmd("ssm create", ['-n myvolume', '/dev/sda /dev/sdb'],
            "btrfs subvolume create /tmp/mount/myvolume")
        self._cmdEq("btrfs device add /dev/sda /tmp/mount", -2)

        self._checkCmd("ssm create", ['-p my_pool', '-n myvolume', '/dev/sdc2 /dev/sda'],
            "btrfs subvolume create /mnt/test/myvolume")
        self._cmdEq("btrfs device add /dev/sda /mnt/test", -2)

        self._checkCmd("ssm create", ['-n myvolume', '/dev/sda /dev/sdb /dev/sde'],
            "btrfs subvolume create /tmp/mount/myvolume")
        self._cmdEq("btrfs device add /dev/sda /dev/sde /tmp/mount", -2)
