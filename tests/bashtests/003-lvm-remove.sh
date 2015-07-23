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
aux prepare_mnts 1
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export LVOL_PREFIX="lvol"
export SSM_NONINTERACTIVE='1'
lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002
lvol3=${LVOL_PREFIX}003

pool1=$vg2
pool2=$vg3
pool3=$vg4
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

# Remove inactive logical volume
ssm create $TEST_DEVS
check lv_field $DEFAULT_VOLUME lv_name $lvol1
lvchange -an $DEFAULT_VOLUME
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
not ssm remove $dev1 $dev2 $dev3
ssm -f remove $DEFAULT_VOLUME
ssm remove $dev1 $dev2 $dev3
not ssm remove $dev3
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

# Remove multiple devices
ssm add $dev1 $dev2 $dev3 -p $pool1
ssm add $dev4 $dev5 --pool $pool2
ssm add $dev6 -p $pool3
ssm remove $dev1 $dev2
check vg_field $pool1 pv_count 1
ssm add $dev1 $dev2 $dev3 -p $pool1
check vg_field $pool1 pv_count 3
ssm remove $dev1 $dev2 $dev4 $dev6
check vg_field $pool1 pv_count 1
check vg_field $pool2 pv_count 1
check vg_field $pool3 pv_count 1
ssm -f remove -a

# Remove multiple volumes
ssm create $dev1 $dev2
ssm add -p $pool1 $TEST_DEVS
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 2
check vg_field $pool1 pv_count 8
ssm create -s ${DEV_SIZE}M -p $pool1 -n $lvol1
ssm create -s ${DEV_SIZE}M -p $pool1 -n $lvol2
ssm create -s ${DEV_SIZE}M -p $pool1 -n $lvol3
check vg_field $pool1 lv_count 3
ssm -f remove $pool1/$lvol1 $pool1/$lvol2
check vg_field $pool1 lv_count 1
ssm create -s ${DEV_SIZE}M -p $pool1 -n $lvol1
ssm create -s ${DEV_SIZE}M -p $pool1 -n $lvol2
ssm -f remove $SSM_LVM_DEFAULT_POOL/$lvol1 $pool1/$lvol1 $pool1/$lvol2
check vg_field $SSM_LVM_DEFAULT_POOL lv_count 0
check vg_field $pool1 lv_count 1
ssm -f remove -a

# Remove multiple pools
ssm create $dev1 $dev2
ssm create -p $pool1 $dev3 $dev4
ssm add -p $pool2 $dev5 $dev6 $dev7
ssm -f remove $SSM_LVM_DEFAULT_POOL $pool1 $pool2
not check vg_field $SSM_LVM_DEFAULT_POOL vg_name $SSM_LVM_DEFAULT_POOL
not check vg_field $pool1 vg_name $pool1
not check vg_field $pool1 vg_name $pool1

# Remove mounted volumes
ssm create --fs ext4 $dev1 $dev2 $mnt1
# Check mounted fs
not ssm check $SSM_LVM_DEFAULT_POOL/$lvol1
# Force the removal
ssm -f remove $SSM_LVM_DEFAULT_POOL/$lvol1
not check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_name $lvol1
ssm create --fs ext4 $dev1 $dev2 $mnt1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 2
ssm list
not ssm -f remove $SSM_LVM_DEFAULT_POOL
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_name $lvol1
umount $mnt1
ssm check $SSM_LVM_DEFAULT_POOL/$lvol1
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
not ssm -f remove --all
not check vg_field $pool1 vg_name $pool1
not check vg_field $pool2 vg_name $pool2
not check vg_field $SSM_LVM_DEFAULT_POOL vg_name $SSM_LVM_DEFAULT_POOL

ssm remove --help

# Some cases which should fail
not ssm remove
not ssm remove non_exist
