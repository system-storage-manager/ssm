#!/bin/bash
#
# (C)2013 Red Hat, Inc., Jan Tulak <jtulak@redhat.com>
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

export test_name='017-info'
export test_description='Check whether info command prints correct values'

. lib/test

DEV_COUNT=10
DEV_SIZE=128
TEST_MAX_SIZE=$(($DEV_COUNT*$DEV_SIZE))
aux prepare_devs $DEV_COUNT $DEV_SIZE
aux prepare_mnts 10
TEST_DEVS=$(cat DEVICES)
export LVOL_PREFIX="lvol"
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'

snap1="snap1"
snap2="snap2"

lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002
lvol3=${LVOL_PREFIX}003

pool0=$vg1
pool1=$vg2
pool2=$vg3
pool3=$vg4

TEST_FS=
#which mkfs.ext2 && TEST_FS+="ext2 "
#which mkfs.ext3 && TEST_FS+="ext3 "
which mkfs.ext4 && TEST_FS+="ext4 "
which mkfs.xfs  && TEST_FS+="xfs"

TEST_MNT=$TESTDIR/mnt
[ ! -d $TEST_MNT ] && mkdir $TEST_MNT &> /dev/null

# Prepare pools and volumes

vol1=volsf
vol2=volss
vol3=volmf
vol4=volms1
vol5=volms2
vol6=volms3
maxvolsz=$((DEV_SIZE-4))
size1=$maxvolsz
size2=$((DEV_SIZE/2))
size3=$((maxvolsz*2))
size4=$((DEV_SIZE/2))
size5=$((DEV_SIZE*2))
size6=$((DEV_SIZE/4))
size4s=$((size4-20))
size2r=$((size2-4))
size5r=$((size5+16))

## test a btrfs on a partition
#
# this is commented out, because the current testing infrastructure is not able
# to handle such configuration. We need to move away from the lvm-like test suite
# as anything complex and non-lvm is having issues with it. But at the same time
# I want this test documented.
#
#
# Test btrfs on a (loopback) partition.
# This is a reproducer of a reported issue with ssm info.
#
# to create the partitions programatically (rather than manually)
# we're going to simulate the manual input to fdisk
# The sed script strips off all the comments so that we can
# document what we're doing in-line with the actual commands
# Note that a blank line (commented as "defualt" will send a empty
# line terminated with a newline to take the fdisk default.
#
#sed -e 's/\s*\([\+0-9a-zA-Z]*\).*/\1/' << EOF | gdisk ${dev1}
#  n # new partition
#  1 # partition number 1
#    # default - start at beginning of disk
#    # default - end at end of disk
#    # default - partition type is not important
#  p # print the in-memory partition table
#  w # write the partition table
#  Y # confirm
#  q # and we're done
#EOF
#partprobe -s $dev1
#
#mkfs.btrfs ${dev1}p1
#ssm info
#


# Test without a filesystem
ssm -f create -n $vol1 $dev1
ssm create -n $vol2 -p $pool1 -s ${size2}M $dev2
ssm create -n $vol3 -p $pool2 $dev3 $dev4
ssm add -p $pool3 $dev{5,6,7,8}
ssm create -p $pool3 -s ${size4}m -n $vol4
ssm create -p $pool3 -s ${size5}m -n $vol5
ssm create -p $pool3 -s ${size6}m -n $vol6
lvchange -an $pool3/$vol6

# test a not found case
output=$(not ssm info foobarbaznotfound 2>&1 )
echo "$output" | grep "The item 'foobarbaznotfound' was not found."

# Check vol, dev, pool, resized vol, and snapshot
output=`ssm info $pool0`
check info_table none "$output" "pool name" name $pool0
check info_table none "$output" type lvm volume group
check info_table none "$output" "logical volume" volume ".*$pool0-$vol1"
check info_table none "$output" size $size1.00MB
check info_table none "$output" used $size1.00MB

output=`ssm info $pool1`
check info_table none "$output" "pool name" name $pool1
check info_table none "$output" type lvm volume group
check info_table none "$output" "logical volume" volume ".*$pool1-$vol2"
check info_table none "$output" size $size1.00MB
check info_table none "$output" used $size2.00MB

output=`ssm info $pool2`
check info_table none "$output" "pool name" name $pool2
check info_table none "$output" type lvm volume group
check info_table none "$output" "logical volume" volume ".*$pool2-$vol3"
check info_table none "$output" size $size3.00MB
check info_table none "$output" used $size3.00MB

output=`ssm info $pool3`
check info_table none "$output" "pool name" name $pool3
check info_table none "$output" type lvm volume group
# The "\|#" is there because info_table none adds a space at the end
# of the expression, but we have to get rid of it without causing
# false matches.
check info_table none "$output" "logical volume.*$vol4\|#" volume ".*$pool3.$vol4"
check info_table none "$output" "logical volume.*$vol5\|#" volume ".*$pool3.$vol5"
check info_table none "$output" "logical volume.*$vol6\|#" volume ".*$pool3.$vol6"
check info_table none "$output" size $((maxvolsz*4)).00MB
check info_table none "$output" used $((size4+size5+size6)).00MB


output=`ssm info $dev1`
check info_table none "$output" type disk
check info_table none "$output" "object name" name ".*$dev1"
check info_table none "$output" "size" $size1.00MB

output=$(ssm info $pool0/$vol1)
check info_table none "$output" type lvm logical volume
check info_table none "$output" "object name.*dev/$pool0/$vol1\|#"
check info_table none "$output" "object name.*mapper/$pool0-$vol1\|#"
check info_table none "$output" "size" $size1.00MB
check info_table none "$output" "parent pool"
check info_table "parent pool" "$output" type lvm volume group
check info_table "parent pool" "$output" name $pool0


# Check ssm vol after resize
ssm -f resize $pool1/$vol2 -s ${size2r}M
ssm resize -s ${size5r}m $pool3/$vol5

output=`ssm info $pool1`
check info_table none "$output" size $size1.00MB
check info_table none "$output" used $size2r.00MB
output=`ssm info $pool3/$vol5`
check info_table none "$output" size $size5r.00MB

ssm snapshot $pool3/$vol4 -n snap1
ssm snapshot $pool3/$vol4 -s ${size4s}m -n snap2
output=`ssm info $pool3/snap1`
check info_table none "$output" type snapshot
check info_table none "$output" parent volume $pool3/$vol4
output=`ssm info $pool3/snap2`
check info_table none "$output" size $size4s.00MB

ssm -f remove -a

# Test with filesystem
for fs in $TEST_FS ; do
	ssm -f create -n $vol1 $dev1 --fs $fs
	ssm create -n $vol2 -p $pool1 -s ${size2}M $dev2 --fs $fs

	# Check fs, vol, dev, pool, resized vol, and snapshot
	output=`ssm info $pool0/$vol1`
	check info_table none "$output" "object name.*$pool0/$vol1"
	check info_table filesystem "$output" "type"  $fs

	ssm -f remove -a

done

# Create volume with all devices at once
size=$(($DEV_SIZE*6))
ssm create --size ${size}M $TEST_DEVS

# Take a snapshot with the default params
export SSM_DEFAULT_BACKEND='btrfs'
ssm snapshot --name $snap1 $SSM_LVM_DEFAULT_POOL/$lvol1

output=$(ssm info $SSM_LVM_DEFAULT_POOL/$snap1)
check info_table none "$output" "object name.*$SSM_LVM_DEFAULT_POOL/$snap1"
check info_table none "$output" "type" snapshot
check info_table none "$output" "parent volume.*$SSM_LVM_DEFAULT_POOL/$lvol1"

output=$(ssm info $SSM_LVM_DEFAULT_POOL)
check info_table none "$output" "type" lvm volume group
check info_table none "$output" "logical volume.*$snap1"


export SSM_DEFAULT_BACKEND='lvm'



exit 0
