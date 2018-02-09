#!/usr/bin/env python
#
# (C)2018 Red Hat, Inc., Jan Tulak <jtulak@redhat.com>
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

# Unittests for the system storage manager

import os
import re
import sys
import stat
import time
import doctest
import unittest
import argparse
from ssmlib import main
from ssmlib import misc
from ssmlib import problem
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from tests.unittests.common import *

class MiscCheck(unittest.TestCase):
    """
    Checks for various helpers and tools.
    """
    def _get_ptable_output(self, data, header=None):
        stdout_orig = sys.stdout
        sys.stdout = stringio = StringIO()
        try:
            misc.ptable(data, header)
        finally:
            sys.stdout = stdout_orig
        return stringio.getvalue()

    def test_ptable_header_types(self):
        self.assertEqual(self._get_ptable_output([
                ('a1', 'b1', 'cde1'),
                ('a2--', 'b2', 'cde2'),
                ('a3', 'b3--', 'cde3---'),
                ('a4', 'b4', 'cde4'),],
            header=(('h1', str), ('h2', str), ('h3', str))),
            "-------------------\n" + \
            "h1    h2    h3     \n" + \
            "-------------------\n" + \
            "a1    b1    cde1   \n" + \
            "a2--  b2    cde2   \n" + \
            "a3    b3--  cde3---\n" + \
            "a4    b4    cde4   \n" + \
            "-------------------\n")

    def test_ptable_header_types_nums(self):
        self.assertEqual(self._get_ptable_output([
                ('a1', '1', '1.2'),
                ('a2--', '2', '42.3455'),
                ('a3', '300', '3.1459265'),
                ('a4', '4', '-10.22'),],
            header=(('h1', str), ('h2', int), ('h3', float))),
            "--------------------\n" + \
            "h1     h2         h3  \n" + \
            "--------------------\n" + \
            "a1      1        1.2  \n" + \
            "a2--    2    42.3455  \n" + \
            "a3    300  3.1459265  \n" + \
            "a4      4     -10.22  \n" + \
            "--------------------\n")

    def test_ptable_header_types_hide_column(self):
        self.assertEqual(self._get_ptable_output([
                ('a1', '1', ''),
                ('a2--', '2', ''),
                ('a3', '300', ''),
                ('a4', '4', ''),],
            header=(('h1', str), ('h2', int), ('h3', float))),
            "-----------\n" + \
            "h1     h2  \n" + \
            "-----------\n" + \
            "a1      1  \n" + \
            "a2--    2  \n" + \
            "a3    300  \n" + \
            "a4      4  \n" + \
            "-----------\n")
    def test_ptable_no_header_no_types(self):
        self.assertEqual(self._get_ptable_output([
                ('a1', 'b1', 'cde1'),
                ('a2--', 'b2', 'cde2'),
                ('a3', 'b3--', 'cde3---'),
                ('a4', 'b4', 'cde4'),
            ]),
            "-------------------\n" + \
            "a1    b1    cde1   \n" + \
            "a2--  b2    cde2   \n" + \
            "a3    b3--  cde3---\n" + \
            "a4    b4    cde4   \n" + \
            "-------------------\n")


class NodeCheck(unittest.TestCase):
    def setUp(self):
        self.root = misc.Node()
        self.nodes = nodes = [misc.Node() for _ in range(4)]
        #            root--->--0
        #           /          |
        #   2--<---1----->-----3
        self.root.add_children(nodes[0])
        self.root.add_children(nodes[1])
        nodes[0].add_children(nodes[3])
        nodes[1].add_children(nodes[3])
        nodes[1].add_children(nodes[2])

    def test_sanity(self):
        self.assertTrue(self.nodes[0] in self.root.neighbours())
        self.assertTrue(self.nodes[0] in self.root.children())
        self.assertFalse(self.nodes[0] in self.root.parents())

        self.assertTrue(self.nodes[3] in self.nodes[0].neighbours())
        self.assertTrue(self.root in self.nodes[0].neighbours())
        self.assertTrue(self.nodes[3] in self.nodes[0].children())
        self.assertTrue(self.root in self.nodes[0].parents())

        self.assertTrue(self.nodes[0] in self.nodes[3].neighbours())
        self.assertTrue(self.nodes[1] in self.nodes[3].neighbours())
        self.assertEqual(self.nodes[3].children(), [])
        self.assertTrue(self.nodes[0] in self.nodes[3].parents())
        self.assertTrue(self.nodes[1] in self.nodes[3].parents())

    def test_multiple_insertions(self):
        a = misc.Node()
        b = misc.Node()
        a.add_children(b)
        a.add_children(b)
        self.assertEqual(a.children(), [b])
        self.assertEqual(b.parents(), [a])
        self.assertEqual(b.neighbours(), [a])
        self.assertEqual(a.neighbours(), [b])
