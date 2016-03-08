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
import atexit
import argparse
from ssmlib import misc
from ssmlib import problem

# Import backends
from ssmlib.backends import lvm, crypt, btrfs, md

EXTN = ['ext2', 'ext3', 'ext4']
SUPPORTED_FS = ['xfs', 'btrfs'] + EXTN
SUPPORTED_BACKENDS = ['lvm', 'btrfs', 'crypt']
SUPPORTED_RAID = ['0', '1', '10']
os.environ['LC_NUMERIC'] = "C"

# If you change this please change doc/conf.py as well
VERSION = '0.4'

# Should the script be run in interactive or non interactive mode ?
try:
    SSM_NONINTERACTIVE = os.environ['SSM_NONINTERACTIVE']
    if SSM_NONINTERACTIVE.upper() in ['YES', 'TRUE', '1']:
        SSM_NONINTERACTIVE = True
    elif SSM_NONINTERACTIVE.upper() in ['NO', 'FALSE', '0']:
        SSM_NONINTERACTIVE = False
except KeyError:
    SSM_NONINTERACTIVE = not os.isatty(sys.stdout.fileno())

if sys.version < '3':
    def __next__(iter):
        return iter.next()
else:
    def __next__(iter):
        return next(iter)


class Options(object):
    """
    Structure that contains option setting allowing it to be
    passed between parts of ssm.
    """

    def __init__(self):
        self.interactive = not SSM_NONINTERACTIVE
        self.verbose = False
        self.debug = False
        self.force = False
        self.yes = False
        self.config = None


# Initialize problem set
PR = problem.ProblemSet(Options())

# Name of the default pool
try:
    DEFAULT_DEVICE_POOL = os.environ['DEFAULT_DEVICE_POOL']
except KeyError:
    DEFAULT_DEVICE_POOL = "device_pool"

# Default back-end
try:
    SSM_DEFAULT_BACKEND = os.environ['SSM_DEFAULT_BACKEND']
    if SSM_DEFAULT_BACKEND not in SUPPORTED_BACKENDS:
        if PR.check(PR.BAD_ENV_VARIABLE,
                    ['SSM_DEFAULT_BACKEND', SSM_DEFAULT_BACKEND]):
            SSM_DEFAULT_BACKEND = 'lvm'
except KeyError:
    SSM_DEFAULT_BACKEND = 'lvm'


# If this environment variable is set, ssm will only consider such devices,
# pools and volumes which names start with this prefix. This is especially
# useful for testing.
try:
    SSM_PREFIX_FILTER = os.environ['SSM_PREFIX_FILTER']
    PR.warn("SSM_PREFIX_FILTER is set to \'{0}\'".format(SSM_PREFIX_FILTER))
except KeyError:
    SSM_PREFIX_FILTER = None


class Struct(object):
    def __init__(self):
        pass


class StoreAll(argparse._StoreAction):
    """
    Argparse class used to store all valid values. Valid values should not be
    empty or None
    """

    def __call__(self, parser, namespace, values, option_string=None):
        for val in values[:]:
            if not val:
                values.remove(val)
        setattr(namespace, self.dest, values)


class SetBackend(argparse._StoreAction):
    """
    Action for the backend parameter, where we want to store provided
    in SSM_DEFAULT_BACKEND.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        # Set default backend to the provided value. All check should be
        # already done by argparse.
        global SSM_DEFAULT_BACKEND
        SSM_DEFAULT_BACKEND = values[0]
        setattr(namespace, self.dest, values)


class FsInfo(object):
    """
    Parse and store information about the file system. Methods specific for
    each file system should be part of this class
    """

    def __init__(self, dev, options):
        self.data = {}
        self.options = options
        fstype = misc.get_fs_type(dev)
        if fstype not in [None, 'btrfs']:
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
        self.mounted = False

    def _get_fs_func(self, func, *args, **kwargs):
        fstype = self.fstype
        if re.match("ext[2|3|4]", self.fstype):
            fstype = "extN"
        try:
            func = getattr(self, "{0}_{1}".format(fstype, func))
        except AttributeError:
            msg = "{0} file system is not yet supported.".format(fstype)
            raise problem.NotSupported(msg)
        return func(*args, **kwargs)

    def fsck(self):
        try:
            ret = self._get_fs_func("fsck")
        except problem.ToolMissing:
            ret = 0
        return ret

    def resize(self, *args, **kwargs):
        return self._get_fs_func("resize", *args, **kwargs)

    def get_info(self, *args, **kwargs):
        return self._get_fs_func("get_info", *args, **kwargs)

    def extN_get_info(self, dev):
        command = ["tune2fs", "-l", dev]
        if not misc.check_binary(command[0]):
            return
        output = misc.run(command)[1]

        for line in output.split("\n")[1:]:
            array = line.split(":")
            if len(array) == 2:
                self.fs_info[array[0]] = array[1].lstrip()

        bsize = int(self.fs_info['Block size'])
        bcount = int(self.fs_info['Block count'])
        rbcount = int(self.fs_info['Reserved block count'])
        fbcount = int(self.fs_info['Free blocks'])
        self.data['fs_size'] = bcount * bsize // 1024
        self.data['fs_free'] = (fbcount - rbcount) * bsize // 1024
        self.data['fs_used'] = (bcount - fbcount) * bsize // 1024

    def extN_fsck(self):
        command = ['fsck.{0}'.format(self.fstype), '-f', '-n']
        if not misc.check_binary(command[0]):
            PR.warn("\'{0}\' tool does not exist. ".format(command[0]) +
                    "File system will not be checked")
            raise problem.ToolMissing("fsck.{0}".format(self.fstype))
        if self.options.force:
            command.append('-f')
        if self.options.verbose:
            command.append('-v')
        command.append(self.device)
        return misc.run(command, stdout=True, can_fail=True)[0]

    def extN_resize(self, new_size=None):
        command = ['resize2fs', self.device]
        if not misc.check_binary(command[0]):
            PR.warn("\'{0}\' tool does not exist. ".format(command[0]) +
                    "File system will not be resized")
            return 1
        if self.options.force:
            command.insert(1, "-f")
        if self.options.verbose:
            command.insert(1, "-p")
        if new_size:
            command.append(new_size)
        # Ext3/4 can resize offline in both directions, but It can not shrink
        # the file system while online. In addition ext2 can only resize
        # offline.
        if self.mounted and (self.fstype == "ext2" or
           new_size < self.data['fs_size']):
            raise problem.FsMounted(
                "{0} is mounted on {1}.".format(self.device, self.mounted) +
                " In this case, mounted file system can not be resized.")
        ret = self.fsck()
        if ret:
            raise PR.error("File system on {0} is not ".format(self.device) +
                           "clean, I will not attempt to resize it. Please," +
                           "fix the problem first")
        return misc.run(command, stdout=True)[0]

    def xfs_get_info(self, dev):
        command = ["xfs_db", "-r", "-c", "sb", "-c", "print", dev]
        if not misc.check_binary(command[0]):
            return
        output = misc.run(command)[1]

        for line in output.split("\n")[1:]:
            array = line.split("=")
            if len(array) == 2:
                self.fs_info[array[0].rstrip()] = array[1].lstrip()

        bsize = int(self.fs_info['blocksize'])
        bcount = int(self.fs_info['dblocks'])
        lbcount = int(self.fs_info['logblocks'])
        bcount -= lbcount
        agcount = int(self.fs_info['agcount'])
        fbcount = int(self.fs_info['fdblocks'])
        fbcount -= 4 + (4 + agcount)
        self.data['fs_size'] = bcount * bsize // 1024
        self.data['fs_free'] = fbcount * bsize // 1024
        self.data['fs_used'] = (bcount - fbcount) * bsize // 1024

    def xfs_fsck(self):
        command = ['xfs_repair', '-n']
        if not misc.check_binary(command[0]):
            PR.warn("\'{0}\' tool does not exist. ".format(command[0]) +
                    "File system will not be checked")
            raise problem.ToolMissing("xfs_repair")
        if self.options.verbose:
            command.append('-v')
        command.append(self.device)
        return misc.run(command, stdout=True, can_fail=True)[0]

    def xfs_resize(self, new_size=None):
        command = ['xfs_growfs', self.device]
        if not misc.check_binary(command[0]):
            PR.warn("\'{0}\' tool does not exist. ".format(command[0]) +
                    "File system will not be resized")
            return 1
        if new_size:
            command.insert(1, ['-D', new_size + 'K'])
        if not self.mounted:
            raise PR.error("Xfs file system on {0}".format(self.device) +
                           " has to be mounted to perform an resize")
        elif new_size and new_size < self.data['fs_size']:
            raise PR.error("Xfs file system can not shrink")
        else:
            misc.run(command, stdout=True)


class DeviceInfo(object):
    """
    Parse and store information about the devices present in the system. The
    main source of information are /proc/partitions, /proc/mounts and
    /proc/swaps. self.data should be appended to since there might be other
    data present which will add more information about devices, usually
    provided from backends.

    Important thing is that we hide all dm devices here, since they might
    really be a volumes. We let backend decide whether the device should be
    listed as device or not simply by setting 'hide' to True/False.
    """

    def __init__(self, options, data=None):
        self.type = 'device'
        self.data = data or {}
        self.attrs = ['major', 'minor', 'dev_size', 'dev_name']
        self.options = options

        hide_dmnumbers = []
        for name in ['device-mapper', 'sr', 'md']:
            hide_dmnumbers.append(misc.get_dmnumber(name))

        mounts = misc.get_mounts('/dev/')
        swaps = misc.get_swaps()

        for items in misc.get_partitions():
            devices = dict(zip(self.attrs, items))
            devices['vol_size'] = devices['dev_size']
            devices['dev_name'] = devices['dev_name']
            if devices['major'] in hide_dmnumbers:
                devices['hide'] = True
            if devices['dev_name'] in self.data:
                if 'hide' in self.data[devices['dev_name']] and \
                   not self.data[devices['dev_name']]['hide']:
                    devices['hide'] = False
                self.data[devices['dev_name']].update(devices)
            else:
                self.data[devices['dev_name']] = devices
            if devices['dev_name'] in mounts:
                devices['mount'] = mounts[devices['dev_name']]['mp']

        for item in swaps:
            if item[0] in self.data:
                self.data[item[0]]['mount'] = "SWAP"

        for i, dev in enumerate(self.data.values()):
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

    def remove(self, device):
        PR.error("It is not clear what do you want " +
                 "to achieve by removing " +
                 "{0}".format(device))

    def set_globals(self, options):
        self.options = options

    def __iter__(self):
        for item in sorted(self.data):
            yield item

    def __getitem__(self, name):
        device = misc.get_real_device(name)
        if device in self.data:
            return self.data[device]
        return None


class Item(object):
    """
    Meta object which provides encapsulation for all devices, pools and
    volumes, so we can work with them as with the usual objects without the
    need to call Dev, Pool or Vol methods directly.
    """

    def __init__(self, obj, name):
        self.obj = obj
        self.name = name
        self.type = obj.type

    @property
    def data(self):
        return self.obj[self.name]

    def __getattr__(self, func_name):
        func = getattr(self.obj, func_name)

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
        fs = FsInfo(name, self.obj.options)
        if 'fs_type' not in fs.data:
            # Not a file system
            return
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
    """
    Template class to use for storing information about Pools, Volumes and
    Devices from different backends. This simplify things a lot since we do not
    have to manually walk through all the backends, but this class will do this
    for us.
    """

    def __init__(self, options):
        self._data = {}
        self.header = None
        self.attrs = None
        self.types = None
        self.set_globals(options)

    def __iter__(self):
        for source in self._data.values():
            for item in source:
                yield Item(source, item)

    def __contains__(self, item):
        if self[item]:
            return True
        else:
            return False

    def __getitem__(self, name):
        for source in self._data.values():
            item = source[name]
            if item:
                return Item(source, name)
        return None

    def reinitialize(self):
        self.__init__(self.options)

    def _apply_prefix_filter(self):
        """
        If SSM_PREFIX FILTER is set, remove all items which basenames does not
        start with SSM_PREFIX_FILTER prefix. This is useful especially for
        testing so that ssm see only relevant devices and does not screw real
        system storage configuration.
        """
        if not SSM_PREFIX_FILTER:
            return
        reg = re.compile("^{0}".format(SSM_PREFIX_FILTER))
        for source in self._data.values():
            for item in source:
                if reg.search(os.path.basename(item)):
                    continue
                if 'pool_name' in source.data[item] and \
                   reg.search(source.data[item]['pool_name']):
                    continue
                if 'dm_name' in source.data[item] and \
                   reg.search(os.path.basename(source.data[item]['dm_name'])):
                    continue
                del source.data[item]

    def get_backend(self, name):
        return self._data[name]

    def set_globals(self, options):
        self.options = options
        if self._data is None:
            return
        for source in self._data.values():
            source.options = options

    def filesystems(self):
        for item in self:
            if 'fs_type' in item:
                yield item

    def ptable(self, cond=None, more_data=None, cond_func=None):
        """
        Print information table about the source (devices, pools, volumes)
        using the predefined variables (below). cond, or cond_func can be
        provided to decide which items not to print out.

        self.header - list of headers for the table
        self.attrs - list of attribute keys to print out
        self.types - types of the attributes to print out (str, or float/int)
        """
        lines = []
        fmt = ""

        if cond == "fs_only":
            iterator = self.filesystems()
        else:
            iterator = self

        # Keep track of used columns. Then we only print out columns with
        # values.
        columns = [False] * len(self.attrs)

        len_matrix = []
        index = 0
        # Gather all lines which are going to be printed into the list
        # and create matrix of attribute lengths.
        # Iterate through all items in each data source first.
        for data in misc.chain(iterator, more_data or []):
            if (cond_func and not cond_func(data)) or 'hide' in data:
                continue
            len_matrix.append([len(self.header[i])
                              for i in range(len(self.header))])
            line = ()
            # Iterate through all attributes in each item
            for i, attr in enumerate(self.attrs):
                if self.types[i] in (float, int):
                    item = misc.humanize_size(data[attr])
                elif attr + "_print" in data:
                    item = data[attr + "_print"]
                else:
                    item = data[attr]
                len_matrix[index][i] = len(item)
                line += item,
                if len(item) > 0:
                    columns[i] = True
            lines.append(line)
            index += 1

        if len(lines) == 0:
            return

        header = [item for item in misc.compress(self.header, columns)]
        alignment = list([(len(self.header[i]))
                         for i in range(len(self.header))])
        term_width = misc.terminal_size()[0]

        # Update matrix of attribute lengths and construct the final list
        # of alignment for each column in the table.
        for index in range(len(len_matrix)):
            line = None
            # Find maximum length for each column
            for a, array in enumerate(len_matrix):
                for i, item in enumerate(array):
                    if not columns[i]:
                        alignment[i] = 0
                        continue
                    if item > alignment[i]:
                        alignment[i] = item
                        line = a

            # Check the overall line length and if it is longer then the
            # actual terminal width we can wrap the line right after the
            # first attribute. Simply set the alignment to the smaller
            # possible and let recalculate the list of column alignments.
            # Note that when even with the line wrap we would still exceed
            # the terminal width, then there is nothing we can do about it
            # so do not bother with line wrapping at all since it would
            # only screw the formatting even more.
            length = sum(alignment) + 2 * len(header) - 2
            if length > term_width and \
               (length - term_width) < (alignment[0] - len(header[0])) and \
               line is not None:
                    alignment[0] = len(header[0])
                    len_matrix[line][0] = len(header[0])
            else:
                break

        # Get the actual line width
        width = sum(misc.compress(alignment, columns)) + 2 * len(header) - 2

        pos = 0
        # Use column alignments list to construct formatting string for each
        # line in the table. Note that some lines might be wrapped later on.
        for i, t in enumerate(self.types):
            if not columns[i]:
                continue
            if t in (float, int):
                fmt += "{{{0}:>{1}}}  ".format(pos, alignment[i])
            else:
                # Do not append additional spaces if this is the last item
                if i == len(header) - 1:
                    fmt += "{{{0}:{1}}}".format(pos, alignment[i])
                else:
                    fmt += "{{{0}:{1}}}  ".format(pos, alignment[i])
            pos += 1

        print("-" * width)
        print(fmt.format(*tuple(header)))
        print("-" * width)
        # Now print each line of the table. When the first attribute of the
        # line is longer than it should be we know that we have to wrap the
        # line.
        for i, line in enumerate(lines):
            line = misc.compress(line, columns)
            tmp1 = __next__(line)
            if len(tmp1) > alignment[0]:
                print(tmp1)
                print(fmt.format('', *line))
            else:
                print(fmt.format(tmp1, *line))
        print("-" * width)


class Pool(Storage):
    """
    Store Pools from all the backends. When new backend is added into the ssm
    it should be registered within this class with appropriate name.
    """

    def __init__(self, *args, **kwargs):
        super(Pool, self).__init__(*args, **kwargs)

        try:
            self._data['lvm'] = lvm.VgsInfo(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about LVM pools")
        try:
            self._data['btrfs'] = btrfs.BtrfsPool(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about btrfs pools")
        try:
            self._data['crypt'] = crypt.DmCryptPool(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about crypt pools")

        backend = self.get_backend(SSM_DEFAULT_BACKEND)
        self.default = Item(backend, backend.default_pool_name)
        self.header = ['Pool', 'Type', 'Devices', 'Free', 'Used', 'Total']
        self.attrs = ['pool_name', 'type', 'dev_count', 'pool_free',
                      'pool_used', 'pool_size']
        self.types = [str, str, str, float, float, float]
        self._apply_prefix_filter()


class Devices(Storage):
    """
    Store Devices from all the backends. When new backend is added into the ssm
    it should be registered within this class with appropriate name.

    If the backend only have new information about the device which is already
    discovered by the DeviceInfo() class then it should just add the
    information into the existing devices by passing the data. But if the
    backed discovers new devices, it should add them as a new entry.
    """

    def __init__(self, *args, **kwargs):
        super(Devices, self).__init__(*args, **kwargs)

        try:
            my_lvm = lvm.PvsInfo(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about LVM physical volumes")
        try:
            my_btrfs = btrfs.BtrfsDev(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about btrfs devices")
            my_btrfs = Struct()
            my_btrfs.data = {}
        try:
            my_md = md.MdRaidDevice(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about MD devices")
            my_md = Struct()
            my_md.data = {}
        try:
            my_crypt = crypt.DmCryptDevice(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about crypt devices")
            my_crypt = Struct()
            my_crypt.data = {}

        self._data['dev'] = DeviceInfo(data=dict(list(my_lvm.data.items()) +
                                                 list(my_btrfs.data.items()) +
                                                 list(my_md.data.items()) +
                                                 list(my_crypt.data.items())),
                                       options=self.options)
        self.header = ['Device', 'Free', 'Used',
                       'Total', 'Pool', 'Mount point']
        self.attrs = ['dev_name', 'dev_free', 'dev_used', 'dev_size',
                      'pool_name', 'mount']
        self.types = [str, float, float, float, str, str]
        self._apply_prefix_filter()


class Volumes(Storage):
    """
    Store Volumes from all the backends. When new backend is added into the ssm
    it should be registered withing this class with appropriate name.
    """

    def __init__(self, *args, **kwargs):
        super(Volumes, self).__init__(*args, **kwargs)

        try:
            self._data['lvm'] = lvm.LvsInfo(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about LVM volumes")
        try:
            self._data['crypt'] = crypt.DmCryptVolume(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about crypt volumes")
        try:
            self._data['btrfs'] = btrfs.BtrfsVolume(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about btrfs volumes")
        try:
            self._data['md'] = md.MdRaidVolume(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about md raid volumes")

        self.header = ['Volume', 'Pool', 'Volume size', 'FS', 'FS size',
                       'Free', 'Type', 'Mount point']
        self.attrs = ['dev_name', 'pool_name', 'vol_size', 'fs_type',
                      'fs_size', 'fs_free', 'type', 'mount']
        self.types = [str, str, float, str, float, float, str, str]
        self._apply_prefix_filter()


class Snapshots(Storage):
    """
    Store Snapshots from all the backends that supports snapshotting. When
    the snapshotting support is added into the backed it should be registered
    within this class with appropriate name.
    """

    def __init__(self, *args, **kwargs):
        super(Snapshots, self).__init__(*args, **kwargs)

        try:
            self._data['lvm'] = lvm.SnapInfo(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about LVM snapshots")
        try:
            self._data['btrfs'] = btrfs.BtrfsSnap(options=self.options)
        except RuntimeError as err:
            PR.warn(err)
            PR.warn("Can not get information about btrfs snapshots")

        self.header = ['Snapshot', 'Origin', 'Pool', 'Volume size', 'Used',
                       'Type', 'Mount point']
        self.attrs = ['dev_name', 'origin', 'pool_name', 'vol_size',
                      'snap_size', 'type', 'mount']
        self.types = [str, str, str, float, float, str, str]
        self._apply_prefix_filter()


class StorageHandle(object):
    """
    The main class where all the magic is done. All the commands provided by
    ssm have its appropriate functions here which are then called by argparse.
    """

    def __init__(self, options=Options()):
        self._mpoint = None
        self._dev = None
        self._pool = None
        self._volumes = None
        self._snapshots = None
        self.set_globals(options)
        self.options = options

    def set_globals(self, options):
        if self._dev:
            self.dev.set_globals(options)
        if self._volumes:
            self.vol.set_globals(options)
        if self._pool:
            self.pool.set_globals(options)
        if self._snapshots:
            self.snap.set_globals(options)
        self.options = options

    @property
    def dev(self):
        if self._dev:
            return self._dev
        self._dev = Devices(options=self.options)
        return self._dev

    def reinit_dev(self):
        if self._dev:
            self._dev.reinitialize()

    @property
    def pool(self):
        if self._pool:
            return self._pool
        self._pool = Pool(options=self.options)
        return self._pool

    def reinit_pool(self):
        if self._pool:
            self._pool.reinitialize()

    @property
    def vol(self):
        if self._volumes:
            return self._volumes
        self._volumes = Volumes(options=self.options)
        return self._volumes

    def reinit_vol(self):
        if self._volumes:
            self._volumes.reinitialize()

    @property
    def snap(self):
        if self._snapshots:
            return self._snapshots
        self._snapshots = Snapshots(options=self.options)
        return self._snapshots

    def reinit_snap(self):
        if self._snapshots:
            self._snapshots.reinitialize()

    def _create_fs(self, fstype, volume):
        """
        Create a file system 'fstype' on the 'volume'.
        """
        command = ["mkfs.{0}".format(fstype), volume]
        if not misc.check_binary(command[0]):
            PR.warn("\'{0}\' tool does not exist. ".format(command[0]) +
                    "File system will not be created")
            return 1
        if self.options.force:
            if fstype == 'xfs':
                command.insert(1, '-f')
            if fstype in EXTN:
                command.insert(1, '-F')
        if self.options.verbose:
            if fstype in EXTN:
                command.insert(1, '-v')
        return misc.run(command, stdout=True)[0]

    def _do_mount(self, volume, options=None, directory=None):
        if directory is None:
            directory = self._mpoint
        try:
            volume.mount(directory, options)
        except AttributeError:
            misc.do_mount(volume['real_dev'], directory, options)

    def check(self, args):
        """
        Check the file system on the volume. FsInfo is used for that purpose,
        except for btrfs. Or check the volume itself if backend supports it.
        """
        err = 0
        checked = 0
        for dev in args.device:
            if 'mount' in dev:
                try:
                    if PR.check(PR.FS_MOUNTED, [dev['real_dev'], dev['mount']]):
                        misc.do_umount(dev['real_dev'])
                except problem.FsMounted:
                    PR.warn("Unable to check file system " +
                            "\'{0}\' on volume \'{1}\'".format(dev['fs_type'],
                                                               dev['real_dev']))
                    continue

            # Does backend support check ?
            try:
                if getattr(dev, "check"):
                    print("Checking volume \'{0}\'.".format(dev['real_dev']))
                    ret = dev.check()
                    checked += 1
                    err += ret
                    if ret:
                        continue
            except AttributeError:
                pass

            # Do we have a file system to check ?
            if 'fs_info' in dev:
                fs = dev['fs_info']
                print("Checking {0} file system on \'{1}\'.".format(fs.fstype,
                                                                    fs.device))
                ret = fs.fsck()
                checked += 1
                err += ret
        if checked == 0:
            PR.error("Nothing was checked")
        if err > 0:
            PR.warn("Some file system(s) contains errors. Please run " +
                    "the appropriate fsck utility")

    def _filter_device_list(self, args, have_size=None, new_size=None):
        """
        Filter the args.device list. Only items which have to be added to
        pool are left in the args.device list. Function returns touple
        (have_size, devices) where have_size is the size of the devices which
        will be added to the pool (args.device) plus optional have_size
        argument. Devices is the list of devices which can be used for volume
        creation, it means that it does not contain devices which are used
        in other pools and are not removed from it in this function.
        """

        if have_size is None:
            have_size = 0.0
        else:
            have_size = float(have_size)

        changed = False

        devices = args.device
        args.device = []

        for dev in devices[:]:
            if self.dev[dev] and 'pool_name' in self.dev[dev] and \
               self.dev[dev]['pool_name'] != args.pool.name:
                if PR.check(PR.DEVICE_USED, [dev, self.dev[dev]['pool_name']]):
                    remove_args = Struct()
                    remove_args.all = False
                    remove_args.items = [self.dev[dev]]
                    if self.remove(remove_args):
                        args.device.append(dev)
                        changed = True
                    elif new_size is None:
                        PR.error("Device \'{0}\' can not be used".format(dev))
                    else:
                        devices.remove(dev)
                        continue
                # This is tricky. We are going to create or resize a device
                # so we might actually need the device for create (or resize)
                # to finish successfully. Create and resize should check
                # whether is has enough space and fail if it does not. The
                # problem is, when the size was not specified, then the result
                # would be different than what user expected, so we should fail
                # right away.
                elif new_size is None:
                    PR.error("Device \'{0}\' can not be used".format(dev))
                else:
                    devices.remove(dev)
                    continue

            if not self.dev[dev] or 'pool_name' not in self.dev[dev]:
                # Check signature of existing file system on the device
                # and ask user whether to use it or not.
                if self.dev[dev] and 'mount' in self.dev[dev]:
                    try:
                        if PR.check(PR.FS_MOUNTED,
                                    [dev, self.dev[dev]['mount']]):
                            misc.do_umount(dev)
                    except problem.FsMounted:
                        args.device.remove(dev)
                        continue
                signature = misc.get_fs_type(dev)
                if signature and \
                   PR.check(PR.EXISTING_FILESYSTEM, [signature, dev]):
                    misc.wipefs(dev, signature)
                    args.device.append(dev)
                elif signature:
                    devices.remove(dev)
                    continue
                else:
                    args.device.append(dev)

        if changed:
            self.reinit_dev()

        for dev in devices:
            if not self.dev[dev]:
                have_size += misc.get_file_size(dev)
            else:
                try:
                    have_size += float(self.dev[dev]['dev_free'])
                except ValueError:
                    have_size += float(self.dev[dev]['dev_size'])

        return have_size, devices

    def resize(self, args):
        """
        Resize the volume to the given size. If more devices are provided as
        arguments, it will be added into the pool prior to the volume resize
        only if the space in the pool is not sufficient. That said, only the
        number of devices are added into the pool to be able to cover the
        resize.
        """
        args.pool = self.pool[args.volume['pool_name']]
        vol_size = float(args.volume['vol_size'])

        if args.pool != None and args.pool.type == 'btrfs':
            msg = "Resizing btrfs volume is not supported"
            raise problem.NotSupported(msg)

        if not args.size:
            new_size = vol_size
        elif args.size[0] == '+':
            new_size = vol_size + float(args.size[1:])
        elif args.size[0] == '-':
            new_size = vol_size + float(args.size)
        else:
            new_size = float(args.size)
        size_change = new_size - vol_size

        fs = True if 'fs_info' in args.volume else False

        if new_size <= 0:
            PR.error("New volume size \'{0} KB\' is too small".format(new_size))

        if vol_size == new_size:
            # Try to grow the file system, since there is nothing to
            # do with the volume itself.
            if fs:
                ret = args.volume['fs_info'].resize()
                if ret:
                    PR.error("File system on {0} can not be resized".format(args.volume.name))
            else:
                PR.check(PR.RESIZE_ALREADY_MATCH, [args.volume.name, new_size])
            return

        # Backend might not support pooling
        if args.pool is None:
            pool_free = 0.0
            pool_name = "none"
        else:
            pool_free = float(args.pool['pool_free'])
            pool_name = args.pool.name

        # No need to do anything with provided devices since
        # we do have enough space to cover the resize
        if (pool_free < size_change):
            have_size, devices = self._filter_device_list(args,
                                                          pool_free,
                                                          new_size)
        else:
            have_size = pool_free

        if have_size < size_change:
            PR.check(PR.RESIZE_NOT_ENOUGH_SPACE,
                     [pool_name, args.volume.name, new_size])
        elif len(args.device) > 0 and size_change > pool_free:
            try:
                self.add(args, True)
            except problem.NotSupported:
                # Some backends might not support pooling at all.
                pass

        if new_size != vol_size:
            args.volume.resize(new_size, fs)

    def create(self, args):
        """
        Create new volume (or subvolume in case of btrfs) using the devices
        provided as arguments. If the device is not in the selected pool, then
        add() is called on the pool prior to create().
        """
        if args.mnt_options and not self._mpoint:
            PR.warn("Mount options are set, but no mount point was " +
                    "provided. Device will not be mounted")

        lvname = self.create_volume(args)

        if args.encrypt and misc.is_bdevice(lvname) and \
           SSM_DEFAULT_BACKEND != 'crypt':
            crypt = self.pool.get_backend("crypt")
            args.pool = Item(crypt, crypt.default_pool_name)
            options = {'encrypt': args.encrypt}
            lvname = args.pool.create(devs=[lvname],
                                      size=None,
                                      options=options,
                                      name=args.name)

        if args.fstype and args.pool.type != 'btrfs':
            if self._create_fs(args.fstype, lvname) != 0:
                self._mpoint = None
        if self._mpoint:
            create_directory(self._mpoint)
            self.reinit_vol()
            self._do_mount(self.vol[lvname], args.mnt_options)

    def create_volume(self, args):
        # Get the size in kilobytes
#        if args.size:
#            args.size = misc.get_real_size(args.size)

        if self._mpoint and not (args.fstype or args.pool.type == 'btrfs'):
            if PR.check(PR.CREATE_MOUNT_NOFS, self._mpoint):
                self._mpoint = None

        devices = args.device
        if args.pool.exists():
            pool_free = float(args.pool['pool_free'])
        else:
            pool_free = 0.0

        # If devices were provided we should only use those
        if len(devices) > 0:
            pool_free = None

        have_size, devices = self._filter_device_list(args, pool_free,
                                                      args.size)

        # When the pool does not exist and there is no device usable
        # for creating the new pool, then there is no point of trying to
        # create a volume, since it would fail in the backend anyway.
        if not args.pool.exists() and len(devices) == 0:
            PR.check(PR.NO_DEVICES, args.pool.name)

        # Currently we do not allow setting subvolume size with btrfs. This
        # should change in the future (quotas maybe) so the check should
        # be removed or pushed to the backend itself.
        if args.size and have_size < float(args.size) and \
           not (args.pool.exists() and args.pool.type == 'btrfs'):
            if PR.check(PR.CREATE_NOT_ENOUGH_SPACE,
                        [have_size, args.pool.name]):
                args.size = None

        if have_size == 0:
            PR.error("Not enough space ({0} KB) to".format(have_size) +
                     "to create volume")

        # Number of stripes must not exceed number of devices within the pool
        if args.stripes and len(devices) > 0 and args.stripes > len(devices):
            PR.error("Number of stripes ({0}) ".format(args.stripes) +
                     "must not exceed number of devices " +
                     "({0})".format(len(devices)))
        elif args.stripes and len(devices) == 0 and args.pool.exists():
            tmp = int(args.pool['dev_count'])
            if args.stripes > tmp:
                PR.error("Number of stripes ({0}) ".format(args.stripes) +
                         "must not exceed number of devices " +
                         "({0})".format(tmp))

        if args.raid:
            # In raid we might has a requirement on a number of devices
            # available as well as different requirements on the size
            # available. We do not do any complicated math to figure out
            # whether we really do have enough space on the devices which
            # might differ in size. Let the respective backend tool deal
            # with that, it's always ok to fail, but we might cover the
            # most obvious cases here.
            dev_count = len(args.device)
            if args.pool.exists():
                dev_count += int(args.pool['dev_count'])
            if args.raid == '10' and args.stripes:
                if args.stripes * 2 > dev_count:
                    PR.error("Not enough devices ({0}) ".format(dev_count) +
                             "for specified number of ".format(args.stripes) +
                             "stripes ({0}). You need ".format(args.stripes) +
                             "at least {0} devices".format(args.stripes * 2))
            if args.raid == '1' and dev_count < 2:
                PR.error("You need at least 2 devices to create " +
                         "raid1 volume")

        # If we want btrfs pool and it does not exist yet, we do not
        # want to call add since it would create it. Note that when
        # btrfs pool is created the new btrfs volume is created as well
        # because it is actually the same thing
        if len(args.device) > 0 and \
           not (not args.pool.exists() and args.pool.type == 'btrfs'):
            try:
                self.add(args, True)
            except problem.NotSupported:
                # Some backends might not support pooling at all.
                pass

        options = {}
        if args.encrypt:
            options['encrypt'] = args.encrypt
        if args.raid:
            options['raid'] = args.raid
            options['stripesize'] = args.stripesize
            options['stripes'] = args.stripes

        lvname = args.pool.create(devs=devices,
                                  size=args.size,
                                  options=options,
                                  name=args.name)
        return lvname

    def list(self, args):
        """
        List devices, pools, volumes
        """
        if not args.type:
            self.dev.ptable()
            self.pool.ptable()
            self.vol.ptable(more_data=self.dev.filesystems())
            self.snap.ptable()
        elif args.type in ['fs', 'filesystems']:
            self.vol.ptable(more_data=self.dev.filesystems(), cond="fs_only")
        elif args.type in ['dev', 'devices']:
            self.dev.ptable()
        elif args.type in ["volumes", "vol"]:
            self.vol.ptable(more_data=self.dev.filesystems())
        elif args.type in ["pool", "pools"]:
            self.pool.ptable()
        elif args.type in ['snap', 'snapshots']:
            self.snap.ptable()

    def add(self, args, skip_check=False):
        """
        Add devices into the pool
        """
        if not skip_check:
            for dev in args.device[:]:
                item = self.dev[dev]
                if item and 'pool_name' in item:
                    if item['pool_name'] == args.pool.name:
                        args.device.remove(dev)
                        continue
                    if PR.check(PR.DEVICE_USED,
                                [item.name, item['pool_name']]):
                        remove_args = Struct()
                        remove_args.all = False
                        remove_args.items = [item]
                        if not self.remove(remove_args):
                            args.device.remove(item.name)
                    else:
                        args.device.remove(dev)
                else:
                    # Check signature of existing file system on the device
                    # and as user whether to use it or not.
                    if item and 'mount' in item:
                        try:
                            if PR.check(PR.FS_MOUNTED, [dev, item['mount']]):
                                misc.do_umount(dev)
                        except problem.FsMounted:
                            args.device.remove(dev)
                            continue
                    else:
                        signature = misc.get_fs_type(dev)
                        if signature and \
                           PR.check(PR.EXISTING_FILESYSTEM,
                                        [signature, dev]):
                            misc.wipefs(dev, signature)
                        elif signature:
                            args.device.remove(dev)
                            continue

        if args.pool.exists():
            if len(args.device) > 0:
                args.pool.extend(args.device)
            else:
                PR.check(PR.NO_DEVICES, args.pool.name)
        else:
            if len(args.device) > 0:
                args.pool.new(args.device)
            else:
                PR.check(PR.NO_DEVICES, args.pool.name)

    def remove(self, args):
        """
        Remove the all the items, or all pools if all argument is specified.
        Items could be the devices, pools or volumes.
        """
        ret = True
        removed = 0
        if args.all:
            for pool in self.pool:
                try:
                    pool.remove()
                    removed += 1
                except (RuntimeError, problem.SsmError):
                    PR.info("Unable to remove '{0}'".format(pool['pool_name']))
                    ret = False
            if removed == 0:
                PR.error("Nothing was removed")
            return ret
        if len(args.items) == 0:
            err = "too few arguments"
            raise argparse.ArgumentTypeError(err)
        for item in args.items:
            try:
                if isinstance(item.obj, DeviceInfo):
                    pool = self.pool[item['pool_name']]
                    if pool:
                        pool.reduce(item.name)
                        removed += 1
                        continue

                item.remove()
                removed += 1
            except (RuntimeError, problem.SsmError) as ex:
                PR.info("Unable to remove '{0}'".format(item.name))
                ret = False
        if removed == 0:
            PR.error("Nothing was removed")
        return ret

    def snapshot(self, args):
        """
        Create a new snapshot of the volume.
        """
        pool = self.pool[args.volume['pool_name']]
        vol_size = float(args.volume['vol_size'])
        pool_free = float(pool['pool_free'])

        if not args.size:
        # We'll ceate snapshot of the size of 20% of the original volume
            snap_size = vol_size * 0.20
            user_set_size = False
        else:
            snap_size = float(args.size)
            #snap_size = float(misc.get_real_size(args.size))
            user_set_size = True

        if pool_free < snap_size:
            snap_size = pool_free

        if snap_size <= 0 and pool.type != 'btrfs':
            PR.error("Not enough space ({0} KB) to".format(pool_free) +
                     "to create snapshot")

        args.volume.snapshot(args.dest, args.name, snap_size, user_set_size)

    def mount(self, args):
        """
        Mount a volume at given directory.
        """
        create_directory(args.directory)
        vol = self.vol[args.volume]
        try:
            if vol:
                self._do_mount(vol, args.options, args.directory)
            else:
                misc.do_mount(args.volume, args.directory, args.options)
        except RuntimeError:
            PR.error("Could not mount {0} to ".format(args.volume) +
                     "{0} with options \'{1}\'".format(args.directory,
                                                       args.options))

    def can_check(self, device):
        fs = self.is_fs(device)
        if fs is False:
            real = misc.get_real_device(device)
            vol = self.vol[real]
            err = "'{0}' is not valid volume to check.".format(device)
            try:
                if not getattr(vol, "check"):
                    raise argparse.ArgumentTypeError(err)
                else:
                    return vol
            except AttributeError:
                raise argparse.ArgumentTypeError(err)
        else:
            return fs


    def is_fs(self, device):
        real = misc.get_real_device(device)

        vol = self.vol[real]
        if vol and 'fs_info' in vol:
            return vol
        dev = self.dev[real]
        if dev and 'fs_info' in dev:
            return dev
        return False

    def _find_device_record(self, path):
        """
        Try to find device name for path, which is used as an key in
        self.dev - this is usually the real block device, but in some
        rare cases (dmsetup) we can have real block device which name
        does not correspond with what we have in /proc/partitions
        """
        if self.dev[path]:
            return path

        minor = os.minor(os.lstat(path).st_rdev)
        dm_dev = "/dev/dm-{0}".format(minor)
        if self.dev[dm_dev]:
            return dm_dev
        else:
            return path

    def check_create_item(self, path):
        """
        Check the create argument for block device or directory.
        """
        if not self._mpoint:
            try:
                mode = os.stat(path).st_mode
            except OSError:
                self._mpoint = path
                return
            if stat.S_ISDIR(mode):
                self._mpoint = path
                return
        return self.get_bdevice(path)

    def get_bdevice(self, path):
        path = misc.is_bdevice(path)
        if path == False:
            err = "'{0}' is not valid block device".format(path)
            raise argparse.ArgumentTypeError(err)
        return self._find_device_record(path)

    def is_pool(self, string):
        pool = self.pool[string]
        if not pool:
            if string:
                self.pool.default.name = string
            pool = self.pool.default
        return pool

    def is_volume(self, string):
        vol = self.vol[string]
        if vol:
            return vol
        dev = self.dev[string]
        if dev and 'fs_info' in dev:
            return dev
        err = "'{0}' is not a valid volume to resize".format(string)
        raise argparse.ArgumentTypeError(err)

    def can_snapshot(self, string):
        vol = self.vol[string]
        have = False
        if not vol:
            for vol in self.vol:
                if 'mount' in vol and (vol['mount'] == string.rstrip("/")):
                    have = True
                    break
        else:
            have = True
        if not have:
            err = "'{0}' is not valid volume nor mount point.".format(string)
            raise argparse.ArgumentTypeError(err)
        else:
            err = "Backend for '{0}' ".format(string) + \
                  "does not support snapshotting."
            try:
                if not getattr(vol, "snapshot"):
                    raise argparse.ArgumentTypeError(err)
                else:
                    return vol
            except AttributeError:
                raise argparse.ArgumentTypeError(err)

    def check_remove_item(self, string):
        """
        Check the remove argument for volume, pool or device.
        """
        volume = self.vol[string]
        if volume:
            return volume
        pool = self.pool[string]
        if pool:
            return pool
        device = self.dev[string]
        if device:
            return device
        else:
            try:
                path = self.get_bdevice(string)
                device = self.dev[path]
                if device:
                    return device
            except argparse.ArgumentTypeError:
                pass
        for vol in self.vol:
            if 'mount' in vol and (vol['mount'] == string.rstrip("/")):
                return vol
        err = "'{0}' is not valid pool nor volume".format(string)
        raise argparse.ArgumentTypeError(err)


def valid_size(size):
    """ Validate that the 'size' is usable size argument. This is almost the
    same as valid_resize_size() except we do not allow '+' and '-' signs
    """

    err = "'{0}' is not valid size.".format(size)
    if len(size) and size[0] in ['+', '-']:
        raise argparse.ArgumentTypeError(err)
    try:
        ret = misc.get_real_size(size)
        if float(ret) < 0:
            raise argparse.ArgumentTypeError(err)
    except:
        raise argparse.ArgumentTypeError(err)
    return ret


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


def is_directory(string):
    """
    Check whether the directory exists, or could be created.
    """
    if string is None:
        err = "Directory name not defined."
        raise argparse.ArgumentTypeError(err)
    try:
        mode = os.lstat(string).st_mode
    except OSError:
        return string
    if stat.S_ISDIR(mode):
        return string
    else:
        err = "'{0}' is not directory.".format(string)
        raise argparse.ArgumentTypeError(err)


def create_directory(string):
    # Create directory if it does not exist, the rest of the check
    # is already done in is_directory
    if os.path.isdir(string):
        return
    if not PR.check(PR.CREATE_DIRECTORY, string):
        PR.error("Directory '{0}' does not exist".format(string))
    try:
        os.mkdir(string)
    except OSError:
        PR.error("Directory '{0}' can\'t be created".format(string))


def is_supported_fs(fs):
    if fs in SUPPORTED_FS:
        return fs
    err = "'{0}' is not supported file system".format(fs)
    raise argparse.ArgumentTypeError(err)


class SsmParser(object):
    """
    This class is used to generate argparse parser and run the actual
    parsing.
    """

    def __init__(self, storage, prog=None):
        self.storage = storage
        self.parser = self._get_parser_global(prog)
        self.subcommands = self.parser.add_subparsers(title="Commands", dest="too few arguments")
        self.subcommands.required = True
        self.parser_check = self._get_parser_check()
        self.parser_resize = self._get_parser_resize()
        self.parser_create = self._get_parser_create()
        self.parser_list = self._get_parser_list()
        self.parser_add = self._get_parser_add()
        self.parser_remove = self._get_parser_remove()
        self.parser_snapshot = self._get_parser_snapshot()
        self.parser_mount = self._get_parser_mount()
        self.args = None

    def parse(self):
        self.args = self.parser.parse_args()
        return self.args

    def _get_parser_global(self, prog):
        """
        General ssm options
        """
        parser = argparse.ArgumentParser(
                description="System Storage Manager", prog=prog,
                epilog='''To get help for particular command please specify
                       \'%(prog)s [command] -h\'.''')
        parser.add_argument('--version', action='version',
                version='%(prog)s {0}'.format(VERSION))
        parser.add_argument('-v', '--verbose',
                help="Show aditional information while executing.",
                action="store_true")
        parser.add_argument('-f', '--force',
                help="Force execution in the case where ssm has some " +
                     "doubts or questions.",
                action="store_true")
        parser.add_argument('-b', '--backend', nargs=1,
                metavar='BACKEND',
                help="Choose backend to use. Currently you can choose from " +
                     "({0}).".format(",".join(SUPPORTED_BACKENDS)),
                choices=SUPPORTED_BACKENDS,
                action=SetBackend)
        parser.add_argument('-n', '--dry-run',
                help='''Dry run. Do not do anything, just parse the command
                     line options and gather system information if necessary.
                     Note that with this option ssm will not perform all the
                     check as some of them are done by the backends
                     themselves. This option is mainly used for debugging
                     purposes, but still requires root privileges.''',
                action="store_true")
        return parser

    def _get_parser_check(self):
        """
        Check command
        """
        parser_check = self.subcommands.add_parser("check",
                help="Check consistency of the file system on the device.")
        parser_check.add_argument('device', nargs='+',
                help="Device with file system to check.",
                type=self.storage.can_check)
        parser_check.set_defaults(func=self.storage.check)
        return parser_check

    def _get_parser_resize(self):
        """
        Resize command
        """
        parser_resize = self.subcommands.add_parser("resize",
                help="Change or set the volume and file system size.")
        parser_resize.add_argument("volume", help="Volume to resize.",
                type=self.storage.is_volume)
        parser_resize.add_argument('-s', '--size',
                help='''New size of the volume. With the + or - sign the
                     value is added to or subtracted from the actual size of
                     the volume and without it, the value will be set as the
                     new volume size. A size suffix of [k|K] for kilobytes,
                     [m|M] for megabytes, [g|G] for gigabytes, [t|T] for
                     terabytes or [p|P] for petabytes is optional. If no unit
                     is provided the default is kilobytes.''',
                type=valid_resize_size)
        parser_resize.add_argument("device", nargs='*',
                help='''Devices to use for extending the volume. If the
                     device is not in any pool, it is added into the
                     volume's pool prior to the extension. Note that only
                     really needed number of devices are added into the pool
                     prior the resize.''')
        parser_resize.set_defaults(func=self.storage.resize)
        return parser_resize

    def _get_parser_create(self):
        """
        Create command
        """
        parser_create = self.subcommands.add_parser("create",
                help="Create a new volume with defined parameters.")
        parser_create.add_argument('-s', '--size',
                help='''Gives the size to allocate for the new logical volume
                     A size suffix K|k, M|m, G|g, T|t, P|p, E|e can be used
                     to define 'power of two' units. If no unit is provided, it
                     defaults to kilobytes. This is optional if if
                     not given maximum possible size will be used.''',
                type=valid_size)
        parser_create.add_argument('-n', '--name',
                help='''The name for the new logical volume. This is optional
                     and if omitted, name will be generated by the
                     corresponding backend.''')
        parser_create.add_argument('--fstype',
                help='''Gives the file system type to create on the new
                     logical volume. Supported file systems are (ext3,
                     ext4, xfs, btrfs). This is optional and if not given
                     file system will not be created.''',
                type=is_supported_fs)
        parser_create.add_argument('-r', '--raid', choices=SUPPORTED_RAID,
                metavar="LEVEL",
                help='''Specify a RAID level you want to use when creating a new
                     volume. Note that some backends might not implement all
                     supported RAID levels. This is optional and if no specified,
                     linear volume will be created. You can choose from the
                     following list of supported levels
                     ({0}).'''.format(",".join(SUPPORTED_RAID)))
        parser_create.add_argument('-I', '--stripesize',
                type=int,
                help='''Gives the number of kilobytes for the granularity
                        of stripes. This is optional and if not given, backend
                        default will be used. Note that you have to specify RAID
                        level as well.''')
        parser_create.add_argument('-i', '--stripes',
                type=int,
                help='''Gives the number of stripes. This is equal to the
                     number of physical volumes to scatter the logical
                     volume. This is optional and if stripesize is set
                     and multiple devices are provided stripes is
                     determined automatically from the number of devices. Note
                     that you have to specify RAID level as well.''')
        parser_create.add_argument('-p', '--pool', default="",
                help="Pool to use to create the new volume.",
                type=self.storage.is_pool)
        parser_create.add_argument('-e', '--encrypt', nargs='?',
                choices=crypt.SUPPORTED_CRYPT, const=True,
                help='''Create encrpted volume. Extension to use can be
                     specified.''')
        parser_create.add_argument('-o', '--mnt-options',
                help='''Mount options are specified with a -o flag followed
                     by a comma separated string of options. This option is
                     equivalent to the -o mount(8) option.''')
        parser_create.add_argument('device', nargs='*',
                help='''Devices to use for creating the volume. If the device
                     is not in any pool, it is added into the pool prior the
                     volume creation.''',
                type=self.storage.check_create_item,
                action=StoreAll)
        parser_create.add_argument('mount', nargs='?',
                help='''Directory to mount the newly create volume to.''')
        parser_create.set_defaults(func=self.storage.create)
        return parser_create

    def _get_parser_list(self):
        """
        List command
        """
        parser_list = self.subcommands.add_parser("list",
                help='''List information about
                     all detected, devices, pools, volumes and snapshots
                     in the system.''')
        parser_list.add_argument('type', nargs='?',
                choices=["volumes", "vol", "dev", "devices", "pool", "pools",
                    "fs", "filesystems", "snap", "snapshots"])
        parser_list.set_defaults(func=self.storage.list)
        return parser_list

    def _get_parser_add(self):
        """
        Add command
        """
        parser_add = self.subcommands.add_parser("add",
                help='''Add one or more devices into the pool.''')
        parser_add.add_argument('-p', '--pool', default="",
                help='''Pool to add device into. If not specified the default
                     pool is used.''', type=self.storage.is_pool)
        parser_add.add_argument('device', nargs='+',
                help="Devices to add into the pool.",
                type=self.storage.get_bdevice,
                action=StoreAll)
        parser_add.set_defaults(func=self.storage.add)
        return parser_add

    def _get_parser_remove(self):
        """
        Remove command
        """
        parser_remove = self.subcommands.add_parser("remove",
                help='''Remove devices from the pool, volumes or pools.''')
        parser_remove.add_argument('-a', '--all', action="store_true",
                help="Remove all pools in the system.")
        parser_remove.add_argument('items', nargs='*',
                help="Items to remove. Item could be device, pool, or volume.",
                type=self.storage.check_remove_item)
        parser_remove.set_defaults(func=self.storage.remove)
        return parser_remove

    def _get_parser_snapshot(self):
        """
        Snapshot command
        """
        parser_snapshot = self.subcommands.add_parser("snapshot",
                help='''Take a snapshot of the existing volume.''')
        parser_snapshot.add_argument('-s', '--size',
                help='''Gives the size to allocate for the new snapshot volume
                     A size suffix K|k, M|m, G|g, T|t, P|p, E|e can be used
                     to define 'power of two' units. If no unit is provided, it
                     defaults to kilobytes. This is option and if not give,
                     the size will be determined automatically.''',
                type=valid_size)
        group = parser_snapshot.add_mutually_exclusive_group()
        group.add_argument('-d', '--dest',
                help='''Destination of the snapshot specified with absolute
                     path to be used for the new snapshot. This is optional
                     and if not specified default backend policy will be
                     performed.''')
        group.add_argument('-n', '--name',
                help='''Name of the new snapshot. This is optional and if not
                     specified  default backend policy will be performed.''')

        parser_snapshot.add_argument('volume',
                help="Volume, or mount point to take a snapshot of.",
                type=self.storage.can_snapshot)
        parser_snapshot.set_defaults(func=self.storage.snapshot)
        return parser_snapshot

    def _get_parser_mount(self):
        """
        Mount command
        """
        parser_mount = self.subcommands.add_parser("mount",
                help='''Mount a volume with file system to specified
                     locaion.''')
        parser_mount.add_argument('-o', '--options',
                help='''Options are specified with a -o flag followed by a
                     comma separated string of options. This option is
                     equivalent to the same mount(8) option.''')
        parser_mount.add_argument("volume", help="Volume to mount.")
        parser_mount.add_argument("directory",
                help="Directory to attach the volume.",
                type=is_directory)
        parser_mount.set_defaults(func=self.storage.mount)
        return parser_mount


def main(args=None):

    if args:
        sys.argv = args.split()

    options = Options()
    PR.set_options(options)
    storage = StorageHandle(options)
    ssm_parser = SsmParser(storage)
    args = ssm_parser.parse()

    # Check create command dependency
    if args.func == storage.create:
        if not args.raid:
            if (args.stripesize):
                err = "You can not specify --stripesize without specifying" + \
                      " RAID level!"
                ssm_parser.parser_create.error(err)
            if (args.stripes):
                err = "You can not specify --stripes without specifying" + \
                      " RAID level!"
                ssm_parser.parser_create.error(err)

    options.verbose = args.verbose
    options.force = args.force

    #storage.set_globals(args.force, args.verbose, args.yes, args.config)
    storage.set_globals(options)

    # Register clean-up function on exit
    atexit.register(misc.do_cleanup)

    if args.dry_run:
        return 0

    try:
        args.func(args)
    except argparse.ArgumentTypeError as ex:
        ssm_parser.parser.error(ex)

    return 0
