#!/bin/bash
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

export test_name='003-remove'
test_description='Exercise ssm remove'

. lib/test

DEV_COUNT=10
DEV_SIZE=10
TEST_MAX_SIZE=$(($DEV_COUNT*$DEV_SIZE))
aux prepare_devs $DEV_COUNT $DEV_SIZE
TEST_DEVS=$(cat DEVICES)
export SSM_LVM_DEFAULT_POOL=$vg1
export LVOL_PREFIX="lvol"
lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002
lvol3=${LVOL_PREFIX}003

pool1=$vg2
pool2=$vg3
DEFAULT_VOLUME=${SSM_LVM_DEFAULT_POOL}/$lvol1

_FS=
which mkfs.ext2 && _FS="ext2"
which mkfs.ext3 && _FS="ext3"
which mkfs.ext4 && _FS="ext4"
which mkfs.xfs  && _FS="xfs"


TEST_MNT=$TESTDIR/mnt

# Remove logical volume
ssm create $TEST_DEVS
check lv_field $DEFAULT_VOLUME lv_name $lvol1
ssm -f remove $DEFAULT_VOLUME
not check lv_field $DEFAULT_VOLUME lv_name $lvol1

# Remove volume group
ssm create $TEST_DEVS
check vg_field $SSM_LVM_DEFAULT_POOL vg_name $SSM_LVM_DEFAULT_POOL
ssm -f remove $SSM_LVM_DEFAULT_POOL
not check vg_field $SSM_LVM_DEFAULT_POOL vg_name $SSM_LVM_DEFAULT_POOL


# Remove unused devices from the pool
ssm create $dev1 $dev2 $dev3
ssm add $TEST_DEVS
check vg_field $SSM_LVM_DEFAULT_POOL pv_count $DEV_COUNT
ssm -f remove $TEST_DEVS
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
ssm -f remove --all

# Remove multiple things
ssm add $dev1 $dev2 -p $pool1
ssm add $dev3 $dev4 --pool $pool2
ssm create -p $pool2
ssm create $dev5 $dev6
ssm create $dev7 $dev8
ssm add $dev9
check vg_field $pool1 pv_count 2
check vg_field $pool2 pv_count 2
check vg_field $pool2 lv_count 1
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 5
check vg_field $SSM_LVM_DEFAULT_POOL lv_count 2
check vg_field $pool1 vg_name $pool1
check lv_field ${pool2}/$lvol1 lv_name $lvol1
ssm -f remove $pool1 ${pool2}/$lvol1 $DEFAULT_VOLUME $dev9
not check vg_field $pool1 vg_name $pool1
not check lv_field ${pool2}/$lvol1 lv_name $lvol1
not check lv_field $DEFAULT_VOLUME lv_name $lvol1
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 4
ssm -f remove --all

# Remove all
ssm add $dev1 $dev2 -p $pool1
ssm add $dev3 $dev4 --pool $pool2
ssm create --pool $pool2
ssm create $dev5 $dev6
ssm create $dev7 $dev8
ssm add $dev9
check vg_field $pool1 pv_count 2
check vg_field $pool2 pv_count 2
check vg_field $pool2 lv_count 1
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 5
check vg_field $SSM_LVM_DEFAULT_POOL lv_count 2
check vg_field $pool1 vg_name $pool1
check vg_field $pool2 vg_name $pool2
check vg_field $SSM_LVM_DEFAULT_POOL vg_name $SSM_LVM_DEFAULT_POOL
ssm -f remove --all
not check vg_field $pool1 vg_name $pool1
not check vg_field $pool2 vg_name $pool2
not check vg_field $SSM_LVM_DEFAULT_POOL vg_name $SSM_LVM_DEFAULT_POOL

ssm remove --help

# Some cases which should fail
not ssm remove
