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

export test_name='005-snapshot'
export test_description='Exercise ssm snapshot'

. lib/test

DEV_COUNT=10
DEV_SIZE=100
TEST_MAX_SIZE=$(($DEV_COUNT*$DEV_SIZE))
aux prepare_devs $DEV_COUNT $DEV_SIZE
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export LVOL_PREFIX="lvol"
export SSM_NONINTERACTIVE='1'
lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002
lvol3=${LVOL_PREFIX}003
snap1="snap1"
snap2="snap2"
snap3="snap3"

pool1=$vg2
pool2=$vg3

TEST_MNT=$TESTDIR/mnt
TEST_MNT2=$TESTDIR/mnt2

# Create volume with all devices at once
size=$(($DEV_SIZE*6))
ssm create --size ${size}M $TEST_DEVS

# Take a snapshot with the default params
export SSM_DEFAULT_BACKEND='btrfs'
ssm snapshot --name $snap1 $SSM_LVM_DEFAULT_POOL/$lvol1
check vg_field $SSM_LVM_DEFAULT_POOL lv_count 2
check list_table "$(ssm list snap)" $snap1 $lvol1 none none none linear
export SSM_DEFAULT_BACKEND='lvm'

# Remove entire pool
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Create volume with all devices at once
size=$(($DEV_SIZE*6))
ssm create --size ${size}M $TEST_DEVS

# Take a snapshot with defined name
snap_size=$(($size/5))
ssm snapshot --name $snap1 $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$snap1 lv_size ${snap_size}.00m
ssm snapshot --name $snap2 $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$snap2 lv_size ${snap_size}.00m
ssm snapshot --name $snap3 $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$snap3 lv_size ${snap_size}.00m
check vg_field $SSM_LVM_DEFAULT_POOL lv_count 4
ssm_output=$(ssm list snap)
check list_table "$ssm_output" $snap1 $lvol1 $SSM_LVM_DEFAULT_POOL ${snap_size}.00MB none linear
check list_table "$ssm_output" $snap2 $lvol1 $SSM_LVM_DEFAULT_POOL ${snap_size}.00MB none linear
check list_table "$ssm_output" $snap3 $lvol1 $SSM_LVM_DEFAULT_POOL ${snap_size}.00MB none linear

# Remove the snapshot volumes
ssm -f remove $SSM_LVM_DEFAULT_POOL/$snap1 $SSM_LVM_DEFAULT_POOL/$snap2 $SSM_LVM_DEFAULT_POOL/$snap3

# Take a snapshot with defined name and size
snap_size=$(($DEV_SIZE))
ssm snapshot --size ${snap_size}M --name $snap1 $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$snap1 lv_size ${snap_size}.00m
ssm snapshot --size ${snap_size}M --name $snap2 $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$snap2 lv_size ${snap_size}.00m
ssm snapshot --size ${snap_size}M --name $snap3 $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$snap3 lv_size ${snap_size}.00m
check vg_field $SSM_LVM_DEFAULT_POOL lv_count 4

ssm -f remove --all

# Create a logical volume with file system and mount it
[ ! -d $TEST_MNT ] && mkdir $TEST_MNT &> /dev/null
size=$(($DEV_SIZE*6))
ssm create --size ${size}M --fs ext4 $TEST_DEVS $TEST_MNT

# Take a snapshot with defined name of volume referenced by the mountpoint
snap_size=$(($size/5))
ssm snapshot --name $snap1 $TEST_MNT
check lv_field $SSM_LVM_DEFAULT_POOL/$snap1 lv_size ${snap_size}.00m
ssm snapshot --name $snap2 $TEST_MNT
check lv_field $SSM_LVM_DEFAULT_POOL/$snap2 lv_size ${snap_size}.00m
ssm snapshot --name $snap3 $TEST_MNT
check lv_field $SSM_LVM_DEFAULT_POOL/$snap3 lv_size ${snap_size}.00m
check vg_field $SSM_LVM_DEFAULT_POOL lv_count 4
# Mount snapshot
[ ! -d $TEST_MNT2 ] && mkdir $TEST_MNT2 &> /dev/null
ssm mount $SSM_LVM_DEFAULT_POOL/$snap3 $TEST_MNT2
ssm_output=$(ssm list snap)
check list_table "$ssm_output" $snap1 $lvol1 $SSM_LVM_DEFAULT_POOL ${snap_size}.00MB none linear
check list_table "$ssm_output" $snap2 $lvol1 $SSM_LVM_DEFAULT_POOL ${snap_size}.00MB none linear
check list_table "$ssm_output" $snap3 $lvol1 $SSM_LVM_DEFAULT_POOL ${snap_size}.00MB none linear $TEST_MNT2
check list_table "$(ssm list fs)" $lvol1 $SSM_LVM_DEFAULT_POOL ${size}.00MB ext4 ${size}.00MB none linear $TEST_MNT

# Remove the snapshot volumes
ssm -f remove $SSM_LVM_DEFAULT_POOL/$snap1 $SSM_LVM_DEFAULT_POOL/$snap2 $SSM_LVM_DEFAULT_POOL/$snap3

# Take a snapshot with defined name of volume referenced by the full volume name
snap_size=$(($DEV_SIZE))
ssm snapshot --size ${snap_size}M --name $snap1 $DM_DEV_DIR/$SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$snap1 lv_size ${snap_size}.00m
ssm snapshot --size ${snap_size}M --name $snap2 $DM_DEV_DIR/$SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$snap2 lv_size ${snap_size}.00m
ssm snapshot --size ${snap_size}M --name $snap3 $DM_DEV_DIR/$SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$snap3 lv_size ${snap_size}.00m
check vg_field $SSM_LVM_DEFAULT_POOL lv_count 4

umount $TEST_MNT
not umount $TEST_MNT2

ssm -f remove --all

# Snapshot of the volumes in defferent pools
ssm create --pool $pool1 $dev1 $dev2
ssm add $dev3 $dev4 --pool $pool1
ssm create --pool $pool2 $dev5 $dev6
ssm add $dev7 $dev8 --pool $pool2

ssm snapshot --name $snap1 $pool1/$lvol1
ssm snapshot --name $snap1 $pool2/$lvol1
check lv_field $pool1/$snap1 lv_name $snap1
check lv_field $pool2/$snap1 lv_name $snap1

ssm -f remove --all

ssm snapshot --help

# Some cases which should fail
not ssm snapshot
ssm create $TEST_DEVS
not ssm snapshot $SSM_LVM_DEFAULT_POOL/$lvol1
ssm -f resize -s $((DEV_SIZE*2)) $SSM_LVM_DEFAULT_POOL/$lvol1
not ssm snapshot $SSM_LVM_DEFAULT_POOL/${lvol1}notexist
ssm -f remove --all

# Snapshot size overflow should fail
ssm create $dev1 $dev2
ssm add $dev3
not ssm snapthot -s $((DEV_SIZE*2)) -n $snap1 $SSM_LVM_DEFAULT_POOL/$lvol1
check vg_field $SSM_LVM_DEFAULT_POOL lv_count 1
ssm -f remove --all
