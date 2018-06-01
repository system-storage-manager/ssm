# (C)2013 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
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

# template module for System Storage Manager contains template classes
# to use when creating new backend

import os
from ssmlib import misc
from ssmlib import problem

__all__ = ["Backend", "BackendPool", "BackendVolume", "BackendDevice"]

try:
    SSM_TEMPLATE_DEFAULT_POOL = os.environ['SSM_TEMPLATE_DEFAULT_POOL']
except KeyError:
    SSM_TEMPLATE_DEFAULT_POOL = "template_pool"


class Backend(object):
    def __init__(self, options, data=None):
        self.type = 'template'
        self.data = data or {}
        self.options = options
        self.output = None
        self.default_pool_name = SSM_TEMPLATE_DEFAULT_POOL
        self.problem = problem.ProblemSet(options)

    def __str__(self):
        return repr(self.data)

    def __iter__(self):
        for item in sorted(self.data):
            yield item

    def __getitem__(self, key):
        if key in self.data:
            return self.data[key]


class BackendPool(Backend):
    def __init__(self, *args, **kwargs):
        super(BackendPool, self).__init__(*args, **kwargs)

    def reduce(self, pool, device):
        self.problem.check(self.problem.NOT_SUPPORTED,
                        ["Reducing pool", "{} backend".format(self.type)])

    def new(self, pool, devices):
        self.problem.check(self.problem.NOT_SUPPORTED,
                        ["Creating new pool", "{} backend".format(self.type)])

    def extend(self, pool, devices):
        self.problem.check(self.problem.NOT_SUPPORTED,
                        ["Extending pool", "{} backend".format(self.type)])

    def remove(self, pool):
        self.problem.check(self.problem.NOT_SUPPORTED,
                        ["Removing pool", "{} backend".format(self.type)])

    def create(self, pool, size=None, name=None, devs=None,
               options=None):
        self.problem.check(self.problem.NOT_IMPLEMENTED,
                        ["Creating volume", "{} backend".format(self.type)])


class BackendVolume(Backend):
    def __init__(self, *args, **kwargs):
        super(BackendVolume, self).__init__(*args, **kwargs)

    def remove(self, volume):
        self.problem.check(self.problem.NOT_SUPPORTED,
                        ["Removing volume", "{} backend".format(self.type)])

    def resize(self, volume, size, resize_fs=True):
        self.problem.check(self.problem.NOT_SUPPORTED,
                        ["Resizing volume", "{} backend".format(self.type)])


class BackendDevice(Backend):
    def __init__(self, *args, **kwargs):
        super(BackendDevice, self).__init__(*args, **kwargs)

    def remove(self, devices):
        self.problem.check(self.problem.NOT_SUPPORTED,
                        ["Removing device", "{} backend".format(self.type)])
