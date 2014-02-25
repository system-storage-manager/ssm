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
import datetime
from ssmlib import misc
from ssmlib.backends import template

__all__ = ["BtrfsVolume", "BtrfsPool", "BtrfsDev"]

try:
    SSM_BTRFS_DEFAULT_POOL = os.environ['SSM_BTRFS_DEFAULT_POOL']
except KeyError:
    SSM_BTRFS_DEFAULT_POOL = "btrfs_pool"


def get_btrfs_version():
    try:
        output = misc.run(['btrfs', '--version'], can_fail=True)[1]
        output = output.strip().split("\n")[-1]
        version = re.search(r'(?<=v)\d+\.\d+', output).group(0)
    except (OSError, AttributeError):
        version = "0.0"
    return float(version)

BTRFS_VERSION = get_btrfs_version()


class Btrfs(template.Backend):

    def __init__(self, *args, **kwargs):
        super(Btrfs, self).__init__(*args, **kwargs)
        self.type = 'btrfs'
        self.default_pool_name = SSM_BTRFS_DEFAULT_POOL
        self._vol = {}
        self._pool = {}
        self._dev = {}
        self._snap = {}
        self._subvolumes = {}
        self._binary = misc.check_binary('btrfs')
        self.modified_list_version = True

        if not self._binary:
            return

        self.mounts = misc.get_mounts('btrfs')
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
                    vol['real_dev'] = ""

                if label != 'none':
                    vol['label'] = label
                vol['ID'] = 0

            elif array[0] == 'Total':
                pool['dev_count'] = array[2]
                fs_used = float(misc.get_real_size(array[6]))

            elif array[0] == 'devid':
                # This is ugly hack to fix a problem with test suite and btrfs
                # where ?sometimes? btrfs prints out device name in the path
                # of the test suite rather than path in the real '/dev/'
                # directory. This should cover that without any impact on
                # real usage
                if not os.path.islink(array[7]):
                    array[7] = re.sub(r'.*/dev/', '/dev/', array[7])
                dev['dev_name'] = misc.get_real_device(array[7])

                if not pool_name:
                    pool_name = self._find_uniq_pool_name(label, array[7])
                dev['pool_name'] = pool_name

                # Fallback in case we could not find real_dev by uuid
                if 'mount' not in pool:
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
                                vol['real_dev'] = found[0].split(':')[0]
                                break

                dev_used = float(misc.get_real_size(array[5]))
                dev['dev_used'] = str(dev_used)
                fs_size += float(misc.get_real_size(array[3]))

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

    def _list_subvolumes(self, mount, list_snapshots=False):
        command = ['btrfs', 'subvolume', 'list']
        if self.modified_list_version:
            command.append('-a')
        if list_snapshots:
            command.append('-s')
        ret, output = misc.run(command + [mount], stdout=False, can_fail=True)
        if ret:
            command = ['btrfs', 'subvolume', 'list']
            if list_snapshots:
                command.append('-s')
            output = misc.run(command + [mount], stdout=False)[1]
            self.modified_list_version = False
        return output

    # There is no way in btrfs to list subvolumes which are not snapshots
    # so we have to get the list of snapshots to filter it out from
    # regular subvolume list so we do not have it in the output twice.
    # Once in volume list and once in snapshot list.
    def _get_snap_name_list(self, mount):
        snap = []
        if BTRFS_VERSION < 0.20:
            return snap
        command = ['btrfs', 'subvolume', 'list', '-s', mount]
        output = misc.run(command, stdout=False)[1]

        for line in output.strip().split("\n"):
            if not line:
                continue
            path = re.search('(?<=path ).*$', line).group(0)
            snap.append(path)
        return snap

    def _fill_subvolumes(self, list_snapshots=False):
        if not self._binary:
            return
        if self._subvolumes:
            return
        for name, vol in self._vol.iteritems():
            pool_name = vol['pool_name']
            real_dev = vol['real_dev']
            pool = self._pool[pool_name]

            if 'mount' in self._pool[pool_name]:
                mount = pool['mount']
            else:
                # If btrfs is not mounted we will not process subvolumes
                continue

            snapshots = []
            if not list_snapshots:
                snapshots = self._get_snap_name_list(mount)

            output = self._list_subvolumes(mount, list_snapshots)
            for volume in self._parse_subvolumes(output):
                new = vol.copy()
                new.update(volume)
                new['dev_name'] = "{0}:{1}".format(name, new['path'])
                item = "{0}:/{1}".format(real_dev, new['path'])
                # If the subvolume is mounted we should find it here
                if item in self.mounts:
                    new['mount'] = self.mounts[item]['mp']
                    # Subvolume is mounted directly
                    new['direct_mount'] = True
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
                                        self._subvolumes[prev_sv]['mount'],
                                        path)
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
                    re.match(r"snap-\d{4}-\d{2}-\d{2}-T\d{6}",
                             os.path.basename(new['mount'])):
                    new['snap_name'] = "{0}:{1}".format(name,
                            os.path.basename(new['path']))
                    new['snap_path'] = new['mount']
                if volume['path'] in snapshots:
                    new['hide'] = True

                self._subvolumes[new['dev_name']] = new

    def _parse_subvolumes(self, output):
        volume = {}
        for line in output.strip().split("\n"):
            if not line:
                continue
            # For the version with screwed 'subvolume list' command
            line = re.sub("<FS_TREE>/*", "", line)
            volume['ID'] = re.search(r'(?<=ID )\d+', line).group(0)
            volume['top_level'] = re.search(r'(?<=top level )\d+', line).group(0)
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

        self._pool[pool['pool_name']] = pool
        self._vol[vol['dev_name']] = vol

    def _remove_filesystem(self, name):
        if 'mount' in self._vol[name]:
            if self.problem.check(self.problem.FS_MOUNTED,
                                  [name, self._vol[name]['mount']]):
                misc.do_umount(self._vol[name]['real_dev'], all_targets=True)
        devices = []
        for dev in self._dev.itervalues():
            if dev['pool_name'] != name:
                continue
            devices.append(dev['dev_name'])
        if len(devices) > 0:
            misc.wipefs(devices, 'btrfs')


class BtrfsVolume(Btrfs, template.BackendVolume):

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
        vol = self.data[vol]
        if options:
            options += ","
        else:
            options = ""
        options += "subvolid={0}".format(vol['ID'])
        misc.do_mount(vol['real_dev'], mpoint, options)

    def remove(self, vol):
        volume = self._vol[vol]
        if 'subvolume' in volume:
            # If subvolume is mounted directly we can not remove it. So ask
            # user whether he wants to umount it. The we'll have to mount the
            # root subvolume and remove this subvolume.
            if 'direct_mount' in volume and volume['direct_mount']:
                if self.problem.check(self.problem.FS_MOUNTED,
                                      [vol, volume['mount']]):
                    misc.do_umount(volume['mount'])
                    del volume['mount']
                    del volume['direct_mount']
            if 'mount' not in volume:
                mount = misc.temp_mount("UUID={0}".format(volume['uuid']))
                path = "{0}/{1}".format(mount, volume['path'])
            else:
                path = volume['mount']
            self.run_btrfs(['subvolume', 'delete', path])
        else:
            self._remove_filesystem(vol)

    def check(self, vol):
        vol = self.data[vol]
        return self.run_btrfs(['check', vol['real_dev']])[0]

    def resize(self, vol, size, resize_fs=True):
        vol = self.data[vol]
        if 'mount' not in vol:
            tmp = misc.temp_mount("UUID={0}".format(vol['uuid']))
            vol['mount'] = tmp
        if 'subvolume' in vol and vol['subvolume'] is True:
            self.problem.check(self.problem.NOT_SUPPORTED,
                               'Resizing btrfs subvolume')
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
            self.problem.warn("Btrfs doesn't allow setting a size of " +
                              "subvolumes")

        command = ['subvolume', 'snapshot', vol['mount'], destination]
        self.run_btrfs(command)


class BtrfsDev(Btrfs, template.BackendDevice):

    def __init__(self, *args, **kwargs):
        super(BtrfsDev, self).__init__(*args, **kwargs)
        if self.data:
            self.data.update(self._dev)
        else:
            self.data = self._dev

    def remove(self, devices):
        raise Exception("Not sure what you want to" +
                        "achieve by removing {0}".format(devices))


class BtrfsPool(Btrfs, template.BackendPool):

    def __init__(self, *args, **kwargs):
        super(BtrfsPool, self).__init__(*args, **kwargs)
        if self.data:
            self.data.update(self._pool)
        else:
            self.data = self._pool

    def _can_btrfs_force(self, command):
        """
        This is just ridiculous. Unfortunately btrfs tools usually change
        behaviour and options without bumping version number. So we have
        to check whether btrfs allows to 'force' file system creation.
        """
        output = misc.run(command + ['--force'], can_fail=True)[1]
        found = re.search('invalid option', output)
        if found:
            return False
        else:
            return True

    def _create_filesystem(self, pool, name, devs, size=None, options=None):
        options = options or {}
        if not devs:
            raise Exception("To create btrfs volume, some devices must be " +
                            "provided")
        self._binary = misc.check_binary('mkfs.btrfs')
        if not self._binary:
            self.problem.check(self.problem.TOOL_MISSING, 'mkfs.btrfs')
        command = ['mkfs.btrfs', '-L', name]

        if 'raid' in options:
            if options['raid'] == '0':
                command.extend(['-m', 'raid0', '-d', 'raid0'])
            elif options['raid'] == '1':
                command.extend(['-m', 'raid1', '-d', 'raid1'])
            elif options['raid'] == '10':
                command.extend(['-m', 'raid10', '-d', 'raid10'])
            else:
                raise Exception("Btrfs backed currently does not support " +
                                "RAID level {0}".format(options['raid']))

        if size:
            command.extend(['-b', "{0}".format(int(float(size) * 1024))])
        # This might seem weird, but btrfs is mostly broken when it comes to
        # checking existing signatures because it will for example check for
        # backup superblocks as well, which is wrong. Also we have check for
        # existing file system signatures in the ssm itself. Other things
        # than file system should be covered by the backend and we should
        # have tried to remove the device from the respective pool already.
        # So at this point there should not be any useful signatures to
        # speak of. However as I mentioned btrfs is broken, so force it.
        if self._can_btrfs_force(command):
            command.extend(['--force'])
        command.extend(devs)
        misc.run(command, stdout=True)
        misc.send_udev_event(devs[0], "change")
        return name

    def _check_new_path(self, path, name):
        msg = 0
        parent = os.path.split(path)[0]
        if os.path.exists(path):
            msg = "Directory \'{0}\' already exist. ".format(path) + \
                  "Subvolume \'{0}\' can not be ".format(name) + \
                  "created"
        elif not os.path.exists(parent):
            msg = "Parent directory \'{0}\' ".format(parent) + \
                  "does not exist. Subvolume " + \
                  "\'{0}\' can not be created".format(name)
        if msg:
            self.problem.error(msg)

    def reduce(self, pool, device):
        pool = self.data[pool]
        if 'mount' not in pool:
            tmp = misc.temp_mount("UUID={0}".format(pool['uuid']))
            pool['mount'] = tmp
        command = ['device', 'delete', device, pool['mount']]
        self.run_btrfs(command)
        misc.send_udev_event(device, "change")

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
        # This might seem weird, but btrfs is mostly broken when it comes to
        # checking existing signatures because it will for example check for
        # backup superblocks as well, which is wrong. Also we have check for
        # existing file system signatures in the ssm itself. Other things
        # than file system should be covered by the backend and we should
        # have tried to remove the device from the respective pool already.
        # So at this point there should not be any useful signatures to
        # speak of. However as I mentioned btrfs is broken, so force it.
        if self._can_btrfs_force(['btrfs', 'device', 'add']):
            command.extend(['--force'])
        command.extend(devices)
        command.append(pool['mount'])
        self.run_btrfs(command)

    def remove(self, pool):
        # Volume and pool name should be the same, since it actually is the
        # same file system
        self._remove_filesystem(pool)

    def create(self, pool, size=None, name=None, devs=None,
               options=None):
        options = options or {}
        if pool in self._pool:
            vol = None
            if size or 'raid' in options:
                self.problem.warn("Only name, volume name and pool name " +
                                  "can be specified when creating btrfs " +
                                  "subvolume, the rest will be ignored")
            tmp = misc.temp_mount("UUID={0}".format(self._pool[pool]['uuid']))
            self._pool[pool]['mount'] = tmp

            if not name:
                now = datetime.datetime.now()
                name = now.strftime("%Y-%m-%d-T%H%M%S")
                vol = "{0}/{1}".format(self._pool[pool]['mount'], name)
            elif os.path.isabs(name):
                vol = name
            else:
                vol = "{0}/{1}".format(self._pool[pool]['mount'], name)

            self._check_new_path(vol, name)
            self.run_btrfs(['subvolume', 'create', vol])
            vol = "{0}:{1}".format(pool, name)
        else:
            if len(devs) == 0:
                self.problem.check(self.problem.NO_DEVICES, pool)
            if name:
                self.problem.warn("Creating new pool. Argument (--name " +
                                  "{0}) will be ignored!".format(name))
            vol = self._create_filesystem(pool, pool, devs, size, options)
        return vol


class BtrfsSnap(Btrfs):

    def __init__(self, *args, **kwargs):
        super(BtrfsSnap, self).__init__(*args, **kwargs)

        self._fill_subvolumes(list_snapshots=True)
        for name, vol in self._subvolumes.iteritems():
            if BTRFS_VERSION < 0.20:
                if 'snap_name' in vol:
                    self._snap[vol['snap_name']] = vol.copy()
                    self._snap[vol['snap_name']]['hide'] = False
            else:
                self._snap[vol['dev_name']] = vol.copy()

        if self.data:
            self.data.update(self._snap)
        else:
            self.data = self._snap
