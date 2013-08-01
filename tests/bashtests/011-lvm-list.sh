#!/bin/bash
#
# (C)2012 Red Hat, Inc., Tom Marek <tmarek@redhat.com>
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

export test_name='011-lvm-list'
export test_description='Check whether list command prints correct values for lvm'

. lib/test

DEV_COUNT=10
DEV_SIZE=100
TEST_MAX_SIZE=$(($DEV_COUNT*$DEV_SIZE))
aux prepare_devs $DEV_COUNT $DEV_SIZE
TEST_DEVS=$(cat DEVICES)
export LVOL_PREFIX="lvol"
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'

snap1="snap1"
snap2="snap2"

pool1=$vg2
pool2=$vg3

TEST_FS=
which mkfs.ext2 && TEST_FS+="ext2 "
which mkfs.ext3 && TEST_FS+="ext3 "
which mkfs.ext4 && TEST_FS+="ext4 "
which mkfs.xfs  && TEST_FS+="xfs"

TEST_MNT=$TESTDIR/mnt
[ ! -d $TEST_MNT ] && mkdir $TEST_MNT &> /dev/null

##LVM
# Check devices
ssm add $TEST_DEVS
ssm_output=$(ssm list dev)
for device in ${TEST_DEVS}; do
     check list_table "$ssm_output" $device 96.00MB 0.00KB 96.00MB $SSM_LVM_DEFAULT_POOL
done

# Check pools
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL $SSM_DEFAULT_BACKEND $DEV_COUNT none none 960.00MB
ssm -f remove --all

# create multiple pools
ssm create --pool $pool1 $dev1 $dev2 $dev3 $dev4
ssm create --pool $pool2 $dev5 $dev6 $dev7 $dev8
ssm_output=$(ssm list pool)
check list_table "$ssm_output" $pool1 lvm 4 none none 384.00MB
check list_table "$ssm_output" $pool2 lvm 4 none none 384.00MB
ssm -f remove --all

ssm add $TEST_DEVS

# Check LVM volume listings with various fs
for fs in $TEST_FS; do
    name="${fs}vol"
    ssm create --fs=$fs -r 0 -I 8 -i $((DEV_COUNT/5)) -s $(($DEV_SIZE*2))M -n "${fs}vol"
done
# Mounted
for fs in $TEST_FS; do
    mount ${DM_DEV_DIR}/${SSM_LVM_DEFAULT_POOL}/${fs}vol $TEST_MNT
    check list_table "$(ssm list vol)" ${fs}vol $SSM_LVM_DEFAULT_POOL $(($DEV_SIZE*2)).00MB ${fs} none none striped $TEST_MNT
    umount $TEST_MNT
done
# Unmounted
ssm_output=$(ssm list vol)
for fs in $TEST_FS; do
    check list_table "$ssm_output" ${fs}vol $SSM_LVM_DEFAULT_POOL $(($DEV_SIZE*2)).00MB ${fs} none none striped
done
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Check lvm snapshot
lvol1=${LVOL_PREFIX}001
# Create volume with all devices at once
size=$(($DEV_SIZE*6))
snap_size1=$(($DEV_SIZE))
snap_size2=$(($size/5))
ssm create --size ${size}M $TEST_DEVS
ssm snapshot --name $snap1 --size ${snap_size1}M $SSM_LVM_DEFAULT_POOL/$lvol1
ssm snapshot --name $snap2 --size ${snap_size2}M $SSM_LVM_DEFAULT_POOL/$lvol1
ssm_output=$(ssm list snap)
check list_table "$ssm_output" $snap1 $lvol1 ${snap_size1}.00MB 0.00KB linear
check list_table "$ssm_output" $snap2 $lvol1 ${snap_size2}.00MB 0.00KB linear
ssm -f remove --all

# Snapshot of the volumes in defferent pools
ssm create --pool $pool1 $dev1 $dev2
ssm add $dev3 $dev4 --pool $pool1
ssm create --pool $pool2 $dev5 $dev6
ssm add $dev7 $dev8 --pool $pool2
ssm snapshot --name $snap1 $pool1/$lvol1
ssm snapshot --name $snap1 $pool2/$lvol1
ssm_output=$(ssm list snap)
check list_table "$ssm_output" "$pool1/$snap1" $lvol1 40.00MB 0.00KB linear
check list_table "$ssm_output" "$pool2/$snap1" $lvol1 40.00MB 0.00KB linear
ssm -f remove --all

# all_done!!!
