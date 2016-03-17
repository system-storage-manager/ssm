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
TEST_MAX_SIZE=$(($DEV_COUNT*($DEV_SIZE-4)))
aux prepare_devs $DEV_COUNT $DEV_SIZE
aux prepare_mnts 4
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

TEST_FS=
which mkfs.ext2 && TEST_FS+="ext2 "
which mkfs.ext3 && TEST_FS+="ext3 "
which mkfs.ext4 && TEST_FS+="ext4 "
which mkfs.xfs  && TEST_FS+="xfs"

# Create with single device
ssm create $dev1
ssm create -p $pool1 $dev2
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
check lv_field $pool1/$lvol1 pv_count 1
ssm -f remove -a

# Create volume with all devices at once
ssm create $TEST_DEVS
not ssm create $TEST_DEVS
not ssm create $TEST_DEVS -p $pool1
not ssm create -s ${DEV_SIZE}M $TEST_DEVS
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count $DEV_COUNT
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL 960.00MB linear
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Specify backend
ssm -b lvm create $TEST_DEVS
not ssm create $TEST_DEVS
not ssm create $TEST_DEVS -p $pool1
not ssm create -s ${DEV_SIZE}M $TEST_DEVS
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count $DEV_COUNT
ssm -f remove $SSM_LVM_DEFAULT_POOL

export SSM_DEFAULT_BACKEND='btrfs'
ssm --backend lvm create $TEST_DEVS
not ssm create $TEST_DEVS
not ssm create $TEST_DEVS -p $pool1
not ssm create -s ${DEV_SIZE}M $TEST_DEVS
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count $DEV_COUNT
ssm -f remove $SSM_LVM_DEFAULT_POOL
export SSM_DEFAULT_BACKEND='lvm'

# Create the group first and then create volume using the whole group
ssm add $TEST_DEVS
ssm create
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count $DEV_COUNT
ssm -f remove $SSM_LVM_DEFAULT_POOL/$lvol1
ssm -f create -s ${DEV_SIZE}m
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size $DEV_SIZE.00m
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Create a logical volume of fixed size
size=$(($DEV_SIZE*6))
ssm create -s ${size}M $TEST_DEVS
not ssm create -s ${TEST_MAX_SIZE}M
size=$(align_size_up $size)
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 360.00MB 600.00MB 960.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL 600.00MB linear
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Create a logical volume specifying size as percentage
ssm add $TEST_DEVS
ssm create -s 50%
not ssm create -s 80%
size=$((TEST_MAX_SIZE/2))
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$((TEST_MAX_SIZE/4))
ssm create -s 50%free
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol2 lv_size ${size}.00m
ssm create -s 20%used
size=$((($TEST_MAX_SIZE-$size)/5))
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol3 lv_size ${size}.00m
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Create a logical volume specifying size and adding devices
ssm create -s 100% $dev1 $dev2 $dev3 $dev4 $dev5
size=$((5*($DEV_SIZE-4)))
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
ssm create -s 50%FREE $dev6 $dev7
size=$(($DEV_SIZE-4))
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol2 lv_size ${size}.00m
ssm create -s 20%USED $TEST_DEVS
size=$(((6*($DEV_SIZE-4))/5))
size=$(align_size_up $size)
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol3 lv_size ${size}.00m
ssm -f remove $SSM_LVM_DEFAULT_POOL

not ssm create -s 200% $dev1 $dev2 $dev3 $dev4 $dev5
ssm create -s 50% $TEST_DEVS
not ssm create -s 200%free
not ssm create -s 200%used
ssm -f remove $SSM_LVM_DEFAULT_POOL
ssm create -s 50% $dev1 $dev2 $dev3 $dev4 $dev5
not ssm create -s 500%free $dev6 $dev7
not ssm create -s 500%used $dev8 $dev9
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Create a striped logical volume
not ssm create -I 32 $TEST_DEVS
ssm create -r 0 -I 32 $TEST_DEVS
not ssm create -I 32 -s ${TEST_MAX_SIZE}M
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripesize 32.00k
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripes $DEV_COUNT
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL 960.00MB striped
ssm  -f remove $SSM_LVM_DEFAULT_POOL

# Create a default raid 0 logical volume
ssm create -r 0 $TEST_DEVS
not ssm create -r 0 -s ${TEST_MAX_SIZE}M
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripesize 64.00k
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripes $DEV_COUNT
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL 960.00MB striped
ssm  -f remove $SSM_LVM_DEFAULT_POOL

# Create a raid 1 logical volume
# Size of the volume must be specified for lvm raid1
not ssm create -r 1 $dev1 $dev2
size=$((DEV_SIZE/2))
size=$(align_size_up $size)
ssm create -s ${size}M -r 1 $dev1 $dev2
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 segtype raid1
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 2 none none 192.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL ${size}.00MB raid1

ssm add $TEST_DEVS
size=$((DEV_SIZE*2))
size=$(align_size_up $size)
ssm create -s ${size}M -r 1
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol2 $SSM_LVM_DEFAULT_POOL ${size}.00MB raid1
ssm  -f remove $SSM_LVM_DEFAULT_POOL

# Create a raid 10 logical volume
# Size of the volume must be specified for lvm raid10
not ssm create -r 10 $dev1 $dev2 $dev3 $dev4
# Minimum is 4 devices
not ssm create -s ${DEV_SIZE}M -r 10 $dev1 $dev2
# Number of device has to be even
not ssm create -s ${DEV_SIZE}M -r 10 $dev1 $dev2 $dev3 $dev4 $dev5
ssm remove $dev5
ssm create -s ${DEV_SIZE}M -r 10 $dev1 $dev2 $dev3 $dev4
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripes 4
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 segtype raid10
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 4 none none 384.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL 104.00MB raid1
size=56
# Stripes or device has to be specified
not ssm create -s ${size}M -r 10
ssm create -s ${size}M -r 10 --stripes 2
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol2 stripes 4
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol2 segtype raid10
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 4 none none 384.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol2 $SSM_LVM_DEFAULT_POOL ${size}.00MB raid10
ssm add $TEST_DEVS
size=60
ssm create -s ${size}M -r 10 --stripes 3
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol3 stripes 6
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol3 segtype raid10
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol3 $SSM_LVM_DEFAULT_POOL ${size}.00MB raid10
ssm  -f remove $SSM_LVM_DEFAULT_POOL
ssm add $TEST_DEVS
size=$((DEV_SIZE*2))
size=$(align_size_up $size)
ssm create -s ${size}M -r 10 $TEST_DEVS
ssm list
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripes 10
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 segtype raid10
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL ${size}.00MB raid10
ssm  -f remove $SSM_LVM_DEFAULT_POOL

# Create several volumes with different parameters
ssm  add $TEST_DEVS
not ssm create -I 8 -i $(($DEV_COUNT/2)) -s $(($DEV_SIZE*2))M
ssm create -r 0 -I 8 -i $(($DEV_COUNT/2)) -s $(($DEV_SIZE*2))M
not ssm create -i $(($DEV_COUNT)) -s $(($DEV_SIZE))M
ssm create -r 0 -i $(($DEV_COUNT)) -s $(($DEV_SIZE))M
not ssm create -r 0 -I 32 -s $(($DEV_SIZE*2))M
ssm create
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripesize 8.00k
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripes $(($DEV_COUNT/2))
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol2 stripes $DEV_COUNT
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol3 segtype linear
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
ssm_output=$(ssm list vol)
check list_table "$ssm_output" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL 200.00MB striped
check list_table "$ssm_output" $SSM_LVM_DEFAULT_POOL/$lvol2 $SSM_LVM_DEFAULT_POOL 120.00MB striped
check list_table "$ssm_output" $SSM_LVM_DEFAULT_POOL/$lvol3 $SSM_LVM_DEFAULT_POOL 640.00MB linear
ssm  -f remove $SSM_LVM_DEFAULT_POOL

# Create several volumes with different parameters from different groups
ssm add $dev1 $dev2 $dev3 -p $pool1
not ssm create $dev1 $dev2
ssm add $dev4 $dev5 $dev6 -p $pool2
not ssm create --stripesize 32 --stripes 3 --size $(($DEV_SIZE*2))M -p $pool2
ssm create -r 0 --stripesize 32 --stripes 3 --size $(($DEV_SIZE*2))M -p $pool2
ssm create -r 0 --stripesize 32 --stripes 3 --size $((DEV_SIZE/2))M -p $pool2
ssm create -r 0 $dev7 $dev8 $dev9 --stripesize 8
not ssm create -p $pool1 --stripes 3
ssm create -r 0 -p $pool1 --stripes 3
not ssm create -s ${DEV_SIZE}M -p $pool1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripesize 8.00k
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripes 3
check lv_field $pool1/$lvol1 stripes 3
check lv_field $pool2/$lvol1 stripesize 32.00k
check lv_field $pool2/$lvol1 stripes 3
check lv_field $pool2/$lvol2 stripesize 32.00k
check lv_field $pool2/$lvol2 stripes 3
ssm_output=$(ssm list pool)
check list_table "$ssm_output" $SSM_LVM_DEFAULT_POOL lvm 3 none none 288.00MB
check list_table "$ssm_output" $vg2 lvm 3 none none 288.00MB
check list_table "$ssm_output" $vg3 lvm 3 none none 288.00MB
ssm_output=$(ssm list vol)
check list_table "$ssm_output" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL 288.00MB striped
check list_table "$ssm_output" $vg2/$lvol1 $vg2 288.00MB striped
check list_table "$ssm_output" $vg3/$lvol1 $vg3 204.00MB striped
check list_table "$ssm_output" $vg3/$lvol2 $vg3 60.00MB striped
ssm  -f remove --all

# Create logical volumes with file system
for fs in $TEST_FS; do
	# check addition with different names and sizes from existent and nonexistent pool
	# pool already exists
	ssm add $dev1 $dev2 $dev3
	ssm create --fstype $fs -s ${DEV_SIZE}m -n $lvol1 $mnt1
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size $((DEV_SIZE)).00m
	check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol1 $mnt1
	check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3

	# pool doesn't exist
	ssm create --fstype $fs -s $((DEV_SIZE/2))m -n randvol $dev4
	ssm mount  $SSM_LVM_DEFAULT_POOL/randvol $mnt2
	size=`align_size_up $((DEV_SIZE/2))`
	check lv_field $SSM_LVM_DEFAULT_POOL/randvol lv_size $size.00m
	check mountpoint $SSM_LVM_DEFAULT_POOL-randvol $mnt2
	check vg_field $SSM_LVM_DEFAULT_POOL pv_count 4
	umount $mnt1 $mnt2
	ssm check $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL/randvol
	ssm -f remove $SSM_LVM_DEFAULT_POOL

	# When we want to get unsed device from other pull, should succeed
	ssm add -p $pool1 $dev1 $dev2 $dev3
	ssm -f create -p $pool2 --fstype $fs -s ${DEV_SIZE}m $dev1 $dev2 $mnt1 -n randvol
	check lv_field $pool2/randvol lv_size $((DEV_SIZE)).00m
	check mountpoint $pool2-randvol $mnt1
	umount $mnt1
	ssm check $pool2/randvol
	check vg_field $pool2 pv_count 2
	ssm -f remove $pool1
	ssm -f remove $pool2

	ssm create --fs=$fs --name $lvol3 -s $(($DEV_SIZE*6))M $TEST_DEVS
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol3 pv_count $DEV_COUNT
	ssm -f check ${SSM_LVM_DEFAULT_POOL}/$lvol3
	ssm check ${SSM_LVM_DEFAULT_POOL}/$lvol3
	check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
	check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol3 $SSM_LVM_DEFAULT_POOL $(($DEV_SIZE*6)).00MB $fs none none linear
	check list_table "$(ssm list fs)" $SSM_LVM_DEFAULT_POOL/$lvol3 $SSM_LVM_DEFAULT_POOL $(($DEV_SIZE*6)).00MB $fs none none linear
	ssm  -f remove $SSM_LVM_DEFAULT_POOL

	ssm create --fs=$fs -r 0 -I 32 -s $(($DEV_SIZE*6))M $TEST_DEVS
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count $DEV_COUNT
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripesize 32.00k
	ssm check ${SSM_LVM_DEFAULT_POOL}/$lvol1
	check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
	check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL $(($DEV_SIZE*6)).00MB $fs none none striped
	check list_table "$(ssm list fs)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL $(($DEV_SIZE*6)).00MB $fs none none striped
	ssm  -f remove $SSM_LVM_DEFAULT_POOL

	ssm add $TEST_DEVS
	ssm create --fs=$fs -r 0 -I 8 -i $((DEV_COUNT/5)) -s $(($DEV_SIZE*2))M
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripes $(($DEV_COUNT/5))
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 stripesize 8.00k
	ssm check ${SSM_LVM_DEFAULT_POOL}/$lvol1
	check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 10 none none 960.00MB
	check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL $(($DEV_SIZE*2)).00MB $fs none none striped
	check list_table "$(ssm list fs)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL $(($DEV_SIZE*2)).00MB $fs none none striped
	ssm  -f remove $SSM_LVM_DEFAULT_POOL
done

# Create volume without enough space in the pool
ssm create $dev1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
ssm add $dev2 $dev3
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
not ssm create -s $(($DEV_SIZE*3))M
not check lv_field $SSM_LVM_DEFAULT_POOL/$lvol2 lv_name $lvol2
# Force to adjust the size
ssm -f create -s $(($DEV_SIZE*3))M
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol2 lv_name $lvol2
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol2 $SSM_LVM_DEFAULT_POOL 192.00MB linear
ssm  -f remove --all


ssm create $dev1 $dev2
ssm -f remove $SSM_LVM_DEFAULT_POOL
# Create volume on device with existing file system
mkfs.ext3 $dev1
not ssm create $dev1
ssm create $dev1 $dev2
ssm  -f remove --all

# Create volume on device with existing file system with force
mkfs.ext3 $dev1
ssm -f create $dev1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
ssm -f remove $SSM_LVM_DEFAULT_POOL
mkfs.ext3 $dev1
ssm -f create $dev1 $dev2
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 2
ssm  -f remove --all

# Create volume with device already used in different pool
ssm add $dev1 $dev2
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 2
# Fail because $dev1 is already used
not ssm create -p $pool1 $dev1
not ssm create -p $pool1 $dev1 $dev2
# Succeed because we have enough space to create volume just with $dev2
ssm create -s $(($DEV_SIZE/2))M -p $pool1 $dev1 $dev3
check lv_field $pool1/$lvol1 pv_count 1
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 2
ssm  -f remove --all

# Create volume with device already used in different pool with force
ssm add $dev1 $dev2
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 2
ssm -f create -p $pool1 $dev1
check lv_field $pool1/$lvol1 pv_count 1
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 1
ssm  -f remove --all

ssm create --help

# Some cases which should fail
not ssm create
ssm add $TEST_DEVS
not ssm create -p $pool1
not ssm create -r 0 -I 16 -i 3 $dev1 $dev2
not ssm create -s-20M
not ssm create -s+20M
not ssm create --size 25.8.1991
not ssm create --size linux
ssm  -f remove --all
