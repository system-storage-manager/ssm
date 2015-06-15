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

# md module for System Storage Manager

import os
import socket
from ssmlib import misc
from ssmlib.backends import template

try:
    SSM_DM_DEFAULT_POOL = os.environ['SSM_DM_DEFAULT_POOL']
except KeyError:
    SSM_DM_DEFAULT_POOL = "md"

MDADM = "mdadm"


class MdRaid(template.Backend):

    def __init__(self, *args, **kwargs):
        super(MdRaid, self).__init__(*args, **kwargs)
        self.type = 'dm'
        self._vol = {}
        self._pool = {}
        self._dev = {}
        self.hostname = socket.gethostname()
        self._binary = misc.check_binary(MDADM)
        self.default_pool_name = SSM_DM_DEFAULT_POOL
        self.attrs = ['dev_name', 'pool_name', 'dev_free',
                      'dev_used', 'dev_size']

        if not self._binary:
            return

        self.mounts = misc.get_mounts('/dev/md')

        mdnumber = misc.get_dmnumber("md")

        for line in misc.get_partitions():
            devname = line[3]
            devsize = int(line[2])
            if line[0] == mdnumber:
                self._vol[devname] = self.get_volume_data(devname)
                for dev in misc.get_slaves(os.path.basename(devname)):
                    self._dev[dev] = self.get_device_data(dev, devsize)

    def get_device_data(self, devname, devsize):
        data = {}
        data['dev_name'] = devname
        data['hide'] = False
        command = [MDADM, '--examine', devname]
        output = misc.run(command, stderr=False)[1].split("\n")
        for line in output:
            array = line.split(":")
            if len(array) < 2:
                continue
            item = array[0].strip()
            if item == "Name":
                data['pool_name'] = SSM_DM_DEFAULT_POOL
            data['dev_used'] = data['dev_size'] = devsize
            data['dev_free'] = 0
        return data

    def get_volume_data(self, devname):
        data = {}
        data['dev_name'] = devname
        data['real_dev'] = devname
        data['pool_name'] = SSM_DM_DEFAULT_POOL
        if data['dev_name'] in self.mounts:
            data['mount'] = self.mounts[data['dev_name']]['mp']
        command = [MDADM, '--detail', devname]
        for line in misc.run(command, stderr=False)[1].split("\n"):
            array = line.split(":")
            if len(array) < 2:
                continue
            item = array[0].strip()
            value = array[1].strip()
            if item == 'Raid Level':
                data['type'] = value
            elif item == 'Array Size':
                data['vol_size'] = value.split()[0]
            elif item == 'Total Devices':
                data['total_devices'] = value

        return data

    def run_mdadm(self, command):
        if not self._binary:
            self.problem.check(self.problem.TOOL_MISSING, MDADM)
        command.insert(0, MDADM)
        return misc.run(command, stdout=True)


class MdRaidVolume(MdRaid, template.BackendVolume):

    def __init__(self, *args, **kwargs):
        super(MdRaidVolume, self).__init__(*args, **kwargs)
        if self.data:
            self.data.update(self._vol)
        else:
            self.data = self._vol

    def remove(self, vol):
        command = ['--stop', vol]
        self.run_mdadm(command)

    def resize(self, vol, size, resize_fs=True):
        self.problem.not_supported("Resizing with \"md\" backend")


class MdRaidDevice(MdRaid, template.BackendDevice):

    def __init__(self, *args, **kwargs):
        super(MdRaidDevice, self).__init__(*args, **kwargs)
        if self.data:
            self.data.update(self._dev)
        else:
            self.data = self._dev

    def remove(self, devices):
        self.problem.not_supported("Removing device from \"md\" backend")
