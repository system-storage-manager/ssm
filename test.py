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

os.environ['SSM_NONINTERACTIVE'] = "1"

from ssmlib import main
from ssmlib import misc
from ssmlib.backends import lvm, crypt, btrfs

from tests.unittests import *

def run_bash_tests():
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
        count += 1
        sys.stdout.write("{0:<29}".format(script) + " ")
        sys.stdout.flush()
        bad_file = re.sub("\.sh$",".bad", script)
        if os.access(bad_file, os.R_OK):
            os.remove(bad_file)
        ret, out = misc.run(['./' + script], stdout=False, can_fail=True)
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
    t1 = time.time() - t0
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


def quick_test():
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
    result = doctest.testmod(misc, exclude_empty=True, report=True,
            raise_on_error=False, optionflags=doctest_flags)
    print("[+] Running unittests")
    test_loader = unittest.TestLoader()
    tests_lvm = test_loader.loadTestsFromModule(test_lvm)
    tests_btrfs = test_loader.loadTestsFromModule(test_btrfs)
    tests_ssm = test_loader.loadTestsFromModule(test_ssm)
    tests = unittest.TestSuite([tests_lvm, tests_btrfs, tests_ssm])
    test_runner = unittest.TextTestRunner(verbosity=2)
    test_runner.run(tests)


if __name__ == '__main__':
    quick_test()
    if not os.geteuid() == 0:
        print("\nRoot privileges required to run more tests!\n")
        sys.exit(0)
    print("[+] Running bash tests")
    result = run_bash_tests()
    sys.exit(result)
