# (C)2013 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
#                        Jan Tulak <jtulak@redhat.com>
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

# multipath backend for ssm

import os
import re
from ssmlib import misc
from ssmlib import problem

from ssmlib.backends import template

__all__ = ["MultipathDevice"]

MP="multipath"

try:
    DM_DEV_DIR = os.environ['DM_DEV_DIR']
except KeyError:
    DM_DEV_DIR = "/dev"

class Multipath(template.Backend):
    def __init__(self, options, data=None):
        self.type = 'multipath'
        self.data = data or {}
        self._dev = {}
        self.options = options
        self.output = None
        self.problem = problem.ProblemSet(options)
        self.swaps = misc.get_swaps()
        self.mounts = misc.get_mounts('{0}/mapper'.format(DM_DEV_DIR))

        for mp_dev in self.get_mp_devices():
            mpname = self.get_real_device(mp_dev)
            self._dev[mp_dev] = self.get_volume_data(mp_dev)
            for devname in self._dev[mp_dev]['nodes']:
                self._dev[devname] = self.get_device_data(devname, mpname, 0)

    def __str__(self):
        return "mp: %s" % repr(self.data)

    def get_real_device(self, devname):
        """ Get the device for multipath volume name.
            Do we have /dev/mapper/mpathX, or /dev/dm-X?
        """
        if len(devname) > 5 and devname[:5] == "mpath":
            return misc.get_real_device("/dev/mapper/"+devname)
        elif len(devname) > 3 and devname[:3] == "dm-":
            return misc.get_real_device("/dev/"+devname)
        # Or maybe raise an exception?
        return devname


    def get_device_data(self, devname, mpname, devsize):
        data = {}
        data['dev_name'] = devname
        data['hide'] = False
        if mpname:
            data['multipath_volname'] = mpname
            data['pool_name'] = self.get_real_device(mpname)
            data['mount'] = 'MULTIPATH'
        return data

    def get_mp_devices(self):
        """ Find all multipath devices (but not their nodes). """
        devices = []
        command = [MP, '-ll']
        try:
            output = misc.run(command, stderr=False, can_fail=True)[1].split("\n")
            pattern = re.compile(r"^([a-z0-9]+) \([^)]+\)")
        except (problem.CommandFailed, OSError):
            # probably multipath not installed
            output = []

        for line in output:
            match = pattern.match(line)
            if match:
                devices.append(match.group(1))
        return devices


    def get_volume_data(self, volname):
        data = {}
        data['dev_name'] = self.get_real_device(volname)
        data['hide'] = False
        command = [MP, '-ll', volname]
        try:
            output = misc.run(command, stderr=False)[1].split("\n")
        except OSError:
            # probably multipath not installed
            output = []

        if len(output) > 0:
            match = re.search(r"\(([^)]+)\)",output[0])
            data['wwid'] = match.group(1)
            data['dev_size'] = misc.get_device_size(data['dev_name'])
            data['nodes'] = []
            data['total_nodes'] = 0
            if data['dev_name'] in self.mounts:
                data['mount'] = self.mounts[data['dev_name']]['mp']
            else:
                for swap in self.swaps:
                    if swap[0] == data['dev_name']:
                        data['mount'] = "SWAP"
                        break
            for entry in zip(output[2::2],output[3::2]):
                """ Some string operations to remove the tree path symbols
                    from the output. """
                dev = list(filter(None,
                            entry[1][re.search(r"[a-zA-Z0-9]", entry[1])
                                     .start():].split(" ")
                        ))
                data['nodes'].append("/dev/"+self.get_real_device(dev[1]))
                data['total_nodes'] += 1
        return data


class MultipathDevice(Multipath, template.BackendDevice):
    def __init__(self, *args, **kwargs):
        super(MultipathDevice, self).__init__(*args, **kwargs)
        if self.data:
            self.data.update(self._dev)
        else:
            self.data = self._dev
