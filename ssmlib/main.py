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
#
# System Storage Manager - ssm

import re
import os
import sys
import stat
import argparse
from ssmlib import misc
from itertools import chain, compress

# Import backends
from ssmlib.backends import lvm, crypt, btrfs

EXTN = ['ext2', 'ext3', 'ext4']
SUPPORTED_FS = ['xfs', 'btrfs'] + EXTN
os.environ['LANG'] = "C"

# Name of the default pool
try:
    DEFAULT_DEVICE_POOL = os.environ['DEFAULT_DEVICE_POOL']
except KeyError:
    DEFAULT_DEVICE_POOL = "device_pool"

# If this environment variable is set, ssm will only consider such devices,
# pools and volumes which names start with this prefix. This is especially
# useful for testing.
try:
    SSM_PREFIX_FILTER = os.environ['SSM_PREFIX_FILTER']
    print >> sys.stderr, "WARNING: SSM_PREFIX_FILTER is set to " + \
        "\'{0}\'".format(SSM_PREFIX_FILTER)
except KeyError:
    SSM_PREFIX_FILTER = None


class StoreAll(argparse._StoreAction):
    '''
    Argparse class used to store all valid values. Valid values should not be
    empty or None
    '''

    def __call__(self, parser, namespace, values, option_string=None):
        for val in values[:]:
            if not val:
                values.remove(val)
        setattr(namespace, self.dest, values)


class FsInfo(object):
    '''
    Parse and store information about the file system. Methods specific for
    each file system should be part of this class
    '''

    def __init__(self, dev, force=False, verbose=False):
        self.data = {}
        fstype = misc.get_fs_type(dev)
        if fstype in SUPPORTED_FS and \
           fstype != 'btrfs':
            self.data['fs_type'] = fstype
        else:
            return

        self.fs_info = {}
        if fstype in EXTN:
            self.extN_get_info(dev)
        elif fstype == "xfs":
            self.xfs_get_info(dev)
        self.fstype = fstype
        self.device = dev
        self.force = force
        self.verbose = verbose
        self.mounted = False

    def _get_fs_func(self, func, *args, **kwargs):
        fstype = self.fstype
        if re.match("ext[2|3|4]", self.fstype):
            fstype = "extN"
        func = getattr(self, "{0}_{1}".format(fstype, func))
        return func(*args, **kwargs)

    def fsck(self):
        return self._get_fs_func("fsck")

    def resize(self, *args, **kwargs):
        return self._get_fs_func("resize", *args, **kwargs)

    def get_info(self, *args, **kwargs):
        return self._get_fs_func("get_info", *args, **kwargs)

    def extN_get_info(self, dev):
        command = ["tune2fs", "-l", dev]
        output = misc.run(command)[1]

        for line in output.split("\n")[1:]:
            array = line.split(":")
            if len(array) == 2:
                self.fs_info[array[0]] = array[1].lstrip()

        bsize = int(self.fs_info['Block size'])
        bcount = int(self.fs_info['Block count'])
        rbcount = int(self.fs_info['Reserved block count'])
        fbcount = int(self.fs_info['Free blocks'])
        self.data['fs_size'] = bcount * bsize / 1024
        self.data['fs_free'] = (fbcount - rbcount) * bsize / 1024
        self.data['fs_used'] = (bcount - fbcount) * bsize / 1024

    def extN_fsck(self):
        command = ['fsck.{0}'.format(self.fstype), '-f']
        if self.force:
            command.append('-f')
        if self.verbose:
            command.append('-v')
        command.append(self.device)
        return misc.run(command, stdout=True, can_fail=True)[0]

    def extN_resize(self, new_size=None):
        command = ['resize2fs', self.device]
        if self.force:
            command.insert(1, "-f")
        if self.verbose:
            command.insert(1, "-p")
        if new_size:
            command.append(new_size)
        # Ext3/4 can resize offline in both directions, but It can not shrink
        # the file system while online. In addition ext2 can only resize
        # offline.
        if self.mounted and (self.fstype == "ext2" or
           new_size < self.data['fs_size']):
            raise Exception(
                "{0} is mounted on {1}".format(self.device, self.mounted) +
                " In this case, mounted file system can not be resized.")
        ret = self.fsck()
        if ret:
            raise Exception("File system on {0} is not ".format(self.device) +
                            "clean, I will not attempt to resize it. Please," +
                            "fix the problem first.")
        misc.run(command, stdout=True)

    def xfs_get_info(self, dev):
        command = ["xfs_db", "-r", "-c", "sb", "-c", "print", dev]
        output = misc.run(command)[1]

        for line in output.split("\n")[1:]:
            array = line.split("=")
            if len(array) == 2:
                self.fs_info[array[0].rstrip()] = array[1].lstrip()

        bsize = int(self.fs_info['blocksize'])
        bcount = int(self.fs_info['dblocks'])
        lbcount = int(self.fs_info['logblocks'])
        bcount = bcount - lbcount
        agcount = int(self.fs_info['agcount'])
        fbcount = int(self.fs_info['fdblocks'])
        fbcount = fbcount - (4 + (4 + agcount))
        self.data['fs_size'] = bcount * bsize / 1024
        self.data['fs_free'] = fbcount * bsize / 1024
        self.data['fs_used'] = (bcount - fbcount) * bsize / 1024

    def xfs_fsck(self):
        command = ['xfs_check']
        if self.verbose:
            command.append('-v')
        command.append(self.device)
        return misc.run(command, stdout=True, can_fail=True)[0]

    def xfs_resize(self, new_size=None):
        command = ['xfs_growfs', self.device]
        if new_size:
            command.insert(1, ['-D', new_size + 'K'])
        if not self.mounted:
            raise Exception("Xfs file system on {0}".format(self.device) +
                    " has to be mounted to perform an resize.")
        elif new_size and new_size < self.data['fs_size']:
            raise Exception("Xfs file system can not shrink.")
        else:
            misc.run(command, stdout=True)


class DeviceInfo(object):
    '''
    Parse and store information about the devices present in the system. The
    main source of information are /proc/partitions, /proc/mounts and
    /proc/swaps. self.data should be appended to since there might be other
    data present which will add more information about devices, usually
    provided from backends.

    Important thing is that we hide all dm devices here, since they might
    really be a volumes. We let backend decide whether the device should be
    listed as device or not simply by setting 'hide' to True/False.
    '''

    def __init__(self, data=None, force=False, verbose=False, yes=False):
        self.data = data or {}
        self.attrs = ['major', 'minor', 'dev_size', 'dev_name']
        self.force = force
        self.verbose = verbose
        self.yes = yes

        dmnumber = misc.get_dmnumber("device-mapper")
        mounts = misc.get_mounts('^/dev')
        swaps = misc.get_swaps()

        for items in misc.get_partitions():
            devices = dict(zip(self.attrs, items))
            devices['vol_size'] = devices['dev_size']
            devices['dev_name'] = "/dev/" + devices['dev_name']
            if devices['major'] == dmnumber:
                devices['hide'] = True
            if devices['dev_name'] in self.data:
                if 'hide' in self.data[devices['dev_name']] and \
                   not self.data[devices['dev_name']]['hide']:
                    devices['hide'] = False
                self.data[devices['dev_name']].update(devices)
            else:
                self.data[devices['dev_name']] = devices
            if devices['dev_name'] in mounts:
                devices['mount'] = mounts[devices['dev_name']]

        for item in swaps:
            if item[0] in self.data:
                self.data[item[0]]['mount'] = "SWAP"

        for i, dev in enumerate(self.data.itervalues()):
            if 'minor' in dev and dev['minor'] != '0':
                continue
            part = 0
            for a, d in enumerate(self.data.values()):
                if a == i:
                    continue
                try:
                    if dev['major'] != d['major']:
                        continue
                except KeyError:
                    continue
                if re.search(dev['dev_name'], d['dev_name']):
                    d['partition'] = True
                    d['type'] = 'part'
                    part += 1
            dev['partitioned'] = part
            if part > 0:
                dev['mount'] = "PARTITIONED"
                dev['type'] = 'disk'

    def __iter__(self):
        for item in sorted(self.data.iterkeys()):
            yield item

    def __getitem__(self, name):
        device = misc.get_real_device(name)
        if device in self.data.iterkeys():
            return self.data[device]
        return None


class Item(object):
    '''
    Meta object which provides encapsulation for all devices, pools and
    volumes, so we can work with them as with the usual objects without the
    need to call Dev, Pool or Vol methods directly.
    '''

    def __init__(self, obj, name):
        self.obj = obj
        self.name = name

    @property
    def data(self):
        return self.obj[self.name]

    def __getattr__(self, func_name):
        func = getattr(self.obj, func_name)
        if not func:
            raise AttributeError

        def _new_func(*args, **kwargs):
            if args and kwargs:
                return func(self.name, *args, **kwargs)
            elif kwargs:
                return func(self.name, **kwargs)
            elif args:
                return func(self.name, *args)
            else:
                return func(self.name)

        return _new_func

    def __getitem__(self, key):
        if key not in self.data and \
           re.match(r"fs_.*", key):
            self._fill_fs_info()
        try:
            ret = self.data[key]
        except KeyError:
            ret = ""
        return ret

    def __contains__(self, item):
        if self[item]:
            return True
        else:
            return False

    def _fill_fs_info(self):
        if 'dm_name' in self.data:
            name = self.data['dm_name']
        elif 'real_dev' in self.data:
            name = self.data['real_dev']
        else:
            name = self.data['dev_name']
        fs = FsInfo(name, self.obj.force, self.obj.verbose)
        try:
            fs.mounted = self.data['mount']
        except KeyError:
            fs.mounted = ""
        self.data.update(fs.data)
        self.data['fs_info'] = fs

    def exists(self):
        if self.name in self.obj:
            return True
        else:
            return False


class Storage(object):
    '''
    Template class to use for storing information about Pools, Volumes and
    Devices from different backends. This simplify things a lot since we do not
    have to manually walk through all the backends, but this class will do this
    for us.
    '''

    def __init__(self, force=False, verbose=False, yes=False):
        self.force = force
        self.verbose = verbose
        self.yes = yes
        self._data = None
        self.header = None
        self.attrs = None
        self.types = None

    def __iter__(self):
        for source in self._data.itervalues():
            for item in source:
                yield Item(source, item)

    def __contains__(self, item):
        if self[item]:
            return True
        else:
            return False

    def __getitem__(self, name):
        for source in self._data.itervalues():
            item = source[name]
            if item:
                return Item(source, name)
        return None

    def _apply_prefix_filter(self):
        '''
        If SSM_PREFIX FILTER is set, remove all items which basenames does not
        start with SSM_PREFIX_FILTER prefix. This is useful especially for
        testing so that ssm see only relevant devices and does not screw real
        system storage configuration.
        '''
        if not SSM_PREFIX_FILTER:
            return
        for source in self._data.itervalues():
            for item in source:
                if not re.search("^{0}".format(SSM_PREFIX_FILTER),
                        os.path.basename(item)):
                    del source.data[item]

    def get_backend(self, name):
        return self._data[name]

    def set_globals(self, force, verbose, yes):
        self.force = force
        self.verbose = verbose
        self.yes = yes
        for source in self._data.itervalues():
            source.force = force
            source.verbose = verbose
            source.yes = yes

    def filesystems(self):
        for item in self:
            if 'fs_type' in item:
                yield item

    def ptable(self, cond=None, more_data=None, cond_func=None):
        '''
        Print information table about the source (devices, pools, volumes)
        using the predefined variables (below). cond, or cond_func can be
        provided to decide which items not to print out.

        self.header - list of headers for the table
        self.attrs - list of attribute keys to print out
        self.types - types of the attributes to print out (str, or float/int)
        '''
        lines = []
        fmt = ""
        alignment = list([(len(self.header[i]))
                    for i in range(len(self.header))])

        if cond == "fs_only":
            iterator = self.filesystems()
        else:
            iterator = self

        # Keep track of used columns. Then we only print out columns with
        # values.
        columns = [False] * len(self.attrs)

        for data in chain(iterator, more_data or []):
            if (cond_func and not cond_func(data)) or 'hide' in data:
                continue
            line = ()
            for i, attr in enumerate(self.attrs):
                if self.types[i] in (float, int):
                    item = misc.humanize_size(data[attr])
                elif attr + "_print" in data:
                    item = data[attr + "_print"]
                else:
                    item = data[attr]
                alignment[i] = max(len(item), alignment[i])
                line += item,
                if len(item) > 0:
                    columns[i] = True
            lines.append(line)

        if len(lines) == 0:
            return

        header = [item for item in compress(self.header, columns)]
        width = sum(compress(alignment, columns)) + 2 * len(header) - 2

        for i, t in enumerate(self.types):
            if not columns[i]:
                continue
            if t in (float, int):
                fmt += "{{:>{0}}}  ".format(alignment[i])
            else:
                fmt += "{{:{0}}}  ".format(alignment[i])

        print "-" * width
        print fmt.format(*tuple(header))
        print "-" * width
        for line in lines:
            line = compress(line, columns)
            print fmt.format(*line)
        print "-" * width


class Pool(Storage):
    '''
    Store Pools from all the backends. When new backend is added into the ssm
    it should be registered withing this class with appropriate name.
    '''

    def __init__(self, *args, **kwargs):
        super(Pool, self).__init__(*args, **kwargs)
        _default_backend = lvm.VgsInfo(force=self.force, verbose=self.verbose,
                                   yes=self.yes)
        self._data = {'lvm': _default_backend,
                     'btrfs': \
                        btrfs.BtrfsPool(force=self.force, verbose=self.verbose,
                        yes=self.yes)}
        self.default = Item(_default_backend, DEFAULT_DEVICE_POOL)
        self.header = ['Pool', 'Type', 'Devices', 'Free', 'Used', 'Total']
        self.attrs = ['pool_name', 'type', 'dev_count', 'pool_free',
                      'pool_used', 'pool_size']
        self.types = [str, str, str, float, float, float]
        self._apply_prefix_filter()


class Devices(Storage):
    '''
    Store Devices from all the backends. When new backend is added into the ssm
    it should be registered withing this class with appropriate name.

    If the backend only have new information about the device which is already
    discovered by the DeviceInfo() class then it should just add the
    information into the existing devices by passing the data. But if the
    backed discovers new devices, it should add them as a new entry.
    '''

    def __init__(self, *args, **kwargs):
        super(Devices, self).__init__(*args, **kwargs)
        self._data = {'dev': \
            DeviceInfo(data=lvm.PvsInfo(btrfs.BtrfsDev().data).data,
            force=self.force, verbose=self.verbose, yes=self.yes)}
        self.header = ['Device', 'Free', 'Used',
                       'Total', 'Pool', 'Mount point']
        self.attrs = ['dev_name', 'dev_free', 'dev_used', 'dev_size',
                      'pool_name', 'mount']
        self.types = [str, float, float, float, str, str]
        self._apply_prefix_filter()


class Volumes(Storage):
    '''
    Store Volumes from all the backends. When new backend is added into the ssm
    it should be registered withing this class with appropriate name.
    '''

    def __init__(self, *args, **kwargs):
        super(Volumes, self).__init__(*args, **kwargs)
        self._data = {'lvm': lvm.LvsInfo(force=self.force,
                        verbose=self.verbose, yes=self.yes),
                     'crypt': crypt.DmCryptVolume(force=self.force,
                        verbose=self.verbose, yes=self.yes),
                     'btrfs': btrfs.BtrfsVolume(force=self.force,
                        verbose=self.verbose, yes=self.yes)}
        self.header = ['Volume', 'Volume size', 'FS', 'Free',
                       'Used', 'FS size', 'Type', 'Mount point']
        self.attrs = ['dev_name', 'vol_size', 'fs_type',
                      'fs_free', 'fs_used', 'fs_size', 'type', 'mount']
        self.types = [str, float, str, float, float, float, str, str]
        self._apply_prefix_filter()


class StorageHandle(object):
    '''
    The main class where all the magic is done. All the commands provided by
    ssm have its appropriate functions here which are then called by argparse.
    '''

    def __init__(self):
        self.force = False
        self.verbose = False
        self.yes = False
        self.config = None
        self._mpoint = None
        self._dev = None
        self._pool = None
        self._volumes = None

    def set_globals(self, force, verbose, yes, config):
        '''
        Set global parameters (force,verbose,yes,config) and propagate it into
        the backends.
        '''
        self.force = force
        self.verbose = verbose
        self.yes = yes
        self.config = config
        if self._dev:
            self.dev.set_globals(force, verbose, yes)
        if self._volumes:
            self.vol.set_globals(force, verbose, yes)
        if self._pool:
            self.pool.set_globals(force, verbose, yes)

    @property
    def dev(self):
        if self._dev:
            return self._dev
        self._dev = Devices(force=self.force, verbose=self.verbose,
                            yes=self.yes)
        return self._dev

    @property
    def pool(self):
        if self._pool:
            return self._pool
        self._pool = Pool(force=self.force, verbose=self.verbose, yes=self.yes)
        return self._pool

    @property
    def vol(self):
        if self._volumes:
            return self._volumes
        self._volumes = Volumes(force=self.force, verbose=self.verbose,
                                yes=self.yes)
        return self._volumes

    def _create_fs(self, fstype, volume):
        """
        Create a file system 'fstype' on the 'volume'.
        """
        command = ["mkfs.{0}".format(fstype), volume]
        if self.force:
            if fstype == 'xfs':
                command.insert(1, '-f')
            if fstype in EXTN:
                command.insert(1, '-F')
        if self.verbose:
            if fstype in EXTN:
                command.insert(1, '-v')
        misc.run(command, stdout=True)

    def check(self, args):
        '''
        Check the file system on the volume. FsInfo is used for that purpose,
        except for btrfs.
        '''
        err = 0
        for fs in args.device:
            print "Checking {0} file system on device {1}:".format(fs.fstype,
                                                                 fs.device),
            if fs.mounted:
                print "MOUNTED - skipping"
                continue
            err += fs.fsck()
        if err > 0:
            print "\nWarning: Some file system(s) contains errors.",
            print "Please run the appropriate fsck utility"

    def resize(self, args):
        '''
        Resize the volume to the given size. If more devices are provided as
        arguments, it will be added into the pool prior to the volume resize
        only if the space in the pool is not sufficient. That said, only the
        number of devices are added into the pool to be able to cover the
        resize.
        '''
        args.pool = self.pool[args.volume['pool_name']]
        vol_size = float(args.volume['vol_size'])

        if not args.size:
            new_size = vol_size
        elif args.size[0] == '+':
            new_size = vol_size + float(args.size[1:])
        elif args.size[0] == '-':
            new_size = vol_size + float(args.size)
        else:
            new_size = float(args.size)

        fs = True if 'fs_type' in args.volume else False

        have_size = float(args.pool['pool_size'])
        devices = args.device
        args.device = []

        for dev in devices[:]:
            if have_size > float(new_size):
                break
            if self.dev[dev] and 'pool_name' in self.dev[dev] and \
               self.dev[dev]['pool_name'] != args.pool.name:
                err = "Device '{0}' is already used in ".format(dev) + \
                      "the pool '{0}'.".format(self.dev[dev]['pool_name'])
                raise argparse.ArgumentTypeError(err)
            if not self.dev[dev] or 'pool_name' not in self.dev[dev]:
                args.device.append(dev)
            have_size += float(self.dev[dev]['dev_size'])

        if have_size < new_size:
            raise Exception("There is not enough space " +
                            "in the pool {0} ".format(args.pool.name) +
                            "to grow volume {0} ".format(args.volume.name) +
                            "to size {0} KB".format(new_size))
        else:
            self.add(args)

        if new_size != vol_size:
            args.volume.resize(new_size, fs)
        else:
            # Try to grow the file system, since there is nothing to
            # do with the volume itself.
            if fs:
                args.volume['fs_info'].resize()
            else:
                raise Exception("'{0}' volume is already {1}".format(
                    args.volume.name, new_size) + \
                    "KBytes long, there is nothing to resize")

    def create(self, args):
        '''
        Create new volume (or subvolume in case of btrfs) using the devices
        provided as arguments. If the device is not in the selected pool, then
        add() is called on the pool prior to create().
        '''
        devices = args.device
        args.device = []
        print "Going to create new device with {0}".format(devices)
        if args.pool.exists():
            print "Pool {0} exists".format(args.pool.name)
        # Get the size in kilobytes
        if args.size:
            args.size = misc.get_real_size(args.size)

        # Btrfs is a bit special, since it is in fact the file system, but it
        # does volume management on its own. So ssm does not handle it as
        # "regular" file system, but rather as volume manager.
        if args.fstype == 'btrfs':
            if not args.name:
                args.name = "btrfs_{0}".format(os.path.basename(devices[0]))
            args.pool = Item(self.pool.get_backend('btrfs'), args.name)
        if args.pool.exists() and args.pool['type'] == 'btrfs' and \
                self._mpoint:
            args.name = self._mpoint
            self._mpoint = None

        for dev in devices[:]:
            if self.dev[dev] and 'pool_name' in self.dev[dev] and \
               self.dev[dev]['pool_name'] != args.pool.name:
                err = "Device '{0}' is already used in ".format(dev) + \
                      "the pool '{0}'.".format(self.dev[dev]['pool_name'])
                raise argparse.ArgumentTypeError(err)
            if not self.dev[dev] or 'pool_name' not in self.dev[dev]:
                args.device.append(dev)

        if len(args.device) > 0 and \
           args.fstype != 'btrfs':
            self.add(args)

        print args.size
        lvname = args.pool.create(devs=devices,
                                  size=args.size,
                                  stripesize=args.stripesize,
                                  stripes=args.stripes,
                                  name=args.name)
        if not args.fstype:
            return
        if not args.fstype == 'btrfs':
            print "Creating {0} file".format(args.fstype) + \
                  "system on {0}: ".format(lvname)
            self._create_fs(args.fstype, lvname)
        if self._mpoint:
            misc.do_mount(lvname, self._mpoint)

    def list(self, args):
        '''
        List devices, pools, volumes
        '''
        if not args.type:
            self.dev.ptable()
            self.pool.ptable()
            self.vol.ptable(more_data=self.dev.filesystems())
        elif args.type in ['fs', 'filesystems']:
            self.vol.ptable(more_data=self.dev.filesystems(), cond="fs_only")
        elif args.type in ['dev', 'devices']:
            self.dev.ptable()
        elif args.type == "volumes":
            self.vol.ptable(more_data=self.dev.filesystems())
        elif args.type == "pool":
            self.pool.ptable()

    def add(self, args):
        '''
        Add devices into the pool
        '''
        if args.pool.exists():
            for dev in args.device[:]:
                item = self.dev[dev]
                if item['pool_name'] == args.pool.name:
                    args.device.remove(dev)
            if len(args.device) > 0:
                args.pool.extend(args.device)
        else:
            args.pool.new(args.device)

    def remove(self, args):
        '''
        Remove the all the items, or all pools if all argument is specified.
        Items could be the devices, pools or volumes.
        '''
        if args.all:
            for pool in self.pool:
                pool.remove()
            return
        if len(args.items) == 0:
            err = "too few arguments"
            raise argparse.ArgumentTypeError(err)
        for item in args.items:
            try:
                if isinstance(item.obj, DeviceInfo):
                    pool = self.pool[item['pool_name']]
                    if pool:
                        pool.reduce(item.name)
                        continue
                    else:
                        raise Exception("It is not clear what do you want " +
                                        "to achieve by removing " +
                                        "{0}".format(item.name))
                item.remove()
            except RuntimeError, ex:
                print ex
                print >> sys.stderr, "Unable to remove '{0}'".format(item.name)

    def mirror(self, args):
        print "mirror"
        print args

    def is_fs(self, device):
        real = misc.get_real_device(device)

        vol = self.vol[real]
        if vol and 'fs_type' in vol:
            return vol['fs_info']
        dev = self.dev[real]
        if dev and 'fs_type' in dev:
            return dev['fs_info']
        err = "'{0}' does not contain valid file system".format(real)
        raise argparse.ArgumentTypeError(err)

    def check_create_item(self, path):
        '''
        Check the create argument for block device or directory.
        '''
        if not self._mpoint:
            try:
                mode = os.stat(path).st_mode
            except OSError:
                err = "'{0}' does not exist.".format(path)
                raise argparse.ArgumentTypeError(err)
            if stat.S_ISDIR(mode):
                self._mpoint = path
                return
        return is_bdevice(path)

    def is_pool(self, string):
        pool = self.pool[string]
        if not pool:
            self.pool.default.name = string
            pool = self.pool.default
        return pool

    def is_volume(self, string):
        vol = self.vol[string]
        if vol:
            return vol
        dev = self.dev[string]
        if dev and 'fs_type' in dev:
            return dev
        err = "'{0}' is not a valid volume to resize".format(string)
        raise argparse.ArgumentTypeError(err)

    def check_remove_item(self, string):
        '''
        Check the remove argument for volume, pool or device.
        '''
        volume = self.vol[string]
        if volume:
            return volume
        pool = self.pool[string]
        if pool:
            return pool
        device = self.dev[string]
        if device:
            return device
        for vol in self.vol:
            if 'mount' in vol and (vol['mount'] == string.rstrip("/")):
                return vol
        err = "'{0}' is not valid pool nor volume".format(string)
        raise argparse.ArgumentTypeError(err)


def valid_resize_size(size):
    """
    Validate that the 'size' is usable as resize argument. It means that the
    'size' argument should be in this format: [+|-]number[unit]. It returns the
    number with the provided sign (even with the plus sign) converted to the
    kilobytes. Is no unit is specified, default is kilobytes.

    >>> valid_resize_size("3.14")
    '3.14'
    >>> valid_resize_size("+3.14")
    '+3.14'
    >>> valid_resize_size("-3.14")
    '-3.14'
    >>> valid_resize_size("3.14k")
    '3.14'
    >>> valid_resize_size("+3.14K")
    '+3.14'
    >>> valid_resize_size("-3.14k")
    '-3.14'
    >>> valid_resize_size("3.14G")
    '3292528.64'
    >>> valid_resize_size("+3.14g")
    '+3292528.64'
    >>> valid_resize_size("-3.14G")
    '-3292528.64'
    >>> valid_resize_size("G")
    Traceback (most recent call last):
    ...
    ArgumentTypeError: 'G' is not valid number for the resize.
    """
    try:
        return misc.get_real_size(size)
    except Exception:
        err = "'{0}' is not valid number for the resize.".format(size)
        raise argparse.ArgumentTypeError(err)


def is_bdevice(path):
    try:
        mode = os.stat(path).st_mode
    except OSError:
        err = "'{0}' is not valid block device".format(path)
        raise argparse.ArgumentTypeError(err)
    if not stat.S_ISBLK(mode):
        err = "'{0}' is not valid block device".format(path)
        raise argparse.ArgumentTypeError(err)
    return path


def is_supported_fs(fs):
    if fs in SUPPORTED_FS:
        return fs
    err = "'{0}' is not supported file system".format(fs)
    raise argparse.ArgumentTypeError(err)


def main(args=None):
    if args:
        sys.argv = args.split()

    storage = StorageHandle()

    parser = argparse.ArgumentParser(description="System Storage Manager",
                epilog='''To get help for particular command please specify
                       \'%(prog)s [command] -h\'.''')
    parser.add_argument('--version', action='version',
                        version='%(prog)s 0.1dev')
    parser.add_argument('-v', '--verbose', help="verbose execution",
                        action="store_true")
    parser.add_argument('-f', '--force', help="force execution",
                        action="store_true")
    #parser.add_argument('-y', '--yes', help="yes", action="store_true")
    #parser.add_argument('-c', '--config', help="config", type=file)

    subcommands = parser.add_subparsers(title="Commands")

    # check command
    parser_check = subcommands.add_parser("check",
            help="check consistency of the file system on the device")
    parser_check.add_argument('device', nargs='+',
            help="Device with file system to check.", type=storage.is_fs)
    parser_check.set_defaults(func=storage.check)

    # resize command
    parser_resize = subcommands.add_parser("resize",
            help="change or set the volume and file system size")
    parser_resize.add_argument("volume", help="Volume to resize.",
            type=storage.is_volume)
    parser_resize.add_argument('-s', '--size',
            help='''New size of the volume. With the + or - sign the value is
            added to or subtracted from the actual size of the volume and
            without it, the value will be set as the new volume size. A size
            suffix of [k|K] for kilobytes, [m|M] for megabytes, [g|G] for
            gigabytes, [t|T] for terabytes or [p|P] for petabytes is optional.
            If no unit is provided the default is kilobytes.''',
            type=valid_resize_size)
    parser_resize.add_argument("device", nargs='*',
            help='''Devices to use for extending the volume. If the
                    device is not in any pool, it is added into the
                    volume's pool prior to the extension. Note that only really
                    needed number of devices are added into the pool prior the
                    resize.''')
    parser_resize.set_defaults(func=storage.resize)

    # create command
    parser_create = subcommands.add_parser("create",
            help="create a new volume with defined parameters")
    parser_create.add_argument('-s', '--size',
            help='''Gives the size to allocate for the new logical volume
                    A size suffix K|k, M|m, G|g, T|t, P|p, E|e can be used
                    to define 'power of two' units. If no unit is provided, it
                    defaults to kilobytes. This is optional if if
                    not given maximum possible size will be used.''')
    parser_create.add_argument('-I', '--stripesize',
            help='''Gives the number of kilobytes for the granularity
                    of stripes. This is optional and if not given, linear
                    logical volume will be created.''')
    parser_create.add_argument('-n', '--name',
            help='''The name for the new logical volume. This is optional and
                    if omitted, name will be generated by the corresponding
                    backend.''')
    parser_create.add_argument('--fstype',
            help='''Gives the file system type to create on the new
                    logical volume. Supported file systems are (ext3,
                    ext4, xfs, btrfs). This is optional and if not given
                    file system will not be created.''',
                    type=is_supported_fs)
    parser_create.add_argument('-i', '--stripes',
            help='''Gives the number of stripes. This is equal to the
                    number of physical volumes to scatter the logical
                    volume. This is optional and if stripesize is set
                    and multiple devices are provided stripes is
                    determined automatically from the number of devices.''')
    parser_create.add_argument('-p', '--pool', default=DEFAULT_DEVICE_POOL,
            help="Pool to use to create the new volume.", type=storage.is_pool)
    parser_create.add_argument('device', nargs='*',
            help='''Devices to use for creating the volume. If the device is
                 not in any pool, it is added into the pool prior the volume
                 creation.''',
            type=storage.check_create_item,
            action=StoreAll)
    parser_create.add_argument('mount', nargs='?', help='''Directory to mount
                                the newly create volume to.''')
    parser_create.set_defaults(func=storage.create)

    # list command
    parser_list = subcommands.add_parser("list", help='''list information about
                    all detected, devices, pools and volumes in the system''')
    parser_list.add_argument('type', nargs='?',
            choices=["volumes", "dev", "devices", "pool", "fs", "filesystems"])
    parser_list.set_defaults(func=storage.list)

    # add command
    parser_add = subcommands.add_parser("add", help='''add one or more devices
                                        into the pool''')
    parser_add.add_argument('-p', '--pool', default=DEFAULT_DEVICE_POOL,
            help='''Pool to add device into. If not specified the default
                 pool is used.''', type=storage.is_pool)
    parser_add.add_argument('device', nargs='+',
            help="Devices to add into the pool",
            type=is_bdevice)
    parser_add.set_defaults(func=storage.add)

    # remove command
    parser_remove = subcommands.add_parser("remove", help='''remove devices
            from the pool, volumes or pools''')
    parser_remove.add_argument('-a', '--all', action="store_true",
            help="Remove all pools")
    parser_remove.add_argument('items', nargs='*',
            help="Items to remove. Item could be device, pool, or volume.",
            type=storage.check_remove_item)
    parser_remove.set_defaults(func=storage.remove)

    # mirror command
    #parser_mirror = subcommands.add_parser("mirror", help="mirror")
    #parser_mirror.set_defaults(func=storage.mirror)

    args = parser.parse_args()
    #storage.set_globals(args.force, args.verbose, args.yes, args.config)
    storage.set_globals(args.force, args.verbose, False, None)

    try:
        args.func(args)
    except argparse.ArgumentTypeError, ex:
        parser.error(ex)
    return 0

if __name__ == "__main__":
    if not os.geteuid() == 0:
        sys.exit("\nRoot privileges required to run this script!\n")
    try:
        sys.exit(main())
    except RuntimeError, ERR:
        print ERR
        sys.exit(1)
