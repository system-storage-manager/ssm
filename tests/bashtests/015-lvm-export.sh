#!/bin/bash
#
# (C)2017 Red Hat, Inc., Jan Tulak <jtulak@redhat.com>
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

export test_name='015-lvm-export'
export test_description='A test of a specific issue with lvm and vgexport'

. lib/test

DEV_COUNT=2
DEV_SIZE=128
TEST_MAX_SIZE=$(($DEV_COUNT*$DEV_SIZE))
aux prepare_devs $DEV_COUNT $DEV_SIZE
TEST_DEVS=$(cat DEVICES)
export LVOL_PREFIX="lvol"
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'


pool0=$vg1

# Prepare pools and volumes

vol1=volsf
vol2=volss
maxvolsz=$((DEV_SIZE-4))
size1=$maxvolsz
size2=$((DEV_SIZE/2))


ssm -f create -n $vol1 $dev1
ssm create -n $vol2 -p $pool0 -s ${size2}M $dev2
vgchange -an $pool0
vgexport $pool0

# this should pass, but lvm returns a non-zero code even when everything is ok
# so test if ssm knows what to do
ssm list

exit 0

