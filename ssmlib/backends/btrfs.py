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
from ssmlib import problem

__all__ = ["BtrfsVolume", "BtrfsPool", "BtrfsDev"]

try:
    SSM_BTRFS_DEFAULT_POOL = os.environ['SSM_BTRFS_DEFAULT_POOL']
except KeyError:
    SSM_BTRFS_DEFAULT_POOL = "btrfs_pool"


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

    def __init__(self, options, data=None):
        self.type = 'btrfs'
        self.data = data or {}
        self.options = options
        self.default_pool_name = SSM_BTRFS_DEFAULT_POOL
        self._vol = {}
        self._pool = {}
        self._dev = {}
        self._snap = {}
        self._subvolumes = {}
        self._binary = misc.check_binary('btrfs')
        self.problem = problem.ProblemSet(options)

        if not self._binary:
            return

        self.mounts = misc.get_mounts('/dev/')
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
                pool['uuid'] = vol['uuid'] = uuid

                try:
                    fallback = False
                    vol['real_dev'] = misc.get_device_by_uuid(uuid)

                    if vol['real_dev'] in self.mounts:
                        pool['mount'] = self.mounts[vol['real_dev']]['mp']
                        vol['mount'] = self.mounts[vol['real_dev']]['mp']
                    else:
                        for dev_i in self.mounts:
                            found = re.findall(r'{0}:/.*'.format(vol['real_dev']), dev_i)
                            if found:
                                pool['mount'] = self.mounts[found[0]]['mp']
                                break
                except OSError:
                    # udev is "hard-to-work-with" sometimes so this is fallback
                    fallback = True
                    vol['real_dev'] = ""

                if label != 'none':
                    vol['label'] = label
                vol['ID'] = 0

            elif array[0] == 'Total':
                pool['dev_count'] = array[2]
                fs_used = get_real_number(array[6])

            elif array[0] == 'devid':
                dev['dev_name'] = array[7]

                if not pool_name:
                    pool_name = self._find_uniq_pool_name(label, array[7])
                dev['pool_name'] = pool_name

                # Fallback in case we could not find real_dev by uuid
                if fallback and 'mount' not in pool:
                    if dev['dev_name'] in self.mounts:
                        pool['mount'] = self.mounts[dev['dev_name']]['mp']
                        vol['real_dev'] = dev['dev_name']

                        if 'root' in self.mounts[dev['dev_name']]:
                            if self.mounts[dev['dev_name']]['root'] == '/':
                                vol['mount'] = self.mounts[dev['dev_name']]['mp']
                    else:
                        for dev_i in self.mounts:
                            found = re.findall(r'{0}:/.*'.format(dev['dev_name']), dev_i)
                            if found:
                                pool['mount'] = self.mounts[found[0]]['mp']
                                break

                dev_used = get_real_number(array[5])
                dev['dev_used'] = str(dev_used)
                fs_size += get_real_number(array[3])

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
            self.problem.check(self.problem.TOOL_MISSING, 'btrfs')
        command.insert(0, "btrfs")
        return misc.run(command, stdout=True)

    def _fill_subvolumes(self):
        if not self._binary:
            return
        if self._subvolumes:
            return
        command = ['btrfs', 'subvolume', 'list']
        for name, vol in self._vol.iteritems():
            pool_name = vol['pool_name']
            real_dev = vol['real_dev']
            pool = self._pool[pool_name]

            if 'mount' in self._pool[pool_name]:
                mount = pool['mount']
            else:
                # If btrfs is not mounted we will not process subvolumes
                continue

            output = misc.run(command + [mount], stdout=False)[1]
            for volume in self._parse_subvolumes(output):
                new = vol.copy()
                new.update(volume)
                new['dev_name'] = "{0}:{1}".format(name, new['path'])
                item = "{0}:/{1}".format(real_dev, new['path'])
                # If the subvolume is mounted we should find it here
                if item in self.mounts:
                    new['mount'] = self.mounts[item]['mp']
                else:
                    # If subvolume is not mounted try to find whether parent
                    # subvolume is mounted
                    found = re.findall(r'^(.*)/([^/]*)$', new['path'])
                    if found:
                        parent_path, path = found[0]
                        # try previously loaded subvolumes
                        for prev_sv in self._subvolumes:
                            # if subvolumes are mounted, use that mp
                            if self._subvolumes[prev_sv]['path'] == parent_path:
                                # if parent subvolume is not mounted this
                                # subvolume is not mounted as well
                                if self._subvolumes[prev_sv]['mount'] == '':
                                    new['mount'] = ''
                                else:
                                    new['mount'] = "{0}/{1}".format(
                                        self._subvolumes[prev_sv]['mount'], path)
                                break
                    # if parent volume is not mounted, use root subvolume
                    # if mounted
                    else:
                        if 'mount' in vol:
                            new['mount'] = "{0}/{1}".format(vol['mount'],
                                new['path'])

                new['hide'] = False
                # Store snapshot info
                if 'mount' in new and \
                    re.match("snap-\d{4}-\d{2}-\d{2}-T\d{6}",
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
            volume['ID'] = re.search('(?<=ID )\d+', line).group(0)
            volume['top_level'] = re.search('(?<=top level )\d+', line).group(0)
            volume['path'] = re.search('(?<=path ).*$', line).group(0)
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
        pool['pool_free'] = str(pool_size - fs_used)
        pool['pool_size'] = pool_size
        pool['pool_name'] = vol['pool_name'] = vol['dev_name'] = pool_name
        pool['type'] = 'btrfs'
        vol['type'] = 'btrfs'

        # Just to be sure that the pool is set if needed. This is mostly for
        # the sake of unittests
        if 'mount' in pool and 'mount' not in vol:
            vol['mount'] = pool['mount']

        self._pool[pool['pool_name']] = pool
        self._vol[vol['dev_name']] = vol

    def __iter__(self):
        for item in sorted(self.data.iterkeys()):
            yield item

    def __getitem__(self, key):
        if key in self.data.iterkeys():
            return self.data[key]

    def _remove_filesystem(self, name):
        if 'mount' in self._vol[name]:
            if self.problem.check(self.problem.FS_MOUNTED,
                    [name, self._vol[name]['mount']]):
                misc.do_umount(self._vol[name]['mount'])
        for dev in self._dev.itervalues():
            if dev['pool_name'] != name:
                continue
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

    def mount(self, vol, mpoint, options=None):
        if options is None:
            options = []
        vol = self.data[vol]
        options.append('subvolid={0}'.format(vol['ID']))
        misc.do_mount(vol['real_dev'], mpoint, options)

    def remove(self, vol):
        if 'subvolume' in self._vol[vol]:
            self.run_btrfs(['subvolume', 'delete', self._vol[vol]['mount']])
        else:
            self._remove_filesystem(vol)

    def resize(self, vol, size, resize_fs=True):
        vol = self.data[vol]
        if 'mount' not in vol:
            tmp = misc.temp_mount("UUID={0}".format(vol['uuid']))
            vol['mount'] = tmp
        command = ['filesystem', 'resize', str(int(size)) + "K", vol['mount']]
        self.run_btrfs(command)

    def snapshot(self, vol, destination, name, size, user_set_size):
        vol = self.data[vol]
        if 'mount' not in vol:
            tmp = misc.temp_mount("UUID={0}".format(vol['uuid']))
            vol['mount'] = tmp

        if not destination and not name:
            now = datetime.datetime.now()
            destination = vol['mount'] + now.strftime("/snap-%Y-%m-%d-T%H%M%S")
        if name:
            destination = vol['mount'] + "/" + name

        if user_set_size:
            self.problem.warn("Btrfs doesn't allow setting a size of " + \
                              "subvolumes")

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

    def _create_filesystem(self, pool, name, devs, size=None, raid=None):
        if not devs:
            raise Exception("To create btrfs volume, some devices must be " + \
                            "provided")
        self._binary = misc.check_binary('mkfs.btrfs')
        if not self._binary:
            self.problem.check(self.problem.TOOL_MISSING, 'mkfs.btrfs')
        command = ['mkfs.btrfs', '-L', name]

        if raid:
            if raid['level'] == '0':
                command.extend(['-m', 'raid0', '-d', 'raid0'])
            elif raid['level'] == '1':
                command.extend(['-m', 'raid1', '-d', 'raid1'])
            elif raid['level'] == '10':
                command.extend(['-m', 'raid10', '-d', 'raid10'])
            else:
                raise Exception("Btrfs backed currently does not support " + \
                                "RAID level {0}".format(raid['level']))

        if size:
            command.extend(['-b', "{0}".format(int(float(size) * 1024))])
        command.extend(devs)
        misc.run(command, stdout=True)
        misc.send_udev_event(devs[0], "change")
        return name

    def reduce(self, pool, device):
        pool = self.data[pool]
        if 'mount' not in pool:
            tmp = misc.temp_mount("UUID={0}".format(pool['uuid']))
            pool['mount'] = tmp
        command = ['device', 'delete', device, pool['mount']]
        self.run_btrfs(command)

    def new(self, pool, devices):
        if type(devices) is not list:
            devices = [devices]
        self.create(pool, devs=devices)

    def extend(self, pool, devices):
        pool = self.data[pool]
        if 'mount' not in pool:
            tmp = misc.temp_mount("UUID={0}".format(pool['uuid']))
            pool['mount'] = tmp
        if type(devices) is not list:
            devices = [devices]
        command = ['device', 'add']
        command.extend(devices)
        command.append(pool['mount'])
        self.run_btrfs(command)

    def remove(self, pool):
        # Volume and pool name should be the same, since it actually is the
        # same file system
        self._remove_filesystem(pool)

    def create(self, pool, size=None, name=None, devs=None,
            raid=None):
        if pool in self._pool:
            vol = None
            if size or raid:
                self.problem.warn("Only name, volume name and pool name " + \
                                  "can be specified when creating btrfs " + \
                                  "subvolume, the rest will be ignored")
            tmp = misc.temp_mount(
                    "UUID={0}".format(self._pool[pool]['uuid']))
            self._pool[pool]['mount'] = tmp

            if not name:
                now = datetime.datetime.now()
                name = now.strftime("%Y-%m-%d-T%H%M%S")
                vol = "{0}/{1}".format(self._pool[pool]['mount'], name)
            elif os.path.isabs(name):
                vol = name
            else:
                vol = "{0}/{1}".format(self._pool[pool]['mount'], name)
            self.run_btrfs(['subvolume', 'create', vol])
            vol = "{0}:{1}".format(pool, name)
        else:
            if len(devs) == 0:
                self.problem.check(self.problem.NO_DEVICES, pool)
            if name:
                self.problem.warn("Creating new pool. Argument (--name " + \
                                  "{0}) will be ignored!".format(name))
            vol = self._create_filesystem(pool, pool, devs, size, raid)
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
