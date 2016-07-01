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

export test_name='004-resize'
test_description='Exercise ssm resize'

. lib/test

DEV_COUNT=10
DEV_SIZE=100
# The real size of the device which lvm will use is smaller
TEST_MAX_SIZE=$(($DEV_COUNT*($DEV_SIZE-4)))
aux prepare_devs $DEV_COUNT $DEV_SIZE
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
DEFAULT_VOLUME=${SSM_LVM_DEFAULT_POOL}/$lvol1

TEST_FS=
which mkfs.ext2 && grep -E "^\sext[234]$" /proc/filesystems && TEST_FS+="ext2 "
which mkfs.ext3 && grep -E "^\sext[34]$" /proc/filesystems && TEST_FS+="ext3 "
which mkfs.ext4 && grep -E "^\sext4$" /proc/filesystems && TEST_FS+="ext4 "
which mkfs.xfs  && grep -E "^\sxfs$" /proc/filesystems && TEST_FS+="xfs"

TEST_MNT=$TESTDIR/mnt

_test_resize()
{
	# Test with no device
	# Test size increase
	size=$DEV_SIZE
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
	size=$((DEV_SIZE + 12))
	ssm resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
	size=$((size + 3))
	ssm resize -s +3M $SSM_LVM_DEFAULT_POOL/$lvol1
	size=$(align_size_up $size)
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
	# Test size decrese
	if [ "$fs" != "xfs" ]; then
		size=$((size - 8))
		ssm -f resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1
		check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
		size=$((size - 7))
		ssm -f resize -s-7M $SSM_LVM_DEFAULT_POOL/$lvol1
		size=$(align_size_up $size)
		check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
		# Test with devcie belongs to no pool
		# size decrease
		size=$((size - 12))
		ssm -f resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev4
		check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
		check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
		check vg_field $pool1 pv_count 3
	fi
	# If the volume is already of the given size ssm will attempt to resize
	# file system to cover the whole device. Note that we do not check for
	# the file system size because it's not really necessary. So this would
	# fail if the file system is present. This might change in future, so
	# comment it out for now.
	# size doesn't change
	#not ssm -f resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev4
	#check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
	#check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
	#check vg_field $pool1 pv_count 3
	# size increase
	size=$((size + 12))
	ssm resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev4
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
	check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
	check vg_field $pool1 pv_count 3

	# Test with device belongs to other pool
	# size decrease
	if [ "$fs" != "xfs" ]; then
		size=$((size - 12))
		ssm -f resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev6
		check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
		check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
		check vg_field $pool1 pv_count 3
	fi
	# size doesn't change
	#not ssm -f resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev6
	#check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
	#check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
	#check vg_field $pool1 pv_count 3
	# size increase
	size=$((size + 12))
	ssm -f resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev6
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
	check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
	check vg_field $pool1 pv_count 3

	# when resize to excessive amount
	size=$((DEV_SIZE*4))
	not ssm resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1
	ssm resize -s ${size}M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev8 $dev9
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
	check vg_field $SSM_LVM_DEFAULT_POOL pv_count 5

}

ssm add $TEST_DEVS
size=$((TEST_MAX_SIZE/3))
ssm create --size ${size}M $TEST_DEVS
size=$(align_size_up $size)
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m

export SSM_DEFAULT_BACKEND='btrfs'
ssm -f resize --size +$(($TEST_MAX_SIZE/3))M ${DM_DEV_DIR}/$DEFAULT_VOLUME
size=$(align_size_up $(($size+($TEST_MAX_SIZE/3))))
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
export SSM_DEFAULT_BACKEND='lvm'

ssm -f resize -s-$(($TEST_MAX_SIZE/2))M $DEFAULT_VOLUME
size=$(align_size_up $(($size-($TEST_MAX_SIZE/2))))
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m

ssm -f resize --size $(($TEST_MAX_SIZE/2))M $DEFAULT_VOLUME
size=$(align_size_up $(($TEST_MAX_SIZE/2)))
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
ssm -f remove $SSM_LVM_DEFAULT_POOL

ssm create $dev1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
ssm resize --size +$((TEST_MAX_SIZE/2))M $DEFAULT_VOLUME $TEST_DEVS
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count $DEV_COUNT
ssm -f remove $SSM_LVM_DEFAULT_POOL

ssm create $dev1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
ssm resize --size $((TEST_MAX_SIZE/2))M ${DM_DEV_DIR}/$DEFAULT_VOLUME $TEST_DEVS
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count $DEV_COUNT
ssm -f remove $SSM_LVM_DEFAULT_POOL

ssm create --size $((DEV_SIZE/2))M $dev1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
ssm resize --size +$((DEV_SIZE/3))M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
ssm -f resize -s-$((DEV_SIZE/3))M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
ssm resize --size +$((DEV_SIZE/3))M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
ssm -f resize -s-$((DEV_SIZE/3))M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
ssm resize --size +${DEV_SIZE}M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 3
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Resize using percentage of the size
ssm create $TEST_DEVS
size=$(($TEST_MAX_SIZE/2))
ssm -f resize -s-50% $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$(($size+($size/4)))
ssm resize -s +25% $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$TEST_MAX_SIZE
ssm resize -s +100%FREE $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$(($TEST_MAX_SIZE/2))
ssm -f resize -s-50%USED $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$((($TEST_MAX_SIZE/2)+($size/2)))
ssm resize -s +50%USED $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$(($size-($size/2)))
ssm -f resize -s-50%USED $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m

# Resize using percentage of the size
size=$TEST_MAX_SIZE
ssm resize -s +100%FREE $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$(($TEST_MAX_SIZE/4))
ssm -f resize --size 25% $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$(($TEST_MAX_SIZE/2))
ssm resize --size 200% $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$(($TEST_MAX_SIZE/4))
ssm -f resize --size 50%free $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
size=$(($TEST_MAX_SIZE/2))
ssm resize --size 200%used $SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
not ssm resize --size +1000% $SSM_LVM_DEFAULT_POOL/$lvol1
ssm -f remove $SSM_LVM_DEFAULT_POOL

ssm add $dev{1,2,3}
ssm create -s ${DEV_SIZE}M
ssm add -p $pool1 $dev{5,6,7}
_test_resize
ssm -f remove $SSM_LVM_DEFAULT_POOL
ssm -f remove $pool1


[ ! -d $TEST_MNT ] && mkdir $TEST_MNT &> /dev/null
for fs in $TEST_FS; do
	ssm add $dev{1,2,3}
	ssm create -s ${DEV_SIZE}M --fs $fs
	ssm -f check $DEFAULT_VOLUME
	ssm add -p $pool1 $dev{5,6,7}
	_test_resize
	ssm -f check $DEFAULT_VOLUME
	ssm -f remove $SSM_LVM_DEFAULT_POOL
	ssm -f remove $pool1
done
# There should not be anything to remove
not ssm  -f remove --all

ssm create $dev1
ssm resize -s +$((DEV_SIZE/2))M  $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2
ssm -f remove $SSM_LVM_DEFAULT_POOL
# Use device with existing file system
mkfs.ext3 $dev2
ssm create $dev1
not ssm resize -s +$((DEV_SIZE/2))M  $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2
ssm resize -s +$((DEV_SIZE/2))M  $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
ssm -f remove --all

# Use device with existing file system
mkfs.ext3 $dev2
ssm create $dev1
ssm -f resize -s +$((DEV_SIZE/2))M  $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 2
ssm -f remove $SSM_LVM_DEFAULT_POOL

mkfs.ext3 $dev2
ssm create $dev1
ssm -f resize -s +$((DEV_SIZE/2))M  $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 3
ssm -f remove --all

# Try to resize inactive volume
ssm create --fs ext4 --size ${DEV_SIZE}M $dev1 $dev2 $dev3
lvchange -a n $SSM_LVM_DEFAULT_POOL/$lvol1
ssm resize --size +${DEV_SIZE}M $DM_DEV_DIR/$SSM_LVM_DEFAULT_POOL/$lvol1
not ssm resize -s-${DEV_SIZE}M $DM_DEV_DIR/$SSM_LVM_DEFAULT_POOL/$lvol1
ssm -f resize -s-${DEV_SIZE}M $DM_DEV_DIR/$SSM_LVM_DEFAULT_POOL/$lvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${DEV_SIZE}.00m
ssm -f remove --all

# Use device already used in different pool
ssm create $dev1
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 1
ssm add -p $pool1 $dev2 $dev3
check vg_field $pool1 pv_count 2
not ssm resize -s +$((DEV_SIZE/2))M  $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2
ssm resize -s +$((DEV_SIZE/2))M  $SSM_LVM_DEFAULT_POOL/$lvol1 $dev3 $dev4
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 2
ssm -f remove --all

# Use device already used in different pool with force
ssm create $dev1
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 1
ssm add -p $pool1 $dev2 $dev3
check vg_field $pool1 pv_count 2
ssm -f resize -s +$((DEV_SIZE/2))M  $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 2
ssm -f remove --all

# Some basic thin tests
export TVOL_PREFIX="tvol"
tvol1=${TVOL_PREFIX}001
tpool1=${SSM_LVM_DEFAULT_POOL}_thin001

# Resize thin volume
virtualsize=$(($DEV_SIZE*10))
ssm create --virtual-size ${virtualsize}M $dev1 $dev2 $dev3
virtualsize=$(align_size_up $virtualsize)
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
check lv_field $SSM_LVM_DEFAULT_POOL/$tpool1 pv_count 3
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 lv_size ${virtualsize}.00m
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 segtype thin
check list_table "$(ssm list pool)" $SSM_LVM_DEFAULT_POOL lvm 3 none none none
check list_table "$(ssm list pool)" $tpool1 thin 3 none none none $SSM_LVM_DEFAULT_POOL
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$tvol1 $tpool1 ${virtualsize}.00MB thin
# Increase size of the thin volume
ssm -f resize --size 100G ${DM_DEV_DIR}/$SSM_LVM_DEFAULT_POOL/$tvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 lv_size 100.00g
ssm -f resize --size +100G ${DM_DEV_DIR}/$SSM_LVM_DEFAULT_POOL/$tvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 lv_size 200.00g
ssm -f resize --size +10% ${DM_DEV_DIR}/$SSM_LVM_DEFAULT_POOL/$tvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 lv_size 220.00g
ssm -f resize --size 50% ${DM_DEV_DIR}/$SSM_LVM_DEFAULT_POOL/$tvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 lv_size 110.00g
# Decrease size of the thin volume
ssm -f resize --size 100G ${DM_DEV_DIR}/$SSM_LVM_DEFAULT_POOL/$tvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 lv_size 100.00g
ssm -f resize -s-50% ${DM_DEV_DIR}/$SSM_LVM_DEFAULT_POOL/$tvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 lv_size 50.00g
ssm -f resize -s-10G ${DM_DEV_DIR}/$SSM_LVM_DEFAULT_POOL/$tvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 lv_size 40.00g
ssm -f resize -s200% ${DM_DEV_DIR}/$SSM_LVM_DEFAULT_POOL/$tvol1
check lv_field $SSM_LVM_DEFAULT_POOL/$tvol1 lv_size 80.00g
ssm  -f remove --all

# Resize thin pool
virtualsize=$(($DEV_SIZE*10))
size=$(($DEV_SIZE*2))
ssm create --size ${size}M --virtual-size ${virtualsize}M $TEST_DEVS
virtualsize=$(align_size_up $virtualsize)
size=$(align_size_up $size)
check lv_field $SSM_LVM_DEFAULT_POOL/$tpool1 pv_count $DEV_COUNT
check lv_field $SSM_LVM_DEFAULT_POOL/$tpool1 lv_size ${size}.00m
check list_table "$(ssm list pool)" $tpool1 thin $DEV_COUNT none none ${size}.00MB $SSM_LVM_DEFAULT_POOL
# Increase size of the thin pool
size=$(($DEV_SIZE*3))
ssm resize --size ${size}M $SSM_LVM_DEFAULT_POOL/$tpool1
check lv_field $SSM_LVM_DEFAULT_POOL/$tpool1 lv_size ${size}.00m
size=$(($DEV_SIZE*4))
ssm resize --size +${DEV_SIZE}M $SSM_LVM_DEFAULT_POOL/$tpool1
check lv_field $SSM_LVM_DEFAULT_POOL/$tpool1 lv_size ${size}.00m
size=$(($DEV_SIZE*6))
ssm resize --size +50% $SSM_LVM_DEFAULT_POOL/$tpool1
check lv_field $SSM_LVM_DEFAULT_POOL/$tpool1 lv_size ${size}.00m
size=$(($DEV_SIZE*9))
ssm resize --size 150% $SSM_LVM_DEFAULT_POOL/$tpool1
check lv_field $SSM_LVM_DEFAULT_POOL/$tpool1 lv_size ${size}.00m
not ssm resize --size 500% $SSM_LVM_DEFAULT_POOL/$tpool1
ssm  -f remove --all

ssm resize --help

# Some cases which should fail
not ssm resize
not ssm resize _garbage_
not ssm resize $dev1
ssm create $TEST_DEVS
not ssm resize $DEFAULT_VOLUME
not ssm -f resize --size +10G $DEFAULT_VOLUME
not ssm -f resize -s-10G $DEFAULT_VOLUME
