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

# Miscellaneous functions for use by System Storage Manager

import os
import re
import sys
import stat
import tempfile
import threading
import subprocess
from ssmlib import problem
from base64 import encode

# List of temporary mount points which should be cleaned up
# before exiting
TMP_MOUNTED = []

if sys.version < '3':
    def __str__(x):
        return str(x)
else:
    def __str__(x):
        return str(x, encoding='utf-8', errors='strict')


def get_unit_size(string):
    """
    Check the last character of the string for the unit and return the tuple
    of unit value, unit name, otherwise return zero. It check only the first
    character of the unit string.

    >>> get_unit_size("B")
    (1, 'B')
    >>> get_unit_size("k")
    (1024, 'k')
    >>> get_unit_size("KiB")
    (1024, 'KiB')
    >>> get_unit_size("KB")
    (1024, 'KB')
    >>> get_unit_size("10M")
    (1048576, 'M')
    >>> get_unit_size("-99.99g")
    (1073741824, 'g')
    >>> get_unit_size("-99.99GiB")
    (1073741824, 'GiB')
    >>> get_unit_size("+99.99G")
    (1073741824, 'G')
    >>> get_unit_size("+99.99gb")
    (1073741824, 'gb')
    >>> get_unit_size("99.99g")
    (1073741824, 'g')
    >>> get_unit_size("0.84T")
    (1099511627776, 'T')
    >>> get_unit_size("0.84TiB")
    (1099511627776, 'TiB')
    >>> get_unit_size("0p")
    (1125899906842624, 'p')
    >>> get_unit_size("99kit")
    (0, '')
    >>> get_unit_size("")
    (0, '')
    >>> get_unit_size("H")
    (0, '')
    """

    mult = 0
    units = {'B': 1, 'K': 2 ** 10, 'M': 2 ** 20, 'G': 2 ** 30, 'T': 2 ** 40,
             'P': 2 ** 50}
    unit = re.sub(r'^\+?-?\d+(\.\d*)?', '', string)
    if len(unit) > 0 and unit[0].upper() in units:
        mult = units[unit[0].upper()]
    all_units = ['B', 'K', 'M', 'G', 'T', 'P',
                 'KB', 'MB', 'GB', 'TB', 'PB',
                 'KIB', 'MIB', 'GIB', 'TIB', 'PIB']
    if unit.upper() in all_units:
        return mult, unit
    else:
        return 0, ""


def is_number(string):
    """
    Check is the string is number and return True or False.

    >>> is_number("3.14")
    True
    >>> is_number("+3.14")
    True
    >>> is_number("-3.14")
    True
    >>> is_number("314")
    True
    >>> is_number("3a14")
    False
    """
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_real_size(size):
    """
    Get the real number from the size argument. It converts the size with units
    into the size in kilobytes. Is no unit is specified it defaults to
    kilobytes.

    >>> get_real_size("3141")
    '3141'
    >>> get_real_size("3141B")
    '3.07'
    >>> get_real_size("3141K")
    '3141.00'
    >>> get_real_size("3141KB")
    '3141.00'
    >>> get_real_size("3141KiB")
    '3141.00'
    >>> get_real_size("3141k")
    '3141.00'
    >>> get_real_size("3141M")
    '3216384.00'
    >>> get_real_size("3141G")
    '3293577216.00'
    >>> get_real_size("3141T")
    '3372623069184.00'
    >>> get_real_size("3141P")
    '3453566022844416.00'
    >>> get_real_size("3.14")
    '3.14'
    >>> get_real_size("+3.14")
    '+3.14'
    >>> get_real_size("-3.14")
    '-3.14'
    >>> get_real_size("3.14k")
    '3.14'
    >>> get_real_size("+3.14K")
    '+3.14'
    >>> get_real_size("-3.14k")
    '-3.14'
    >>> get_real_size("3.14G")
    '3292528.64'
    >>> get_real_size("3.14GB")
    '3292528.64'
    >>> get_real_size("3.14GiB")
    '3292528.64'
    >>> get_real_size("+3.14g")
    '+3292528.64'
    >>> get_real_size("-3.14G")
    '-3292528.64'
    >>> get_real_size("G")
    Traceback (most recent call last):
    ...
    Exception: Not supported unit in the size 'G' argument.
    >>> get_real_size("3141H")
    Traceback (most recent call last):
    ...
    Exception: Not supported unit in the size '3141H' argument.
    """
    if is_number(size):
        return size
    else:
        # Always use kilobytes in ssm
        mult, unit = get_unit_size(size)
        mult /= float(1024)
        number = re.sub(unit + "$", '', size)
        if is_number(number):
            sign = '+' if size[0] == '+' else ''
            if mult:
                return '{0}{1:.2f}'.format(sign, float(number) * mult)
    raise Exception("Not supported unit in the " +
                    "size \'{0}\' argument.".format(size))


def get_slaves(devname):
    return ["/dev/{0}".format(fname) for fname in os.listdir("/sys/block/{0}/slaves".format(devname))]


def send_udev_event(device, event):
    major, minor = get_major_minor(device)
    with open('/sys/dev/block/{0}:{1}/uevent'.format(major, minor), "w") as f:
        f.write(event)


def get_device_by_uuid(uuid):
    path = "/dev/disk/by-uuid/{0}".format(uuid)
    return os.path.abspath(os.path.join(os.path.dirname(path),
                           os.readlink(path)))


def get_major_minor(device):
    real_dev = get_real_device(device)
    info = os.stat(real_dev)
    major = os.major(info.st_rdev)
    minor = os.minor(info.st_rdev)
    return major, minor


def get_file_size(path):
    """
    Get size of the file (even block device) by seeking to the end of the
    file and returning offset. The returning size is in kilobytes.
    """
    with open(path, 'r') as f:
        return os.lseek(f.fileno(), os.SEEK_SET, os.SEEK_END) / 1024


def check_binary(name):
    command = ['which', name]
    if run(command, can_fail=True)[0]:
        return False
    else:
        return True


def do_mount(device, directory, options=None):
    command = ['mount']
    if options:
        command.extend(['-o', options])
    command.extend([device, directory])
    run(command)


def do_umount(mpoint, all_targets=False):
    command = ['umount']
    if all_targets:
        command.append('--all-targets')
    try:
        run(command + [mpoint])
    except RuntimeError:
        command.append('-l')
        run(command + mpoint)


def temp_mount(device, options=None):
    tmp = tempfile.mkdtemp()
    do_mount(device, tmp, options)
    TMP_MOUNTED.append(tmp)
    return tmp


def temp_umount(mpoint=None):
    if not mpoint:
        mpoint = TMP_MOUNTED.pop()
    do_umount(mpoint)
    os.rmdir(mpoint)


def do_cleanup():
    while 1:
        try:
            temp_umount()
        except IndexError:
            break


def get_signature(device, types=None):
    command = ["blkid", "-o", "value", "-p", "-s", "TYPE"]
    if types is not None:
        command.extend(['-u', types])
    command.append(device)

    ret, output = run(command, can_fail=True, stderr=False)
    output = output.strip()

    if ret:
        return None
    else:
        return output


def get_fs_type(device):
    return get_signature(device, "filesystem")


def get_real_device(device):
    if os.path.islink(device):
        return os.path.abspath(os.path.join(os.path.dirname(device),
                               os.readlink(device)))
    else:
        return device


def get_swaps():
    swap = []
    with open('/proc/swaps', 'r') as f:
        for line in f.readlines()[1:]:
            swap.append(line.split())
    return swap


def get_partitions():
    partitions = []
    new_line = []
    output = run(["lsblk","-l","-b","-n","-p","-o","MAJ:MIN,SIZE,KNAME"], stdout=False)

    for line in output[1].splitlines():
        new_line = re.split('\s+|:',line.strip())
        if len(new_line) == 4:
            new_line[2] = int(new_line[2])/1024
            partitions.append(new_line)
        else:
            pass
    return partitions


def get_mountinfo(regex=".*"):
    mounts = {}
    reg = re.compile(regex)
    names = ['id', 'parent', 'major_minor', 'root', 'mp', 'options']
    with open('/proc/self/mountinfo', 'r') as f:
        for line in f:
            m = reg.search(line)
            if not m:
                continue
            array = line.split(None, 6)
            row = dict([(names[index], array[index])
                for index in min(range(len(array) - 1), range(len(names)))])
            array = line.rsplit(None, 3)
            row['fs'] = array[1]
            row['dev'] = array[2]
            row['sb_options'] = array[3]
            dev = get_real_device(row['dev'])
            if row['root'] != '/':
                dev = "{0}:{1}".format(dev, row['root'])
            mounts[dev] = row
    return mounts


def get_mounts_old(regex=".*"):
    mounts = {}
    reg = re.compile(regex)
    with open('/proc/mounts', 'r') as f:
        for line in f:
            m = reg.search(line)
            if m:
                l = line.split()[:2]
                dev = get_real_device(l[0])
                mounts[dev] = {'dev': l[0], 'mp': l[1]}
    return mounts


def get_mounts(regex=".*"):
    if os.path.exists("/proc/self/mountinfo"):
        return get_mountinfo(regex)
    else:
        return get_mounts_old(regex)


def get_dmnumber(name):
    reg = re.compile(" {0}$".format(name))
    dmnumber = None
    with open('/proc/devices', 'r') as f:
        for line in f:
            m = reg.search(line)
            if m:
                dmnumber = line.split()[0]
                break
    return dmnumber


def wipefs(devices, signatures):
    if type(devices) is not list:
        devices = [devices]
    if type(signatures) is not list:
        signatures = [signatures]
    command = ['wipefs', '-a', '-t', ','.join(signatures)] + devices
    # Avoid race with udev
    run(['udevadm', 'settle'], stderr=False, can_fail=True)
    run(command)


def humanize_size(arg):
    """
    Returns the number with power of two units "KiB, MiB, ...etc. Parameter arg
    should be string of non-zero length, or integer. IMPORTANT: The arg
    argument is expected to be in KiB.

    >>> humanize_size(314)
    '314.00 KB'
    >>> humanize_size("314")
    '314.00 KB'
    >>> humanize_size(314159)
    '306.80 MB'
    >>> humanize_size(314159265)
    '299.61 GB'
    >>> humanize_size(314159265358)
    '292.58 TB'
    >>> humanize_size(314159265358979)
    '285.73 PB'
    >>> humanize_size(314159265358979323)
    '279.03 EB'
    >>> humanize_size(314159265358979323846)
    '272.49 ZB'
    >>> humanize_size(314159265358979323846264)
    '266.10 YB'
    >>> humanize_size(314159265358979323846264338)
    '266103.25 YB'
    >>> humanize_size(-314159265)
    '-299.61 GB'
    >>> humanize_size("")
    ''
    >>> humanize_size("hello world")
    Traceback (most recent call last):
        ...
    ValueError: could not convert string to float: hello world
    """
    count = 0
    if type(arg) is str and len(arg) == 0:
        return ""
    size = float(arg)
    while abs(size) >= 1024 and count < 7:
        size /= 1024
        count += 1
    units = ["KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    try:
        unit = units[count]
    except IndexError:
        unit = "???"
    return ("{0:.2f} {1}").format(size, unit)


def run(cmd, show_cmd=False, stdout=False, stderr=True, can_fail=False,
        stdin_data=None, return_stdout=True):

    stdin = None
    if stdin_data is not None:
        stdin = subprocess.PIPE

    if stderr:
        stderr = subprocess.STDOUT
    else:
        stderr = subprocess.PIPE

    if stdout:
        stdout = None
    else:
        stdout = subprocess.PIPE

    # Convert all parts of cmd into string
    for i, item in enumerate(cmd):
        if type(item) is not str:
            cmd[i] = str(item)

    proc = subprocess.Popen(cmd, stdout=stdout,
                            stderr=stderr, stdin=stdin)

    if stdin_data is not None:

        class StdinThread(threading.Thread):

            def run(self):
                proc.stdin.write(stdin_data)
                proc.stdin.close()
        stdin_thread = StdinThread()
        stdin_thread.daemon = True
        stdin_thread.start()

    output, error = proc.communicate()

    if stdin_data is not None:
        stdin_thread.join()

    err_msg = "ERROR running command: \"{0}\"".format(" ".join(cmd))
    if proc.returncode != 0 and show_cmd:
        if output is not None:
            print(output)
        if error is not None:
            print(error)
        sys.stderr.write(err_msg + '\n')

    if proc.returncode != 0 and not can_fail:
        if output is not None:
            print(output)
        if error is not None:
            print(error)
        raise problem.CommandFailed(err_msg)

    if not return_stdout:
        output = None

    if output is not None:
        return (proc.returncode, __str__(output))
    else:
        return (proc.returncode, output)


def chain(*iterables):
    """
    Make an iterator that returns elements from the first iterable until
    it is exhausted, then proceeds to the next iterable, until all of the
    iterables are exhausted. Used for treating consecutive sequences as a
    single sequence. This code has been taken from itertools python module.

    chain('ABC', 'DEF') --> A B C D E F
    """
    for it in iterables:
        for element in it:
            yield element


def izip(*iterables):
    """
    Make an iterator that aggregates elements from each of the iterables.
    Like zip() except that it returns an iterator instead of a list. Used
    for lock-step iteration over several iterables at a time. This code has
    been taken from itertools python module.

    izip('ABCD', 'xy') --> Ax By
    """
    iterators = map(iter, iterables)
    while iterators:
        yield tuple(map(next, iterators))


def compress(data, selectors):
    """
    Make an iterator that filters elements from data returning only those
    that have a corresponding element in selectors that evaluates to True.
    Stops when either the data or selectors iterables has been exhausted.
    This code has been taken from itertools python module.

    compress('ABCDEF', [1,0,1,0,1,1]) --> A C E F
    """
    return (d for d, s in izip(data, selectors) if s)


def permutations(iterable, r=None):
    """
    Return successive r length permutations of elements in the iterable.
    This code has been taken from itertools python module.

    permutations('ABCD', 2) --> AB AC AD BA BC BD CA CB CD DA DB DC
    permutations(range(3)) --> 012 021 102 120 201 210
    """
    pool = tuple(iterable)
    n = len(pool)
    r = n if r is None else r
    if r > n:
        return
    indices = range(n)
    cycles = range(n, n - r, -1)
    yield tuple(pool[i] for i in indices[:r])
    while n:
        for i in reversed(range(r)):
            cycles[i] -= 1
            if cycles[i] == 0:
                indices[i:] = indices[i + 1:] + indices[i:i + 1]
                cycles[i] = n - i
            else:
                j = cycles[i]
                indices[i], indices[-j] = indices[-j], indices[i]
                yield tuple(pool[i] for i in indices[:r])
                break
        else:
            return


def terminal_size(default=(25, 80)):
    """
    Returns running terminal size. If size cannot be found out default size
    is returned.
    """
    def _ioctl_GWINSZ(fd):
        try:
            import fcntl
            import termios
            import struct
            cr = struct.unpack('hh',
                               fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
        except:
            return None
        return cr

    try:
        env = os.environ
        cr = (env['LINES'], env['COLUMNS'])
    except:
        cr = _ioctl_GWINSZ(0) or _ioctl_GWINSZ(1) or _ioctl_GWINSZ(2)
        if not cr:
            try:
                fd = os.open(os.ctermid(), os.O_RDONLY)
                cr = _ioctl_GWINSZ(fd)
                os.close(fd)
            except:
                pass
        if not cr:
            cr = default
    return int(cr[1]), int(cr[0])


def is_bdevice(path):
    """
    Check whether the path is block device. If it is return
    the path to the real block device, otherwise return False
    """
    path = get_real_device(path)
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return False
    if not stat.S_ISBLK(mode):
        return False
    return path


def get_device_size(device):
    info = os.stat(device)
    major, minor = divmod(info.st_rdev, 256)
    with open("/sys/dev/block/{0}:{1}/size".format(major, minor), 'r') as f:
        for line in f:
            size = int(line)/2
            return size
