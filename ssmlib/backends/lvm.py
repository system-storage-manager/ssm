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

# lvm module for System Storage Manager

import os
import stat
from ssmlib import misc

__all__ = ["PvsInfo", "VgsInfo", "LvsInfo"]

try:
    DM_DEV_DIR = os.environ['DM_DEV_DIR']
except KeyError:
    DM_DEV_DIR = "/dev"
MAX_LVS = 999


class LvmInfo(object):

    def __init__(self, data=None, force=False, verbose=False, yes=False):
        self.data = data or {}
        self.attrs = []
        self.output = None
        self.force = force
        self.verbose = verbose
        self.yes = yes
        self.binary = misc.check_binary('lvm')

    def run_lvm(self, command, noforce=False):
        if not self.binary:
            raise Exception("ERROR: Lvm is not installed on the system!")
        if self.force and not noforce:
            command.insert(1, "-f")
        if self.verbose:
            command.insert(1, "-v")
        command.insert(0, "lvm")
        misc.run(command, stdout=True)

    def __str__(self):
        return self.output

    def _data_index(self, row):
        return row.values()[len(row.values()) - 1]

    def _parse_data(self, command):
        if not self.binary:
            return
        self.output = misc.run(command, stderr=False)[1]
        for line in self.output.split("\n"):
            if not line:
                break
            array = line.split("|")
            row = dict([(self.attrs[index], array[index].lstrip())
                for index in range(len(array))])
            self._fill_aditional_info(row)
            self.data[self._data_index(row)] = row

    def _fill_aditional_info(self, row):
        pass

    def __iter__(self):
        for item in sorted(self.data.iterkeys()):
            yield item

    def __getitem__(self, key):
        if key in self.data.iterkeys():
            return self.data[key]


class VgsInfo(LvmInfo):

    def __init__(self, *args, **kwargs):
        super(VgsInfo, self).__init__(*args, **kwargs)
        command = ["lvm", "vgs", "--separator", "|", "--noheadings",
                "--nosuffix", "--units", "k", "-o",
                "vg_name,pv_count,vg_size,vg_free,lv_count"]
        self.attrs = ['pool_name', 'dev_count', 'pool_size', 'pool_free',
                'vol_count']

        self._parse_data(command)

    def _fill_aditional_info(self, vg):
        vg['type'] = 'lvm'
        vg['pool_used'] = float(vg['pool_size']) - float(vg['pool_free'])

    def _data_index(self, row):
        return row['pool_name']

    def _generate_lvname(self, vg):
        for i in range(1, MAX_LVS):
            name = "lvol{0:0>{align}}".format(i, align=len(str(MAX_LVS)))
            path = "{0}/{1}/{2}".format(DM_DEV_DIR, vg, name)
            try:
                if stat.S_ISBLK(os.stat(path).st_mode):
                    continue
            except OSError:
                pass
            return name
        raise Exception("ERROR: could not find proper lvname")

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
            stripes=None, stripesize=None):
        devices = devs or []
        command = ['lvcreate', vg]
        if size:
            command.extend(['-L', size + 'K'])
        else:
            if len(devices) > 0:
                size = "100%PVS"
            else:
                size = "100%FREE"
            command.extend(['-l', size])

        if name:
            lvname = name
        else:
            lvname = self._generate_lvname(vg)

        command.extend(['-n', lvname.rpartition("/")[-1]])
        if not stripes and stripesize and len(devices) > 0:
            stripes = str(len(devices))
        elif not stripes and stripesize:
            raise Exception("Stripesize defined, but stripes not!")
        if stripesize:
            command.extend(['-I', stripesize])
        if stripes:
            command.extend(['-i', stripes])
        command.extend(devices)
        self.run_lvm(command, noforce=True)
        return "{0}/{1}/{2}".format(DM_DEV_DIR, vg, lvname)


class PvsInfo(LvmInfo):

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

    def _fill_aditional_info(self, pv):
        pv['hide'] = False

    def remove(self, devices):
        if len(devices) == 0:
            return
        command = ['pvremove']
        command.extend(devices)
        self.run_lvm(command)


class LvsInfo(LvmInfo):

    def __init__(self, *args, **kwargs):
        super(LvsInfo, self).__init__(*args, **kwargs)
        command = ["lvm", "lvs", "--separator", "|", "--noheadings",
                "--nosuffix", "--units", "k", "-o",
                "vg_name,lv_size,stripes,stripesize,segtype,lv_path"]
        self.attrs = ['pool_name', 'vol_size', 'stripes',
                'stripesize', 'type', 'dev_name']
        self.handle_fs = True
        self.mounts = misc.get_mounts('^{0}/mapper'.format(DM_DEV_DIR))
        self._parse_data(command)

    def _fill_aditional_info(self, lv):
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

        if lv['dm_name'] in self.mounts:
            lv['mount'] = self.mounts[lv['dm_name']]

    def __getitem__(self, name):
        if name in self.data.iterkeys():
            return self.data[name]
        device = name
        if not os.path.exists(name):
            device = DM_DEV_DIR + "/" + name
            if not os.path.exists(device):
                return None
        device = misc.get_real_device(device)
        if device in self.data.iterkeys():
            return self.data[device]
        return None

    def _data_index(self, row):
        return row['real_dev']

    def remove(self, lv):
        command = ['lvremove', lv]
        self.run_lvm(command)

    def resize(self, lv, size, resize_fs=True):
        command = ['lvresize', '-L', str(size) + 'k', lv]
        if resize_fs:
            command.insert(1, '-r')
        self.run_lvm(command)
