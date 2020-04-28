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

# Main testing script for the system storage manager


import os
import re
import sys
import time
import doctest
import unittest
import argparse
import distutils.spawn

os.environ['SSM_NONINTERACTIVE'] = "1"

from ssmlib import main
from ssmlib import misc
from ssmlib.backends import lvm, crypt, btrfs, multipath

import tests.unittests as tests_module
from tests.unittests import *


def prog_exists(program):
    """ Test if given program/path/file exists and can be executed.
        Will search in $PATH too.

    Parameters
    ----------
    program : str
        Absolute/relative path to search for.

    Returns
    -------
    bool
        True if the program exists and can be executed.
    """

    return bool(distutils.spawn.find_executable(program))


def check_system_dependencies():
    """ Verify if we have all dependencies in system installed and print any
        that is missing.
        This function will not test for python modules available, only binaries.

    Returns
    -------
    bool
        True if everything is ok, False if any dependency is missing.
    """

    binaries = [
        'blkid',
        'which',
        'mount',
        'wipefs',
        'dd',
        'tune2fs',
        'resize2fs',
        'mkfs.ext3',
        'mkfs.ext4',
        'mkfs.xfs',
        'mkfs.btrfs',
        'fsck.ext3',
        'fsck.ext4',
        'fsck.xfs',
        'fsck.btrfs',
        'xfs_db',
        'xfs_growfs',
        'xfs_repair',
        'lvm',
        'dmsetup',
        'cryptsetup',
        'multipath',
        'mkswap',
        'swapon',
        'swapoff',
        'udevadm'
    ]

    missing = []
    for prog in binaries:
        if not prog_exists(prog):
            missing.append(prog)

    if missing:
        print("Dependencies are missing; some tests will probably fail or won't run:")
        print('\n'.join(missing))
        return False
    return True


def run_bash_tests(names, want_logs=False):
    cur = os.getcwd()
    os.chdir('./tests/bashtests')
    command = ['ls', '-m']
    if os.access('.coverage', os.R_OK):
        os.remove('.coverage')

    failed = []
    passed = []
    count = 0
    misc.run('./set.sh', stdout=False)
    output = misc.run(command, stdout=False)[1]
    t0 = time.time()
    for script in output.split(","):
        script = script.strip()
        if not re.match("^\d\d\d-.*\.sh$", script):
            continue
        if names and script not in names and script[:3] not in names:
            continue
        count += 1
        sys.stdout.write("{0:<29}".format(script) + " ")
        sys.stdout.flush()
        bad_file = re.sub("\.sh$",".bad", script)
        if os.access(bad_file, os.R_OK):
            os.remove(bad_file)
        ret, out, err = misc.run(['./' + script], stdout=False, can_fail=True)
        if ret:
            print("\033[91m[FAILED]\033[0m")
            failed.append(script)
            with open(bad_file, 'w') as f:
                f.write(out)
        elif re.search("Traceback", out):
            # There should be no tracebacks in the output
            out += "\nWARNING: Traceback in the output!\n"
            print("\033[93m[WARNING]\033[0m")
            with open(bad_file, 'w') as f:
                f.write(out)
        else:
            print("\033[92m[PASSED]\033[0m")
            passed.append(script)

    if count == 0 and names:
        print("[+] No bash test matches the name(s)")
        return 0

    t1 = time.time() - t0

    if want_logs:
        print_logs(failed)

    print("Ran {0} tests in {1} seconds.".format(count, round(t1, 2)))
    print("{0} tests PASSED: {1}".format(len(passed), ", ".join(passed)))
    ret = 0
    if len(failed) > 0:
        print("{0} tests FAILED: {1}".format(len(failed), ", ".join(failed)))
        print("See files with \"bad\" extension for output")
        ret = 1
    # Show coverage report output if possible
    if misc.check_binary('coverage'):
        print("[+] Coverage")
        misc.run(['coverage', 'report'], stdout=True, can_fail=True)
    os.chdir(cur)
    return ret

def print_logs(tests):
    for test in tests:
        logfile = re.sub(r"\.sh$",".bad", test)
        print("-----------------------------------\n{}\n-----------------------------------".format(
            logfile
        ))
        try:
            with open(logfile, 'r') as f:
                print(f.read())
        except IOError:
            print("The file '{}' does not exist.".format(logfile))
    print("-----------------------------------")


def doc_tests():
    print("[+] Running doctests")
    doctest_flags = doctest.IGNORE_EXCEPTION_DETAIL | doctest.ELLIPSIS | \
                    doctest.REPORT_ONLY_FIRST_FAILURE
    result = doctest.testmod(main, exclude_empty=True, report=True,
            raise_on_error=False, optionflags=doctest_flags)
    result = doctest.testmod(lvm, exclude_empty=True, report=True,
            raise_on_error=False, optionflags=doctest_flags)
    result = doctest.testmod(crypt, exclude_empty=True, report=True,
            raise_on_error=False, optionflags=doctest_flags)
    result = doctest.testmod(btrfs, exclude_empty=True, report=True,
            raise_on_error=False, optionflags=doctest_flags)
    result = doctest.testmod(multipath, exclude_empty=True, report=True,
            raise_on_error=False, optionflags=doctest_flags)
    result = doctest.testmod(misc, exclude_empty=True, report=True,
            raise_on_error=False, optionflags=doctest_flags)

def unit_tests(names):
    print("[+] Running unittests")
    tests = unittest.TestSuite()
    test_loader = unittest.TestLoader()

    if names:
        for name in names:
            if name[-3:] == ".sh" or name.isdigit():
                # bash test, skip here
                continue

            # first try a full name
            try:
                tests = unittest.TestSuite([tests, test_loader.loadTestsFromName(
                    name)])
                continue
            except (ImportError, AttributeError):
                pass

            # then a name with the prefix omitted
            try:
                tests = unittest.TestSuite([tests, test_loader.loadTestsFromName(
                    "tests.unittests." + name)])
                continue
            except (ImportError, AttributeError):
                pass

            # ok, maybe even the file name was omitted, so we are down to class.method name
            tests_classes = [cname for cname in dir(tests_module) if cname[:5] == 'test_']
            found = False
            for c in tests_classes:
                try:
                    tests = unittest.TestSuite([tests, test_loader.loadTestsFromName(
                        "tests.unittests.{}.{}".format(c,name))])
                    found = True
                    break
                except (ImportError, AttributeError):
                    pass
            if found:
                continue

            # still nothing found... it might be a method only, but TODO that
            print("Warning: Test {} was not found.".format(name))

        if tests.countTestCases() == 0:
            print("[+] No unittest matches the name(s)")
            return
    else:
        tests_lvm = test_loader.loadTestsFromModule(test_lvm)
        tests_btrfs = test_loader.loadTestsFromModule(test_btrfs)
        tests_ssm = test_loader.loadTestsFromModule(test_ssm)
        tests_misc = test_loader.loadTestsFromModule(test_misc)
        tests_multipath = test_loader.loadTestsFromModule(test_multipath)
        tests = unittest.TestSuite([tests_lvm, tests_btrfs, tests_ssm, tests_misc, tests_multipath])

    test_runner = unittest.TextTestRunner(verbosity=2)
    return not test_runner.run(tests).wasSuccessful()


if __name__ == '__main__':
    result = 0
    parser = argparse.ArgumentParser(description="Run the test suite for SSM. "
            "If both --bash and --unit arguments are ommited, run both groups. "
            "If a test name is specified, only matching tests are run.")
    parser.add_argument('-b', '--bash', dest='bash', action='store_true',
                    help='run only bash tests')
    parser.add_argument('-u', '--unit', dest='unit', action='store_true',
                    help='run only unit tests')
    parser.add_argument('-l', '--logs', dest='want_logs', action='store_true',
                    help='if a bash test fails, print out it\'s log to stdout')
    parser.add_argument('tests', metavar='TEST', type=str, nargs='*',
                    help='Specific tests to be run. For bash tests, '
                         'that means either a full name (001-foo.sh), '
                         'or just the number. '
                         'For unit tests, it means something like '
                         'BtrfsFunctionCheck.test_btrfs_resize for a specific test, '
                         'BtrfsFunctionCheck for specific test suite '
                         'and test_btrfs for a whole file of tests.')

    args = parser.parse_args()

    check_system_dependencies()

    run_all = not args.unit and not args.bash
    if args.unit and args.bash:
        print("Do not use both --bash and --unit at once."
            "All tests are run when these options are omitted.")
        sys.exit(1)

    if args.unit or run_all:
        if not args.tests:
            doc_tests()
        result = unit_tests(args.tests)
        if result:
            # if a unittest failed, break out immediately and do not try bash tests
            sys.exit(result)


    if args.bash or run_all:
        if not os.geteuid() == 0:
            print("\nRoot privileges required to run more tests!\n")
            sys.exit(0)
        print("[+] Running bash tests")
        result = run_bash_tests(names=args.tests, want_logs=args.want_logs)
    sys.exit(result)
