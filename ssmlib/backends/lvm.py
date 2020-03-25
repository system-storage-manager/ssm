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

# lvm module for System Storage Manager

import re
import os
import stat
import datetime
from ssmlib import misc
from ssmlib import problem
from ssmlib.backends import template

__all__ = ["PvsInfo", "VgsInfo", "LvsInfo", "ThinPool"]

try:
    SSM_LVM_DEFAULT_POOL = os.environ['SSM_LVM_DEFAULT_POOL']
except KeyError:
    SSM_LVM_DEFAULT_POOL = "lvm_pool"

try:
    DM_DEV_DIR = os.environ['DM_DEV_DIR']
except KeyError:
    DM_DEV_DIR = "/dev"
MAX_LVS = 999

# TODO: This is ugly and needs to be removed and done properly
THIN_POOL_DATA = {}

def get_lvm_version():
    try:
        output = misc.run(['lvm', 'version'], can_fail=True)[1]
        output = output.strip().split("\n")
        pattern = re.compile("LVM version:")
        version = [0, 0, 0]
        for line in output:
            if pattern.match(line.strip()):
                match = " ".join(line.split())
                tmp = re.search(r'(?<=LVM version: )\d+\.\d+\.\d+',
                                    match).group(0)
                version = list(map(int, tmp.split(".", 3)))
    except (OSError, AttributeError):
        version = [0, 0, 0]
    return version

LVM_VERSION = get_lvm_version()

def create_thin_volume(parent_pool, thin_pool, virtsize, lvname):
    pool_volume = parent_pool + '/' + thin_pool

    # Ignore options for non existing thin volumes somehow
    command = ['lvcreate', '-n', lvname, '-T', pool_volume,
               '-V', str(virtsize) + 'K']
    command.insert(0, "lvm")
    misc.run(command, stdout=True)
    return "{0}/{1}/{2}".format(DM_DEV_DIR, parent_pool, lvname)


class LvmInfo(template.Backend):

    def __init__(self, *args, **kwargs):
        super(LvmInfo, self).__init__(*args, **kwargs)
        self.type = 'lvm'
        self.attrs = []
        self.binary = misc.check_binary('lvm')
        self.default_pool_name = SSM_LVM_DEFAULT_POOL
        self.init_local_problem_set()

    def parse_attr(self, lv, attr):
        if attr[4] == 'a':
            lv['active'] = True
        else:
            lv['active'] = False

    def init_local_problem_set(self):
        self.DEVICE_INACTIVE = \
            ['Device \'{0}\' is not active! It might contain filesystem we\'re unable to detect and it may be destroyed by this operation.',
             problem.PROMPT_CONTINUE,
             problem.FL_DEFAULT_NO | problem.FL_EXIT_ON_NO | problem.FL_FORCE_YES,
             problem.GeneralError]

    def run_lvm(self, command, noforce=False):
        if not self.binary:
            self.problem.check(self.problem.TOOL_MISSING, 'lvm')
        if self.options.force and not noforce:
            command.insert(1, "-f")
        if self.options.verbose:
            command.insert(1, "-v")
        command.insert(0, "lvm")
        misc.run(command, stdout=True)

    def _data_index(self, row):
        return row.values()[len(row.values()) - 1]

    def _skip_data(self, row):
        return False

    def _parse_data(self, command):
        if not self.binary:
            return
        ret, self.output, err = misc.run(command, stderr=False, can_fail=True)
        # A workaround for LVM behaviour:
        # lvm lvs' exit code is 5 on exported volumes, even if everything
        # is ok. So, if the code is 5, command was 'lvm lvs ...'
        # and error message says that a volume was exported, ignore the
        # error
        if ret != 0:
            err_msg = "ERROR exit code {0} for running command: \"{1}\"".format(
                      ret, " ".join(command))
            if ret != 5 or command[0:2] != ['lvm', 'lvs'] or \
               not str(err).endswith('is exported\n'):
                if err is not None:
                    print(err)
                raise problem.CommandFailed(err_msg, exitcode=ret)

        for line in self.output.split("\n"):
            if not line:
                break
            array = line.split("|")
            row = dict([(self.attrs[index], array[index].lstrip())
                       for index in range(len(array))])
            if self._skip_data(row):
                continue
            self._fill_additional_info(row)
            self.data[self._data_index(row)] = row

    def _fill_additional_info(self, row):
        pass

    def supported_since(self, version, string):
        if version > LVM_VERSION:
            msg = "ERROR: You need at least lvm version " + \
                  "{0}. Feature \"{1}\"".format(".".join(map(str, version)),
                                                string)
            self.problem.check(self.problem.NOT_SUPPORTED, msg)
        return True

    def require_thin_support(self):

        # Old versions of lvm had a bug for some cases of thin provisioning.
        # Because Debian 8 still has an affected version in its repository,
        # check the version and prevent any thin provisioning related
        # operations.
        self.supported_since([2,2,112],"thin provisioning")

        # Test if thin provisioning tools are installed.
        # SSM is not directly using them, but lvm does. ome distributions
        # have it only as an optional dependency for lvm2 and if it is not installed,
        # lvm behaves strangely and can fail without any useful information
        # in middle of a sequence of commands SSM does.
        found = False
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            if os.path.isfile(os.path.join(path, 'thin_check')):
                    found = True
                    break

        if not found:
            msg = "ERROR: lvm does not have installed thin provisioning tools. " +\
                  "Some distributions mark it as an optional dependency for lvm2, " +\
                  "in which case, you need to install it manually"
            self.problem.check(self.problem.GENERAL_ERROR, msg)

        return True


class VgsInfo(LvmInfo, template.BackendPool):

    def __init__(self, *args, **kwargs):
        super(VgsInfo, self).__init__(*args, **kwargs)
        command = ["lvm", "vgs", "--separator", "|", "--noheadings",
                   "--nosuffix", "--units", "k", "-o",
                   "vg_name,pv_count,vg_size,vg_free,lv_count"]
        self.attrs = ['pool_name', 'dev_count', 'pool_size', 'pool_free',
                      'vol_count']

        self._parse_data(command)

    def _fill_additional_info(self, vg):
        vg['type'] = 'lvm'
        vg['pool_used'] = float(vg['pool_size']) - float(vg['pool_free'])

    def _data_index(self, row):
        return row['pool_name']

    def _generate_lvname(self, lvname, vg):
        for i in range(1, MAX_LVS):
            name = "{0}{1:0>{align}}".format(lvname, i, align=len(str(MAX_LVS)))
            path = "{0}/{1}/{2}".format(DM_DEV_DIR, vg, name)
            if "{}/{}".format(vg, name) in THIN_POOL_DATA:
                continue
            try:
                if stat.S_ISBLK(os.stat(path).st_mode):
                    continue
            except OSError:
                pass
            return name
        self.problem.error("Can not find proper lvname!")

    def reduce(self, vg, device):
        command = ['vgreduce', vg, device]
        self.run_lvm(command)

    def new(self, vg, devices):
        if type(devices) is not list:
            devices = [devices]
        command = ['vgcreate', vg]
        command.extend(devices)
        self.run_lvm(command)

    def extend(self, vg, devices):
        if type(devices) is not list:
            devices = [devices]
        command = ['vgextend', vg]
        command.extend(devices)
        self.run_lvm(command)

    def remove(self, vg):
        command = ['vgremove', vg]
        self.run_lvm(command)

    def create(self, vg, size=None, name=None, devs=None,
               options=None):
        options = options or {}
        devices = devs or []
        command = ['lvcreate', vg]

        if 'virtsize' in options:
            # We're going to create new lv which is going to be thin pool
            # so name it appropriately
            lvname = self._generate_lvname(vg + "_thin", vg)
        elif name:
            lvname = name
        else:
            lvname = self._generate_lvname("lvol", vg)

        if 'virtsize' in options:
            self.require_thin_support()
            command.extend(['-T'])

        if size:
            command.extend(['-L', str(size) + 'K'])
        else:
            if len(devices) > 0:
                tmp = "100%PVS"
            else:
                tmp = "100%FREE"
            command.extend(['-l', tmp])

        command.extend(['-n', lvname.rpartition("/")[-1]])

        if 'raid' in options:
            if options['raid'] == '0':
                if not options['stripesize']:
                    options['stripesize'] = "64"
                if not options['stripes'] and len(devices) > 0:
                    options['stripes'] = str(len(devices))
                if not options['stripes']:
                    self.problem.error("Devices or number of " +
                                       "stripes should be defined!")
                if options['stripesize']:
                    command.extend(['-I', options['stripesize']])
                if options['stripes']:
                    command.extend(['-i', options['stripes']])
            elif options['raid'] == '1' and \
                 self.supported_since([2,2,89],"raid1"):
                if options['stripesize'] or options['stripes']:
                    msg = "ERROR: Specifying stripe size or number of " + \
                          "stripes when creating raid1 volume with lvm backend"
                    self.problem.check(self.problem.NOT_SUPPORTED, msg)
                # Unfortunately 50%PVS does not work here because it does not
                # take in account metadata needed to create mirrored volume.
                # Using 49%PVS is not viable either because it will cut off
                # a lot of potential storage. So we'll require to specify
                # size in this case.
                if not size:
                    msg = "ERROR: Creating raid1 with lvm backend without " + \
                          "specifying size"
                    self.problem.check(self.problem.NOT_SUPPORTED, msg)
                command.extend(["--type", "raid1"])
            elif options['raid'] == '10' and \
                 self.supported_since([2,2,98],"raid10"):
                if not options['stripesize']:
                    options['stripesize'] = "64"
                if not options['stripes'] and len(devices) > 0:
                    if len(devices) < 4:
                        self.problem.error("Number of devices should be at " +
                                           "least 4 in raid 10 setup")
                    if len(devices) % 2 != 0:
                        self.problem.error("Number of devices should be " +
                                           "even in raid 10 setup")
                    options['stripes'] = str(len(devices)//2)
                if not options['stripes']:
                    self.problem.error("Devices or number of " +
                                       "stripes should be defined")
                if int(options['stripes']) < 2:
                    self.problem.error("Number of stripes should be at " +
                                       "least 2 in raid 10 setup")
                if options['stripesize']:
                    command.extend(['-I', options['stripesize']])
                if options['stripes']:
                    command.extend(['-i', options['stripes']])
                if not size:
                    msg = "ERROR: Creating raid10 with lvm backend without " + \
                          "specifying size"
                    self.problem.check(self.problem.NOT_SUPPORTED, msg)
                command.extend(["--type", "raid10"])
            else:
                self.problem.not_supported("RAID level {0}".format(options['raid']) +
                                           " with \"lvm\" backend")

        # This should be done only if necessary - for example when the size
        # was not provided and is used as %PVS, otherwise let lvm decide
        # which devices to use from the pool.
        command.extend(devices)
        self.run_lvm(command, noforce=True)
        path = "{0}/{1}/{2}".format(DM_DEV_DIR, vg, lvname)
        if 'virtsize' in options:
            thin_pool = lvname
            if name:
                lvname = name
            else:
                lvname = self._generate_lvname("tvol", vg)
            path = create_thin_volume(vg, thin_pool, options['virtsize'], lvname)
        return path

    def migrate(self, vg, source, target):
        """ Migrate a PV to a new device using pvmove.

        Parameters
        ----------
        vg : [str]
            Volume group into which the PV belongs.
        source : [main.DeviceItem]
            Source PV device.
        target : [str]
            Path to the target device.
        """
        # We're ready to do pvmove source and target must be already in the
        # pool

        # pvmove does not accept -f, temporarily unset it
        force = self.options.force
        self.options.force = False

        # If the source is not used we do not have to do anything
        if float(source['dev_used']) > 0.0:
            command = ['pvmove', '--atomic', source.name, target ]
            self.run_lvm(command)

        misc.send_udev_event(source.name, "change")
        misc.send_udev_event(target, "change")

        # restore saved value
        self.options.force = force


class PvsInfo(LvmInfo, template.BackendDevice):

    def __init__(self, *args, **kwargs):
        super(PvsInfo, self).__init__(*args, **kwargs)
        command = ["lvm", "pvs", "--separator", "|", "--noheadings",
                   "--nosuffix", "--units", "k", "-o",
                   "pv_name,vg_name,pv_free,pv_used,pv_size"]
        self.attrs = ['dev_name', 'pool_name', 'dev_free',
                      'dev_used', 'dev_size']

        self._parse_data(command)

    def _data_index(self, row):
        return misc.get_real_device(row['dev_name'])

    def _fill_additional_info(self, pv):
        pv['hide'] = False
        # If the device is not in any group we do not need this info
        # and we do not want it to show up in the device listing
        if not pv['pool_name']:
            pv['dev_used'] = ''
            pv['dev_free'] = ''
            del pv['pool_name']

    def remove(self, devices):
        if len(devices) == 0:
            return
        command = ['pvremove']
        command.extend(devices)
        self.run_lvm(command)


class LvsInfo(LvmInfo, template.BackendVolume):

    def __init__(self, *args, **kwargs):
        super(LvsInfo, self).__init__(*args, **kwargs)
        command = ["lvm", "lvs", "--separator", "|", "--noheadings",
                   "--nosuffix", "--units", "k", "-o",
                   "vg_name,lv_size,stripes,stripesize,segtype,lv_name,origin,lv_attr,pool_lv"]
        self.attrs = ['pool_name', 'vol_size', 'stripes',
                      'stripesize', 'type', 'lv_name', 'origin', 'attr', 'pool_lv']
        self.handle_fs = True
        self.mounts = misc.get_mounts('{0}/mapper'.format(DM_DEV_DIR))
        self.swaps = misc.get_swaps()
        self._parse_data(command)

    def _fill_additional_info(self, lv):
        lv['dev_name'] = "{0}/{1}/{2}".format(DM_DEV_DIR, lv['pool_name'],
                                              lv['lv_name'])
        if lv['origin'] or \
           lv['attr'][0] == 't':
            lv['hide'] = True

        # Show thin-pool as a pool name in case of thin volumes
        if lv['type'] == 'thin':
            lv['parent_pool'] = lv['pool_name']
            lv['pool_name'] = lv['pool_lv']

        lv['real_dev'] = misc.get_real_device(lv['dev_name'])

        sysfile = "/sys/block/{0}/dm/name".format(
                  os.path.basename(lv['real_dev']))

        # In some weird cases the "real" device might not be in /dev/dm-*
        # form (see tests). In this case constructed sysfile will not exist
        # so we just use real device name to search mounts.
        try:
            with open(sysfile, 'r') as f:
                lvname = f.readline()[:-1]
            lv['dm_name'] = "{0}/mapper/{1}".format(DM_DEV_DIR, lvname)
        except IOError:
            lv['dm_name'] = lv['real_dev']

        if lv['real_dev'] in self.mounts:
            lv['mount'] = self.mounts[lv['real_dev']]['mp']
        else:
            for swap in self.swaps:
                if swap[0] == lv['real_dev']:
                    lv['mount'] = "SWAP"
        self.parse_attr(lv, lv['attr'])

    def __getitem__(self, name):
        if name in self.data:
            return self.data[name]
        if DM_DEV_DIR + "/" + name in self.data:
            return self.data[DM_DEV_DIR + "/" + name]
        device = name
        if not os.path.exists(name):
            device = DM_DEV_DIR + "/" + name
            if not os.path.exists(device):
                return None
        device = misc.get_real_device(device)
        if device in self.data:
            return self.data[device]
        return None

    def _data_index(self, row):
        return row['real_dev']

    def _get_dev_name(self, lv):
        real = misc.get_real_device(lv)
        if real in self.data:
            return self.data[real]['dev_name']
        else:
            return lv

    def remove(self, lv):
        vol = self[lv]
        if 'mount' in vol:
            if self.problem.check(self.problem.FS_MOUNTED,
                                  [vol['dev_name'], vol['mount']]):
                misc.do_umount(vol['mount'])
        lv = self._get_dev_name(lv)
        command = ['lvremove', lv]
        self.run_lvm(command)

    def resize(self, lv, size, resize_fs=True):
        lv = self._get_dev_name(lv)
        command = ['lvresize', '-L', str(size) + 'k', lv]
        vol = self[lv]
        if vol['active'] == False and \
           size < float(vol['vol_size']):
            self.problem.check(self.DEVICE_INACTIVE, lv)
        if resize_fs:
            command.insert(1, '-r')
        self.run_lvm(command)

    def snapshot(self, lv, destination, name, snap_size=None):
        vol = self[lv]
        vol_size = float(vol['vol_size'])
        lv = self._get_dev_name(lv)

        if not name:
            now = datetime.datetime.now()
            name = now.strftime("snap%Y%m%dT%H%M%S")

        if vol['type'] == "thin":
            if snap_size:
                self.problem.warn("Setting snapshot size for thin volume is" +
                                  " not supported")
                snap_size = None
        elif not snap_size:
            # We'll ceate snapshot of the size of 20% of the original volume
            snap_size = vol_size * 0.20

        if snap_size:
            command = ['lvcreate', '--size', str(snap_size) + 'K', '--snapshot',
                       '--name', name, lv]
        else:
            command = ['lvcreate', '--snapshot', '--name', name, lv]

        self.run_lvm(command)


class SnapInfo(LvmInfo):

    def __init__(self, *args, **kwargs):
        super(SnapInfo, self).__init__(*args, **kwargs)
        command = ["lvm", "lvs", "--separator", "|", "--noheadings",
                   "--nosuffix", "--units", "k", "-o",
                   "vg_name,lv_size,stripes,stripesize,segtype," +
                   "lv_name,origin,snap_percent,lv_attr,pool_lv"]
        self.attrs = ['pool_name', 'vol_size', 'stripes',
                      'stripesize', 'type', 'lv_name', 'origin',
                      'snap_size', 'attr', 'pool_lv']
        self.handle_fs = True
        self.mounts = misc.get_mounts('{0}/mapper'.format(DM_DEV_DIR))
        self._parse_data(command)

    def _skip_data(self, row):
        if not row['origin']:
            return True
        else:
            return False

    def _data_index(self, row):
        return misc.get_real_device(row['dev_name'])

    def _fill_additional_info(self, snap):
        snap['dev_name'] = "{0}/{1}/{2}".format(DM_DEV_DIR, snap['pool_name'],
                                                snap['lv_name'])
        snap['hide'] = False
        snap['snap_path'] = snap['dev_name']

        if snap['type'] != "thin":
            # It's possible that snap_percent in lvm output is not defined.
            # For example on inactive volume, so just remove it.
            if snap['snap_size']:
                size = float(snap['vol_size']) * float(snap['snap_size'])
                snap['snap_size'] = str(size / 100.00)
            else:
                del snap['snap_size']
        else:
            # Show thin-pool as a pool name in case of thin volumes
            snap['parent_pool'] = snap['pool_name']
            snap['pool_name'] = snap['pool_lv']

        snap['real_dev'] = misc.get_real_device(snap['dev_name'])

        sysfile = "/sys/block/{0}/dm/name".format(
                  os.path.basename(snap['real_dev']))

        # In some weird cases the "real" device might not be in /dev/dm-*
        # form (see tests). In this case constructed sysfile will not exist
        # so we just use real device name to search mounts.
        try:
            with open(sysfile, 'r') as f:
                lvname = f.readline()[:-1]
            snap['dm_name'] = "{0}/mapper/{1}".format(DM_DEV_DIR, lvname)
        except IOError:
            snap['dm_name'] = snap['real_dev']

        if snap['real_dev'] in self.mounts:
            snap['mount'] = self.mounts[snap['real_dev']]['mp']

        self.parse_attr(snap, snap['attr'])


class ThinPool(LvmInfo, template.BackendPool):

    def __init__(self, *args, **kwargs):
        super(ThinPool, self).__init__(*args, **kwargs)
        self.type = 'thin'
        command = ["lvm", "lvs", "--separator", "|", "--noheadings",
                   "--nosuffix", "--units", "k", "-o",
                   "vg_name,lv_size,stripes,stripesize,segtype,lv_name," +
                   "origin,lv_attr,pv_count,thin_count,data_percent," +
                   "metadata_percent,snap_percent"]
        self.attrs = ['parent_pool', 'vol_size', 'stripes',
                      'stripesize', 'type', 'lv_name', 'origin', 'attr',
                      'dev_count', 'vol_count', 'data_percent',
                      'metadata_percent', 'snap_percent']
        self._parse_data(command)
        # Uff, so ugly...needs to be changed
        global THIN_POOL_DATA
        THIN_POOL_DATA = self.data

    def _fill_additional_info(self, vg):
        vg['type'] = 'thin'
        vg['pool_name'] = os.path.basename(vg['lv_name'])
        vg['index_name'] = "{}/{}".format(vg['parent_pool'], vg['pool_name'])
        vg['pool_size'] = vg['vol_size']
        vg['pool_used'] = float(vg['vol_size']) * (float(vg['data_percent'])/100)
        vg['pool_free'] = float(vg['vol_size']) - vg['pool_used']
        if vg['attr'][4] == 'a':
            vg['active'] = True
        else:
            vg['active'] = False

    def __getitem__(self, key):
        # we can have <key> in self.data and then it is simple
        # but we can also have <parentpool>/<key> and then it gets complicated
        if key in self.data:
            return self.data[key]

        found = None
        for (name,item) in self.data.items():
            subkey = name.split('/', 1)
            if subkey[1] == key:
                if not found:
                    found = item
                else:
                    raise Exception("Multiple items with name {} found".format(key))
        return found

    def _data_index(self, row):
        return row['index_name']

    def _skip_data(self, row):
        if row['attr'][0] not in ['t', 'T']:
            return True
        else:
            return False

    def _generate_lvname(self, lvname, vg):
        for i in range(1, MAX_LVS):
            name = "{0}{1:0>{align}}".format(lvname, i, align=len(str(MAX_LVS)))
            path = "{0}/{1}/{2}".format(DM_DEV_DIR, vg, name)
            if name in self.data:
                continue
            try:
                if stat.S_ISBLK(os.stat(path).st_mode):
                    continue
            except OSError:
                pass
            return name
        self.problem.error("Can not find proper lvname!")

    def reduce(self, vg, device):
        msg = "Removing devices from thin pool"
        self.problem.check(self.problem.NOT_SUPPORTED, msg)

    def new(self, vg, devices):
        msg = "Creating a new"
        self.problem.check(self.problem.NOT_SUPPORTED, msg)

    def extend(self, vg, devices):
        self.require_thin_support()
        # Add devices to the parent pool first
        vg = self[vg]
        pool = vg['parent_pool']
        if type(devices) is not list:
            devices = [devices]
        command = ['vgextend', pool]
        command.extend(devices)
        self.run_lvm(command)
        # Now resize the thin-pool volume
        lv = vg['parent_pool'] + '/' + vg['lv_name']
        command = ['lvresize', lv]
        command.extend(devices)
        if vg['active'] == False:
            self.problem.check(self.DEVICE_INACTIVE, lv)
        self.run_lvm(command)

    def remove(self, vg):
        vg = self[vg]
        lvname = vg['parent_pool'] + '/' + vg['lv_name']
        command = ['lvremove', lvname]
        self.run_lvm(command)

    def create(self, vg, size=None, name=None, devs=None,
               options=None):
        self.require_thin_support()
        vg = self[vg]
        if vg['active'] == False:
            lv = vg['parent_pool'] + '/' + vg['lv_name']
            self.problem.check(self.DEVICE_INACTIVE, lv)

        if name:
            lvname = name
        else:
            lvname = self._generate_lvname("tvol", vg['parent_pool'])

        pool_volume = vg['parent_pool'] + '/' + vg['lv_name']

        # Once can specify either --size or --virtual-size argument when
        # creating thin volume out of thin pool, but not both.
        if size and 'virtsize' in options:
            self.problem.error("Either '--size' or '--virtual-size' can be" +
                               " can be specified for new thin volume size" +
                               " but not both")

        virtsize = None
        # Size needs to be specified for the thin volume
        if 'virtsize' in options:
            virtsize = options['virtsize']
        elif size:
            virtsize = size
        else:
            self.problem.error("Size must be specified to create a volume " +
                               "from a thin pool")

        # Ignore options for non existing thin volumes somehow
        command = ['lvcreate', '-n', lvname, '-T', pool_volume,
                   '-V', str(virtsize) + 'K']
        self.run_lvm(command)
        return "{0}/{1}/{2}".format(DM_DEV_DIR, vg['parent_pool'], lvname)
