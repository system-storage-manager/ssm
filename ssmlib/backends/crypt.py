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

# crypt module for System Storage Manager

import re
import os
import stat
import tempfile
from ssmlib import misc
from ssmlib import problem
from ssmlib.backends import template

__all__ = ["DmCryptVolume"]

SUPPORTED_CRYPT = ['luks', 'plain']
CRYPT_SIGNATURES = ['crypto_LUKS']
CRYPT_DEFAULT_EXTENSION = "luks"

try:
    SSM_CRYPT_DEFAULT_POOL = os.environ['SSM_CRYPT_DEFAULT_POOL']
except KeyError:
    SSM_CRYPT_DEFAULT_POOL = "crypt_pool"

try:
    SSM_CRYPT_DEFAULT_VOL_PREFIX = os.environ['SSM_CRYPT_DEFAULT_VOL_PREFIX']
except KeyError:
    SSM_CRYPT_DEFAULT_VOL_PREFIX = "encrypted"

# cryptsetup against my expectations does not take into account
# DM_DEV_DIR so set it to /dev pernamently for now.
#try:
#    DM_DEV_DIR = os.environ['DM_DEV_DIR']
#except KeyError:
#    DM_DEV_DIR = "/dev"
DM_DEV_DIR = "/dev"
MAX_DEVS = 999


def get_cryptsetup_version():
    try:
        output = misc.run(['cryptsetup', '--version'], can_fail=True)[1]
        version = list(map(int, output.strip().split()[-1].split('.', 3)))
    except (OSError, AttributeError):
        version = [0, 0, 0]
    return version

CRYPTSETUP_VERSION = get_cryptsetup_version()


class DmObject(template.Backend):
    def __init__(self, *args, **kwargs):
        super(DmObject, self).__init__(*args, **kwargs)
        self.type = 'crypt'
        self.mounts = misc.get_mounts('{0}/mapper'.format(DM_DEV_DIR))
        self.default_pool_name = SSM_CRYPT_DEFAULT_POOL

        if not misc.check_binary('dmsetup') or \
           not misc.check_binary('cryptsetup'):
            return

    def run_cryptsetup(self, command, stdout=True, password=None):
        if not misc.check_binary('cryptsetup'):
            self.problem.check(self.problem.TOOL_MISSING, 'cryptsetup')
        command.insert(0, "cryptsetup")
        if password != None:
            return misc.run(command, stdout=stdout, stdin_data=password)
        else:
            return misc.run(command, stdout=stdout)


class DmCryptPool(DmObject, template.BackendPool):
    def __init__(self, *args, **kwargs):
        super(DmCryptPool, self).__init__(*args, **kwargs)
        '''
        pool = {'pool_name': self.default_pool_name,
                'type': 'crypt',
                'dev_count': '0',
                'pool_free': '0',
                'pool_used': '0',
                'pool_size': '0',
                'hide': True}
        self.data[self.default_pool_name] = pool
        '''
        self.passphrase = None

    def set_passphrase(self, passphrase):
        self.passphrase = passphrase.encode()


    def check_passphrase_strength(self, passphrase):
        """ Verify is the password is in line with system-imposed requirements.
            This will create a temporary file and try encrypt it.
        """
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write( ('\0' * (10 * 1000 * 1000)).encode())  # 10 MB
            tmp.flush()
            command = ['-q', 'luksFormat', tmp.name]
            ret = 0
            try:
                if passphrase:
                    self.run_cryptsetup(command, password=passphrase.encode())
                else:
                    self.run_cryptsetup(command)
            except problem.CommandFailed as ex:
                if ex.exitcode == 2:
                    raise problem.GeneralError("Password quality check failed, see your system configuration for password requirements.")
                else:
                    raise ex

    def create(self, pool, size=None, name=None, devs=None,
               options=None):
        if CRYPTSETUP_VERSION < [1, 6, 0]:
            msg = "You need at least cryptsetup version " + \
                  "{0}. Creating encrypted volumes".format('1.6.0')
            self.problem.check(self.problem.NOT_SUPPORTED, msg)
        options = options or {}
        if 'encrypt' in options:
            if options['encrypt'] is True:
                options['encrypt'] = CRYPT_DEFAULT_EXTENSION
            if options['encrypt'] not in SUPPORTED_CRYPT:
                self.problem.not_supported("Extension "
                                           "\'{0}\'".format(options['encrypt']))
        else:
            # So the options is not crypt specific. It's ok, just use defaults
            options['encrypt'] = CRYPT_DEFAULT_EXTENSION

        if len(devs) > 1:
            self.problem.not_supported("Device concatenation" +
                                       " with \"crypt\" backend")
        if not name:
            name = self._generate_devname()
        device = devs[0]
        args = []
        command = []
        if self.options.verbose:
            args.append('-v')
        else:
            args.append('-q')
        if options['encrypt'] == "luks":
            command.extend(args)
            if self.options.force:
                command.append('--force-password')
            if self.options.interactive and not self.passphrase:
                command.append('-y')
            command.extend(['luksFormat', device])
            self.run_cryptsetup(command, password=self.passphrase)
        command = []
        command.extend(args)
        command.append('open')
        if size:
            # Size is in KiB but cryptsetup accepts it in 512 byte blocks
            size = str(float(size) * 2).split('.')[0]
            command.extend(['--size', size])
        command.extend(['--type', options['encrypt'], device, name])
        self.run_cryptsetup(command, password=self.passphrase)
        return "{0}/mapper/{1}".format(DM_DEV_DIR, name)

    def _generate_devname(self):
        for i in range(1, MAX_DEVS):
            name = "{0}{1:0>{align}}".format(SSM_CRYPT_DEFAULT_VOL_PREFIX, i,
                                            align=len(str(MAX_DEVS)))
            path = "{0}/mapper/{1}".format(DM_DEV_DIR, name)
            try:
                if stat.S_ISBLK(os.stat(path).st_mode):
                    continue
            except OSError:
                pass
            return name
        self.problem.error("Can not find proper device name. Specify one!")


class DmCryptVolume(DmObject, template.BackendVolume):

    def __init__(self, *args, **kwargs):
        super(DmCryptVolume, self).__init__(*args, **kwargs)

        command = ['dmsetup', 'table']
        self.output = misc.run(command, stderr=False)[1]
        for line in self.output.split("\n"):
            if not line or line == "No devices found":
                break
            dm = {}
            array = line.split()
            if len(array) == 1:
                continue
            dm['type'] = array[3]
            if dm['type'] != 'crypt':
                continue
            dm['vol_size'] = str(int(array[2]) / 2.0)
            devname = re.sub(":$", "",
                             "{0}/mapper/{1}".format(DM_DEV_DIR, array[0]))
            dm['dm_name'] = devname
            dm['pool_name'] = self.default_pool_name
            dm['dev_name'] = devname
            dm['real_dev'] = misc.get_real_device(devname)
            if dm['real_dev'] in self.mounts:
                dm['mount'] = self.mounts[dm['real_dev']]['mp']

            # Check if the device really exists in the system. In some cases
            # (tests) DM_DEV_DIR can lie to us, if that is the case, simple
            # ignore the device.
            if not os.path.exists(devname):
                continue
            command = ['cryptsetup', 'status', devname]
            self._parse_cryptsetup(command, dm)
            self.data[dm['dev_name']] = dm

    def _parse_cryptsetup(self, cmd, dm):
        self.output = misc.run(cmd, stderr=False)[1]
        for line in self.output.split("\n"):
            if not line:
                break
            array = line.split()
            if array[0].strip() == 'cipher:':
                dm['cipher'] = array[1]
            elif array[0].strip() == 'keysize:':
                dm['keysize'] = array[1]
            elif array[0].strip() == 'device:':
                dm['crypt_device'] = array[1]

    def __getitem__(self, name):
        if name in self.data:
            return self.data[name]
        device = name
        if not os.path.exists(name):
            device = DM_DEV_DIR + "/" + name
            if not os.path.exists(device):
                return None
        device = misc.get_real_device(device)
        if device in self.data:
            return self.data[device]
        return None

    def remove(self, dm):
        vol = self[dm]
        if 'mount' in vol:
            if self.problem.check(self.problem.FS_MOUNTED,
                                  [vol['dev_name'], vol['mount']]):
                misc.do_umount(vol['mount'])
        command = ['remove', dm]
        self.run_cryptsetup(command)
        misc.wipefs(vol['crypt_device'], CRYPT_SIGNATURES)


class DmCryptDevice(DmObject, template.BackendDevice):

    def __init__(self, *args, **kwargs):
        super(DmCryptDevice, self).__init__(*args, **kwargs)

        for line in misc.get_partitions():
            device = {}
            devname = line[3]
            signature = misc.get_signature(devname)
            if signature in CRYPT_SIGNATURES:
                device['hide'] = False
                device['dev_name'] = devname
                device['pool_name'] = self.default_pool_name
                device['dev_free'] = '0'
                device['dev_used'] = str(misc.get_device_size(devname))
                self.data[devname] = device

    def remove(self, devices):
        misc.wipefs(devices, CRYPT_SIGNATURES)
