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

    def mock_run(self, cmd, *args, **kwargs):
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
                output += "{0}|{1}|{2}|{3}|{4}|{5}\n".format(data['pool_name'],
                        data['vol_size'], data['stripes'], data['stripesize'],
                        data['type'], data['dev_name'])
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output)

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

        #main.main("ssm list")
