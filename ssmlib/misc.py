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

from __future__ import print_function

import os
import re
import sys
import stat
import tempfile
import threading
import subprocess
from ssmlib import problem
from base64 import encode
from typing import List, Set

if sys.version < '3':
    def __next__(iter):
        return iter.next()
else:
    def __next__(iter):
        return next(iter)

# List of temporary mount points which should be cleaned up
# before exiting
TMP_MOUNTED = []

# A debug flag, because we can't reach to main.py from here
VERBOSE_VV_FLAG = False
VERBOSE_VVV_FLAG = False

if sys.version < '3':
    def __str__(x):
        if x is not None:
            return str(x)
else:
    def __str__(x):
        if x is not None:
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
    if unit and unit[0].upper() in units:
        mult = units[unit[0].upper()]
    all_units = ['B', 'K', 'M', 'G', 'T', 'P',
                 'KB', 'MB', 'GB', 'TB', 'PB',
                 'KIB', 'MIB', 'GIB', 'TIB', 'PIB']
    if unit.upper() in all_units:
        return mult, unit
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

def get_perc_size_argument(string):
    """
    Get percentage size argument. We now accept size argument in percentages
    of - free pool/volume space (FREE)
       - used pool/volume space (USED)
       - total pool/original volume size
    The accepted format is INTEGER%STRING where STRING needs to be one of
    the following (FREE, USED, or empty)
    """
    p = re.compile(r'%')
    perc, word = p.split(string, 1)

    if is_number(perc) and word.upper() in ['FREE', 'USED', '']:
        return (perc, word.upper())
    else:
        raise Exception("Not supported unit in the " +
                        "size \'{0}\' argument.".format(string))

def get_slaves(devname):
    return ["/dev/{0}".format(fname) for fname in os.listdir("/sys/block/{0}/slaves".format(devname))]


def send_udev_event(device, event):
    major, minor = get_major_minor(device)
    with open('/sys/dev/block/{0}:{1}/uevent'.format(major, minor), "w") as f:
        f.write(event)


def udev_settle():
    run(['udevadm', 'settle'], stderr=False, can_fail=True)


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
        return os.lseek(f.fileno(), os.SEEK_SET, os.SEEK_END) // 1024


def check_binary(name):
    command = ['which', name]
    if run(command, can_fail=True)[0]:
        return False
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

    ret, output, err = run(command, can_fail=True, stderr=False)
    output = output.strip()

    if ret:
        return None
    return output


def get_fs_type(device):
    return get_signature(device, "filesystem")


def get_real_device(device):
    if os.path.islink(device):
        return os.path.abspath(os.path.join(os.path.dirname(device),
                                            os.readlink(device)))
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
    output = run(["lsblk", "-l", "-b", "-n", "-p", "-o", "MAJ:MIN,SIZE,KNAME,NAME,PKNAME"],
                 stdout=False)

    for line in output[1].splitlines():
        new_line = re.split(r'\s+|:', line.strip())
        # Not every line has the parent device name, but in either case,
        # if we got data, convert the size to kB
        if len(new_line) in [5, 6]:
            new_line[2] = int(new_line[2])//1024
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
                        for index in min(
                            list(range(len(array) - 1)),
                            list(range(len(names)))
                        )])
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

def udev_checkpoint(devices):
    if not isinstance(devices, list):
        devices = [devices]
    for dev in devices:
        send_udev_event(dev, "change")
    udev_settle()

def wipefs(devices, signatures):
    if not isinstance(devices, list):
        devices = [devices]
    if not isinstance(signatures, list):
        signatures = [signatures]
    command = ['wipefs', '-a', '-t', ','.join(signatures)] + devices
    # Avoid race with udev
    udev_settle()
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
    if isinstance(arg, str) and not arg:
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
        if not isinstance(item, str):
            cmd[i] = str(item)

    if VERBOSE_VV_FLAG:
        print('executing command: {}'.format(' '.join(cmd)))

    proc = subprocess.Popen(cmd, stdout=stdout,
                            stderr=stderr, stdin=stdin, close_fds=True)

    output, error = proc.communicate(input=stdin_data)

    err_msg = "ERROR exit code {0} for running command: \"{1}\"".format(
              proc.returncode, " ".join(cmd))

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
        raise problem.CommandFailed(err_msg, exitcode=proc.returncode)

    if VERBOSE_VVV_FLAG:
        msg = "Exit: {}".format(proc.returncode)
        if error:
            msg += ", Error: {}".format(error)
        if output:
            msg += "\nOutput: {}".format(output)

        print(msg)

    if not return_stdout:
        output = None

    return (proc.returncode, __str__(output), __str__(error))


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


if sys.version < '3':
    def izip(*iterables):
        """
        Make an iterator that aggregates elements from each of the iterables.
        Like zip() except that it returns an iterator instead of a list. Used
        for lock-step iteration over several iterables at a time. This code has
        been taken from itertools python module (Python 2).

        izip('ABCD', 'xy') --> Ax By
        """
        iterators = map(iter, iterables)
        while iterators:
            yield tuple(map(next, iterators))
else:
    def izip(*iterables):
        """
        Make an iterator that aggregates elements from each of the iterables.
        Like zip() except that it returns an iterator instead of a list. Used
        for lock-step iteration over several iterables at a time. This code has
        been taken from itertools python module (Python 3).

        izip('ABCD', 'xy') --> Ax By
        """
        sentinel = object()
        iterators = [iter(it) for it in iterables]
        while iterators:
            result = []
            for it in iterators:
                elem = next(it, sentinel)
                if elem is sentinel:
                    return
                result.append(elem)
            yield tuple(result)


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
    indices = list(range(n))
    cycles = list(range(n, n - r, -1))
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
    except KeyError:
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
            size = int(line)//2
            return size

def ptable(data, table_header=None):
    """
    Print data in a table, optionally with a header.
    The data has to be a list of tuples of strings [('a', 'b', 'c'), ...]
    The header is a tuple: (('name', type), ... ), where the type is used to decide alignment.
    Int and float aligns to right, anything else to left.
    All the tuples has to have the same number of members.
    """
    if len(data) == 0:
        return

    header = []
    types = []
    fmt = ""
    skip_header = True
    # Keep track of used columns. Then we only print out columns with values.
    columns = [False] * len(data[0])

    len_matrix = []
    if table_header:
        skip_header = False
        line = []
        for n, t in table_header:
            if not isinstance(n, str) or not isinstance(t, type):
                raise ValueError("The header for ptable has to be a tuple/list in the format: " +
                                 "[('name', type), ...], but got [..., ({}, {}), ...]".format(n, t))
            line.append(len(n))
            header.append(n)
            types.append(t)
        # add header lengths into the matrix
        len_matrix.append(line)
    else:
        header = [''] * len(data[0])
        types = [str] * len(data[0])

    for _ in data:
        len_matrix.append([0 for _ in data[0]])

    index = 0
    # Gather all lines which are going to be printed into the list
    # and create matrix of attribute lengths.
    # Iterate through all items.
    for itemsline in data:
        # a line
        for i, item in enumerate(itemsline):
            len_matrix[index][i] = len(item)
            if len(item) > 0:
                columns[i] = True
        index += 1


    if header:
        alignment = [(len(item)) for item in header]
    else:
        alignment = [0]*len(data[0])
        types = [str]*len(data[0])
    term_width = terminal_size()[0]

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
    width = sum(compress(alignment, columns)) + 2 * len(header) - 2

    pos = 0
    # Use column alignments list to construct formatting string for each
    # line in the table. Note that some lines might be wrapped later on.
    for i, t in enumerate(types):
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


    if not skip_header:
        print("-" * width)
        print(fmt.format(*tuple(header)))
    print("-" * width)
    # Now print each line of the table. When the first attribute of the
    # line is longer than it should be we know that we have to wrap the
    # line.
    for i, line in enumerate(data):
        line = compress(line, columns)
        tmp1 = __next__(line)
        if len(tmp1) > alignment[0]:
            print(tmp1)
            print(fmt.format('', *line))
        else:
            print(fmt.format(tmp1, *line))
    print("-" * width)


class Node(object):
    """ A simple graph node class """

    def __init__(self):
        self._neighbours = []
        self._parents = []
        self._children = []

    @property
    def neighbours(self):
        return self._neighbours

    @property
    def parents(self):
        return self._parents

    @property
    def children(self):
        return self._children

    def add_neighbour(self, node):
        """ A two-way method. It will add self into the other node as well. """
        if not isinstance(node, Node):
            raise ValueError("Only other Nodes can be added as a neighbour.")
        if not node in self._neighbours:
            self._neighbours.append(node)
            node.add_neighbour(self)

    def add_children(self, node):
        """ A two-way method. It will add self into the other node as well. """
        if not node in self._children:
            self.add_neighbour(node)
            self._children.append(node)
            node.add_parent(self)

    def add_parent(self, node):
        """ A two-way method. It will add self into the other node as well. """
        if not node in self._parents:
            self.add_neighbour(node)
            self._parents.append(node)
            node.add_children(self)

    def get_roots(self):
        """ Find all root nodes by recursively traversing up all the parents. """
        roots = set()
        for parent in self.parents:
            roots |= parent.get_roots()

        if not roots:
            return {self}
        return roots

    @staticmethod
    def find_node(name, node_cls):
        """ Search item of class node_cls and try to find one
            with specific name.
        """
        if node_cls is Pool:
            for item in pools:
                if item['pool_name'] == name:
                    return item

        elif node_cls is Volumes:
            for item in volumes:
                if item['dev_name'] == name:
                    return item

        elif node_cls is Devices:
            for item in devices:
                if item['dev_name'] == name:
                    return item

        elif node_cls is Snapshots:
            for item in snapshots:
                if item['dev_name'] == name:
                    return item
        return None

class Blacklist(object):
    __instance = None
    def __new__(cls, *args, **kwargs):
        if Blacklist.__instance is None:
            Blacklist.__instance = _Blacklist(*args, **kwargs)
        return Blacklist.__instance

    def __getattr__(self, name):
        return getattr(self.__instance, name)

    def __setattr__(self, name, value):
        return setattr(self.__instance, name, value)

class _Blacklist(object):
    """A blacklist of devices that have to be ignored by ssm at all cost.

       This class serves as a single point of truth. All input/output
       operations with a device have to check if the device is allowed.

    Raises
    ------
    problem.BlacklistedItem
        Raised by allowed_or_exception(item) when item is blacklisted.
    """



    def __init__(self, blacklisted: List[str], verbose: bool=False):
        self._blacklist = set(blacklisted)
        self._verbose = verbose

    def __str__(self):
        items = ["'{}'".format(item) for item in sorted(list(self._blacklist))]
        items_str = ', '.join(items)
        return "[{0}]".format(items_str)

    def __contains__(self, key: str):
        return not self.allowed(key)

    @property
    def verbose(self) -> bool:
        return self._verbose

    @verbose.setter
    def verbose(self, value: bool) -> None:
        self._verbose = value

    @property
    def enforced(self) -> bool:
        return bool(self._blacklist)

    def allowed(self, item: str) -> bool:
        """Check if given item is allowed, or is in the blacklist.

        Parameters
        ----------
        item : str
            Item to be tested. If it is a path, symlinks are resolved, but it
            can be any string.

        Returns
        -------
        bool
            Return True if the item is allowed, or False if the item
            is in the blacklist.
        """
        if not self.enforced:
            return True

        item = get_real_device(item)
        if item in self._blacklist:
            if self.verbose:
                print(f"Item {item} blacklisted.")
            return False
        return True

    def allowed_or_exception(self, item: str) -> bool:
        """Check if given item is allowed, or is in the blacklist.

        Parameters
        ----------
        item : str
            Item to be tested. If it is a path, symlinks are resolved, but it
            can be any string.

        Raises
        ------
        problem.BlacklistedItem
            Raised when the item is in the blacklist.

        Returns
        -------
        bool
            Always return True if the item is allowed or raise an exception
            if the item is blacklisted.
        """
        if not self.enforced:
            return True

        item = get_real_device(item)
        if item in self._blacklist:
            if self.verbose:
                print(f"Item {item} blacklisted.")
            raise problem.BlacklistedItem(item)
        return True
