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

# btrfs module for System Storage Manager

import re
import os
import sys
import datetime
from ssmlib import misc

__all__ = ["BtrfsVolume", "BtrfsPool", "BtrfsDev"]


def get_real_number(string):
    number = float(string[0:-2])
    unit = string[-2:-1]
    # The result will be in kilobytes
    units = ["K", "M", "G", "T", "P", "E", "Z", "Y"]
    for i, u in enumerate(units):
        if u == unit:
            number *= (2 ** (i * 10))
            break
    return number


class Btrfs(object):

    def __init__(self, data=None, force=False, verbose=False, yes=False):
        self.data = data or {}
        self.force = force
        self.verbose = verbose
        self.yes = yes
        self._vol = {}
        self._pool = {}
        self._dev = {}
        self._snap = {}
        self._subvolumes = {}
        self._binary = misc.check_binary('btrfs')

        if not self._binary:
            return

        self.mounts = misc.get_mounts('^/dev/')
        command = ['btrfs', 'filesystem', 'show']
        self.output = misc.run(command, stderr=False)[1]

        vol = {}
        pool = {}
        dev = {}
        partitions = {}
        fs_size = pool_size = fs_used = 0
        pool_name = ''
        for line in misc.get_partitions():
            partitions[line[3]] = line

        for line in self.output.strip().split("\n"):
            if not line:
                continue
            array = line.split()

            if array[0] == 'Label:':
                if len(vol) > 0:
                    self._store_data(vol, pool, fs_used, fs_size, pool_size,
                            pool_name)
                    vol = {}
                    pool = {}
                    fs_size = pool_size = 0
                    pool_name = ''

                label = array[1].strip("'")
                uuid = array[3]
                pool['uuid'] = uuid

                if label != 'none':
                    vol['label'] = label

            elif array[0] == 'Total':
                pool['dev_count'] = array[2]
                fs_used = get_real_number(array[6])

            elif array[0] == 'devid':
                if 'real_dev' not in vol:
                    vol['real_dev'] = array[7]
                dev['dev_name'] = array[7]

                if not pool_name:
                    pool_name = self._find_uniq_pool_name(label, array[7])
                dev['pool_name'] = pool_name

                dev_used = get_real_number(array[5])
                dev['dev_used'] = str(dev_used)
                fs_size += get_real_number(array[3])

                if dev['dev_name'] in self.mounts:
                    vol['mount'] = self.mounts[dev['dev_name']]
                    pool['mount'] = vol['mount']

                dev_size = \
                    int(partitions[dev['dev_name'].rpartition("/")[-1]][2])
                pool_size += dev_size
                dev['dev_free'] = dev_size - dev_used
                self._dev[dev['dev_name']] = dev
                dev = {}

        if len(vol) > 0:
            self._store_data(vol, pool, fs_used, fs_size, pool_size, pool_name)

    def run_btrfs(self, command):
        if not self._binary:
            raise Exception("ERROR: Btrfs is not installed on the system!")
        command.insert(0, "btrfs")
        misc.run(command, stdout=True)

    def _fill_subvolumes(self):
        if not self._binary:
            return
        if self._subvolumes:
            return
        command = ['btrfs', 'subvolume', 'list']
        for name, vol in self._vol.iteritems():
            if 'mount' in vol:
                output = misc.run(command + [vol['mount']], stdout=False)[1]
                for volume in self._parse_subvolumes(output):
                    new = volume.copy()
                    new.update(vol)
                    new['dev_name'] = "{0}:{1}".format(name, new['path'])
                    new['mount'] = "{0}/{1}".format(vol['mount'],
                            new['path'])

                    new['hide'] = False
                    # Store snapshot info
                    if re.match("snap-\d{4}-\d{2}-\d{2}-T\d{6}",
                            os.path.basename(new['mount'])):
                        new['hide'] = True
                        new['snap_name'] = new['dev_name']
                        new['snap_name'] = "{0}:{1}".format(name,
                                os.path.basename(new['path']))
                        new['snap_path'] = new['mount']

                    self._subvolumes[new['dev_name']] = new

    def _parse_subvolumes(self, output):
        volume = {}
        for line in output.strip().split("\n"):
            if not line:
                continue
            array = line.split()
            volume['ID'] = array[1]
            volume['top_level'] = array[4]
            volume['path'] = array[6]
            volume['subvolume'] = True
            yield volume

    def _find_uniq_pool_name(self, label, dev):
        if len(label) < 3 or label == "none":
            label = "btrfs_{0}".format(os.path.basename(dev))
        if label not in self._pool:
            return label
        return os.path.basename(dev)

    def _store_data(self, vol, pool, fs_used, fs_size, pool_size, pool_name):
        vol['fs_type'] = 'btrfs'
        vol['fs_used'] = str(fs_used)
        vol['fs_free'] = str(fs_size - fs_used)
        vol['fs_size'] = vol['vol_size'] = pool['pool_used'] = \
            str(fs_size)
        pool['pool_free'] = str(pool_size - fs_size)
        pool['pool_size'] = pool_size
        pool['pool_name'] = vol['pool_name'] = vol['dev_name'] = pool_name
        pool['type'] = 'btrfs'
        vol['type'] = 'btrfs'

        self._pool[pool['pool_name']] = pool
        self._vol[vol['dev_name']] = vol

    def __iter__(self):
        for item in sorted(self.data.iterkeys()):
            yield item

    def __getitem__(self, key):
        if key in self.data.iterkeys():
            return self.data[key]

    def _remove_filesystem(self, name):
        for dev in self._dev.itervalues():
            if dev['pool_name'] != name:
                continue
            if 'mount' in self._vol[name]:
                print >> sys.stderr, "'{0}' is mounted!".format(name)
                return
            misc.wipefs(dev['dev_name'], 'btrfs')


class BtrfsVolume(Btrfs):

    def __init__(self, *args, **kwargs):
        super(BtrfsVolume, self).__init__(*args, **kwargs)
        self._fill_subvolumes()
        if self.data:
            self.data.update(self._vol)
            self.data.update(self._subvolumes)
        else:
            self.data = self._vol
            self.data.update(self._subvolumes)

    def remove(self, vol):
        # Volume and pool name should be the same, since it actually is the
        # same file system
        if 'subvolume' in self._vol[vol]:
            self.run_btrfs(['subvolume', 'delete', self._vol[vol]['mount']])
        else:
            self._remove_filesystem(vol)

    def resize(self, vol, size, resize_fs=True):
        vol = self.data[vol]
        if 'mount' not in vol:
            raise Exception("Btrfs pool can be reduced only when mounted!")
        command = ['filesystem', 'resize', str(int(size)) + "K", vol['mount']]
        self.run_btrfs(command)

    def snapshot(self, vol, destination, size, user_set_size):
        vol = self.data[vol]
        if 'mount' not in vol:
            raise Exception("Btrfs volume can be snapshotted only when mounted!")

        if not destination:
            now = datetime.datetime.now()
            destination = vol['mount'] + now.strftime("/snap-%Y-%m-%d-T%H%M%S")

        if user_set_size:
            print "Warning: Btrfs doesn't allow setting a size of a subvolume"

        command = ['subvolume', 'snapshot', vol['mount'], destination]
        self.run_btrfs(command)


class BtrfsDev(Btrfs):

    def __init__(self, *args, **kwargs):
        super(BtrfsDev, self).__init__(*args, **kwargs)
        if self.data:
            self.data.update(self._dev)
        else:
            self.data = self._dev

    def remove(self, devices):
        raise Exception("Not sure what you want to" + \
                        "achieve by removing {0}".format(devices))


class BtrfsPool(Btrfs):

    def __init__(self, *args, **kwargs):
        super(BtrfsPool, self).__init__(*args, **kwargs)
        if self.data:
            self.data.update(self._pool)
        else:
            self.data = self._pool

    def _create_filesystem(self, pool, size=None, name=None, devs=None,
                           stripes=None, stripesize=None):
        if not devs:
            raise Exception("To create btrfs volume, some devices must be " + \
                            "provided")
        command = ['mkfs.btrfs', '-L', name]
        if size:
            command.extend(['-b', str(float(size) * 1024)])
        command.extend(devs)
        print command
        misc.run(command, stdout=True)
        return devs[0]

    def reduce(self, pool, device):
        pool = self.data[pool]
        if 'mount' not in pool:
            raise Exception("Btrfs pool can be reduced only when mounted!")
        command = ['device', 'delete', device, pool['mount']]
        self.run_btrfs(command)

    def new(self, pool, devices):
        if type(devices) is not list:
            devices = [devices]
        print "new {0} with {1}".format(pool, devices)

    def extend(self, pool, devices):
        pool = self.data[pool]
        if 'mount' not in pool:
            raise Exception("Btrfs pool can be extended only when mounted!")
        if type(devices) is not list:
            devices = [devices]
        command = ['device', 'add']
        command.extend(devices)
        command.append(pool['mount'])
        self.run_btrfs(command)

    def remove(self, pool):
        # Volume and pool name should be the same, since it actually is the
        # same file system
        print  "Removing pool ", pool
        self._remove_filesystem(pool)

    def create(self, pool, size=None, name=None, devs=None,
            stripes=None, stripesize=None):
        if pool in self._pool:
            vol = None
            if size or devs or stripes or stripesize:
                print >> sys.stderr, "Only name, volume name and pool" + \
                    "name can be specified when creating btrfs subvolume, " + \
                    "the rest will be ignored"
            if 'mount' not in self._pool[pool]:
                raise Exception("Can not create btrfs subvolume on " + \
                        "umounted file system. Please mount it first!")

            if not name:
                now = datetime.datetime.now()
                name = now.strftime("%Y-%m-%d-T%H%M%S")
                vol = "{0}/{1}".format(self._pool[pool]['mount'], name)
            elif os.path.isabs(name):
                vol = name
            else:
                vol = "{0}/{1}".format(self._pool[pool]['mount'], name)
            self.run_btrfs(['subvolume', 'create', vol])
        else:
            vol = self._create_filesystem(pool, size, name, devs,
                                          stripes, stripesize)
        return vol


class BtrfsSnap(Btrfs):

    def __init__(self, *args, **kwargs):
        super(BtrfsSnap, self).__init__(*args, **kwargs)

        self._fill_subvolumes()
        for name, vol in self._subvolumes.iteritems():
            if 'snap_name' in vol:
                self._snap[vol['snap_name']] = vol.copy()
                self._snap[vol['snap_name']]['hide'] = False

        if self.data:
            self.data.update(self._snap)
        else:
            self.data = self._snap
