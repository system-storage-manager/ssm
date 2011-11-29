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

export test_name='002-create'
test_description='Exercise ssm create'

. lib/test

DEV_COUNT=10
DEV_SIZE=100
TEST_MAX_SIZE=$(($DEV_COUNT*$DEV_SIZE))
aux prepare_devs $DEV_COUNT $DEV_SIZE
TEST_DEVS=$(cat DEVICES)
export DEFAULT_DEVICE_POOL=$vg1
export LVOL_PREFIX="lvol"
lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002
lvol3=${LVOL_PREFIX}003

pool1=$vg2
pool2=$vg3

TEST_FS=
which mkfs.ext2 && TEST_FS+="ext2 "
which mkfs.ext3 && TEST_FS+="ext3 "
which mkfs.ext4 && TEST_FS+="ext4 "
which mkfs.xfs  && TEST_FS+="xfs"

# Create volume with all devices at once
ssm create $TEST_DEVS
not ssm create $TEST_DEVS
not ssm create $TEST_DEVS -p $pool1
not ssm create -s ${DEV_SIZE}M $TEST_DEVS
check lv_field $DEFAULT_DEVICE_POOL/$lvol1 pv_count $DEV_COUNT
ssm -f remove $DEFAULT_DEVICE_POOL

# Create the group first and then create volume using the whole group
ssm add $TEST_DEVS
ssm create
check lv_field $DEFAULT_DEVICE_POOL/$lvol1 pv_count $DEV_COUNT
ssm -f remove $DEFAULT_DEVICE_POOL

# Create a logical volume of fixed size
size=$(($DEV_SIZE*6))
ssm create -s ${size}M $TEST_DEVS
not ssm create -s ${TEST_MAX_SIZE}M
size=$(align_size_up $size)
check lv_field $DEFAULT_DEVICE_POOL/$lvol1 lv_size ${size}.00m
ssm -f remove $DEFAULT_DEVICE_POOL

# Create a striped logical volume
ssm create -I 32 $TEST_DEVS
not ssm create -I 32 -s ${TEST_MAX_SIZE}M
check lv_field $DEFAULT_DEVICE_POOL/$lvol1 stripesize 32.00k
ssm  -f remove $DEFAULT_DEVICE_POOL

# Create several volumes with different parameters
ssm  add $TEST_DEVS
ssm create -I 8 -i $(($DEV_COUNT/2)) -s $(($DEV_SIZE*2))M
ssm create -i $(($DEV_COUNT)) -s $(($DEV_SIZE))M
not ssm create -I 32 -s $(($DEV_SIZE*2))M
ssm create
check lv_field $DEFAULT_DEVICE_POOL/$lvol1 stripesize 8.00k
check lv_field $DEFAULT_DEVICE_POOL/$lvol1 stripes $(($DEV_COUNT/2))
check lv_field $DEFAULT_DEVICE_POOL/$lvol2 stripes $DEV_COUNT
check lv_field $DEFAULT_DEVICE_POOL/$lvol3 segtype linear
ssm  -f remove $DEFAULT_DEVICE_POOL

# Create several volumes with different parameters from different groups
ssm add $dev1 $dev2 $dev3 -p $pool1
not ssm create $dev1 $dev2
ssm add $dev4 $dev5 $dev6 -p $pool2
ssm create --stripesize 32 --stripes 3 --size $(($DEV_SIZE*2))M -p $pool2
ssm create --stripesize 32 --stripes 3 --size $((DEV_SIZE/2))M -p $pool2
ssm create $dev7 $dev8 $dev9 --stripesize 8
ssm create -p $pool1 --stripes 3
not ssm create -s ${DEV_SIZE}M -p $pool1
check lv_field $DEFAULT_DEVICE_POOL/$lvol1 stripesize 8.00k
check lv_field $DEFAULT_DEVICE_POOL/$lvol1 stripes 3
check lv_field $pool1/$lvol1 stripes 3
check lv_field $pool2/$lvol1 stripesize 32.00k
check lv_field $pool2/$lvol1 stripes 3
check lv_field $pool2/$lvol2 stripesize 32.00k
check lv_field $pool2/$lvol2 stripes 3
ssm  -f remove --all

# Create logical volumes with file system
for fs in $TEST_FS; do
	ssm create --fs=$fs --name $lvol3 -s $(($DEV_SIZE*6))M $TEST_DEVS
	check lv_field $DEFAULT_DEVICE_POOL/$lvol3 pv_count $DEV_COUNT
	ssm -f check ${DEFAULT_DEVICE_POOL}/$lvol3
	ssm check ${DEFAULT_DEVICE_POOL}/$lvol3
	ssm  -f remove $DEFAULT_DEVICE_POOL

	ssm create --fs=$fs -I 32 -s $(($DEV_SIZE*6))M $TEST_DEVS
	check lv_field $DEFAULT_DEVICE_POOL/$lvol1 pv_count $DEV_COUNT
	check lv_field $DEFAULT_DEVICE_POOL/$lvol1 stripesize 32.00k
	ssm check ${DEFAULT_DEVICE_POOL}/$lvol1
	ssm  -f remove $DEFAULT_DEVICE_POOL

	ssm add $TEST_DEVS
	ssm create --fs=$fs -I 8 -i $((DEV_COUNT/5)) -s $(($DEV_SIZE*2))M
	check lv_field $DEFAULT_DEVICE_POOL/$lvol1 stripes $(($DEV_COUNT/5))
	check lv_field $DEFAULT_DEVICE_POOL/$lvol1 stripesize 8.00k
	ssm check ${DEFAULT_DEVICE_POOL}/$lvol1
        ssm list
	ssm  -f remove $DEFAULT_DEVICE_POOL
done

ssm create --help

# Some cases which should fail
not ssm create
ssm add $TEST_DEVS
not ssm create -p $pool1
not ssm create -I 16 -i 3 $dev1 $dev2
ssm  -f remove --all
