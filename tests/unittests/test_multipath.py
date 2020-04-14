#!/usr/bin/env python
#
# (C)2012 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
# (C)2016 Red Hat, Inc., Jan Tulak <jtulak@redhat.com>
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

# Unittests for the system storage manager multipath backend


import unittest
from ssmlib import problem
from ssmlib import main
from ssmlib import misc
from ssmlib.backends import multipath
from tests.unittests.common import *
from os.path import basename
from ssmlib.backends.multipath import MultipathDevice
import sys
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

class MultipathFunctionCheck(MockSystemDataSource):


    """
    Create a multipah configuration.
    device - without /dev, e.g. "dm-10"
    mpath - without /dev/mapper, e.g. "mpatha"
    size - in bytes
    nodes - a list of nodes without /dev, e.g. ["sda","sdb"]
    """
    def createMP(self, device, mpath, size, nodes):
        for node in nodes:
            self._addDevice('/dev/'+node, size)
            self.dev_data['/dev/'+node]['mp_vol']= '/dev/mapper/'+mpath
        self._addDevice('/dev/'+device, size)
        self._addLink('/dev/'+device, '/dev/mapper/'+mpath)
        self._addVol(mpath, size, 1, 'mapper', ('/dev/'+n for n in nodes))
        self.vol_data['/dev/mapper/'+mpath]['type']='multipath'
        self.vol_data['/dev/mapper/'+mpath]['real_dev']='/dev/'+device
        self.dev_data['/dev/'+device]['major'] = misc.get_dmnumber('device-mapper')

    def setUp(self):
        super(MultipathFunctionCheck, self).setUp()
        self._options = main.Options()
        self._addPool('mapper', [])

        # some standard, non-mp devices
        self._addDevice('/dev/sdc', 2684354560)
        self._addDevice('/dev/sdc1', 2042177280, 1)
        self._addDevice('/dev/sdc2', 29826161, 2)
        self._addDevice('/dev/sdc3', 1042177280, 3)

        # two mp volumes
        self.createMP("dm-90", "mpatha", 11489037516, ["sda", "sdb"])
        self.createMP("dm-91", "mpathb", 11489037, ["sdd", "sde", "sdf"])


    def _mp_size(self, rawsize):
        size = rawsize / 1024


    def mock_run(self, cmd, *args, **kwargs):

        # Convert all parts of cmd into string
        for i, item in enumerate(cmd):
            if type(item) is not str:
                cmd[i] = str(item)

        self.run_data.append(" ".join(cmd))
        output = ""
        if cmd[:2] == ['multipath', '-ll']:
            mp_vol = None
            if len(cmd) > 2:
                mp_vol = cmd[2]
            counter=0
            for (vol, v_data) in self.vol_data.items():
                size_converted = misc.humanize_size(v_data['dev_size'])

                if size_converted[-1] == 'B':
                    size_converted = size_converted[:-1].replace(" ","")

                # if there was an optional argument (volume name),
                # let's continue if we are not in the correct volume
                mp_name = "mpath"+chr(ord('a')+counter)
                counter += 1
                if mp_vol != None and mp_vol != mp_name:
                    continue
                mp_id="XX360000000000000000e0000000"+chr(ord('a')+counter)
                output += "{name} ({id}) {dev} QEMU    ,QEMU HARDDISK \n".format(name=mp_name, id=mp_id, dev=basename(v_data['real_dev']))
                output += "size={0} features='0' hwhandler='0' wp=rw\n".format(size_converted)

                devs = []
                for (dev, d_data) in sorted(self.dev_data.items()):
                    if not 'mp_vol' in d_data or d_data['mp_vol'] != vol:
                        continue
                    devs.append(d_data)

                if len(devs):
                    for d_data in devs[:-1]:
                        output += "|-+- policy='service-time 0' prio=1 status=active\n"
                        # [5:] to drop the "/dev/" part from the path
                        output += "| `- 11:0:0:1 {0} 8:64 active ready running\n".format(d_data['dev_name'][5:])
                    # format the last item differently
                    d_data = devs[-1]
                    output += "`-+- policy='service-time 0' prio=1 status=enabled\n"
                    output += "  `- 11:0:0:1  {0} 8:64 active ready running\n".format(d_data['dev_name'][5:])
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output, None)

    def test_mp_get_real_device(self):
        mp = MultipathDevice(options=self._options)
        self.assertEqual(mp.get_real_device("mpatha"), "/dev/dm-90")
        self.assertEqual(mp.get_real_device("mpathb"), "/dev/dm-91")
        self.assertEqual(mp.get_real_device("dm-90"), "/dev/dm-90")
        self.assertEqual(mp.get_real_device("dm-91"), "/dev/dm-91")
        self.assertEqual(mp.get_real_device("/dev/foo"), "/dev/foo")

    def test_mp_get_volumes_list(self):
        mp = MultipathDevice(options=self._options)
        self.assertEqual(mp.get_mp_devices(), ["mpatha", "mpathb"])

    def test_mp_get_device_data(self):
        mp = MultipathDevice(options=self._options)

        self.assertEqual(
            mp.get_device_data("/dev/sda", "mpatha", 0),
            {'dev_name':'/dev/sda', 'hide':False, 'multipath_volname':'mpatha',
             'pool_name':'/dev/dm-90', 'mount':'MULTIPATH'})
        self.assertEqual(
            mp.get_device_data("/dev/mapper/mpatha", "mpatha", 0),
            {'dev_name':'/dev/mapper/mpatha', 'hide':False,
             'multipath_volname':'mpatha', 'pool_name':'/dev/dm-90',
             'mount':'MULTIPATH'})

    def test_mp_get_volume_data(self):
        mp = MultipathDevice(options=self._options)
        vdata = mp.get_volume_data("mpatha")
        self.assertEqual(vdata['dev_name'], '/dev/dm-90')
        self.assertEqual(vdata['nodes'], ['/dev/sda','/dev/sdb'])

    def test_mp_forbidden_ops(self):
        self.assertRaises(problem.SsmError, main.main, "ssm remove /dev/mapper/mpatha")
        self.assertRaises(problem.SsmError, main.main, "ssm remove /dev/dm-90")
        self.assertRaises(problem.SsmError, main.main, "ssm remove mpatha")

    def test_mp_mock_raw_data(self):
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        try:
            main.main("ssm list dev")
        finally:
            sys.stdout = self._stdout
        vol_entries = 0
        for line in self._stringio.getvalue().splitlines():
            if line[:6] in ['------', 'Device']:
                continue
            dev = line.split(" ")
            if dev[0] in ['/dev/dm-90', '/dev/dm-91']:
                vol_entries += 1
        self.assertEqual(vol_entries, 2, "List vol should show 2 entries for 2 multipath devices, but found {0}.".format(vol_entries))

        # There should be no output for pools
        sys.stdout = self._stringio = StringIO()
        try:
            main.main("ssm list pool")
        finally:
            sys.stdout = self._stdout
        self.assertEqual(self._stringio.getvalue(),
            "", "Multipath should show no pool, but has some.")

        # There should be no output for vols
        sys.stdout = self._stringio = StringIO()
        try:
            main.main("ssm list vol")
        finally:
            sys.stdout = self._stdout
        self.assertEqual(self._stringio.getvalue(),
            "", "Multipath should show no vols, but has some.")

        sys.stdout = self._stringio = StringIO()
        try:
            main.main("ssm list vol")
        finally:
            sys.stdout = self._stdout

    def test_mp_mount(self):
        self._mountVol('mpatha', self.vol_data['/dev/mapper/mpatha']['pool_name'],
            ['/dev/sda', '/dev/sdb'], '/mnt/test1')
        mp = MultipathDevice(options=self._options)
        self.assertEqual(mp['mpatha']['mount'], '/mnt/test1')
