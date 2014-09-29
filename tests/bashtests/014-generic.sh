#!/bin/bash
#
# (C)2014 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
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

export test_name='014-generic'
export test_description='Various simple test cases'

. lib/test

export COLUMNS=1024
DEV_COUNT=10
aux prepare_devs $DEV_COUNT 10
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'

# e5057e5be14226fd65f8f43bbc08f989b3bf2c58 Fix traceback when calling 'ssm list' with empty dm tables
ssm list
dmsetup create $vg2 --notable
ssm list
dmsetup remove $vg2
