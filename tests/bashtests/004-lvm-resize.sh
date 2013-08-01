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
	size=$((TEST_MAX_SIZE/2))
	echo 'y' | ssm -f resize --size ${size}M ${DM_DEV_DIR}/$DEFAULT_VOLUME
	size=$(align_size_up $size)
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m

	# xfs does not support shrinking (xfs only grows big!! :))
	if [ "$fs" != "xfs" ]; then
		ssm -f -v resize -s-$(($TEST_MAX_SIZE/4))M $DEFAULT_VOLUME
		size=$(align_size_up $(($size-($TEST_MAX_SIZE/4))))
		check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
	fi
	echo 'y' | ssm -f resize --size +$(($TEST_MAX_SIZE/5))M $DEFAULT_VOLUME
	size=$(align_size_up $(($size+($TEST_MAX_SIZE/5))))
	check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${size}.00m
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
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 2
ssm -f resize -s-$((DEV_SIZE/3))M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
ssm resize --size +$((DEV_SIZE/3))M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 3
ssm -f resize -s-$((DEV_SIZE/3))M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 3
ssm resize --size +${DEV_SIZE}M $SSM_LVM_DEFAULT_POOL/$lvol1 $dev2 $dev3
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 3
ssm -f remove $SSM_LVM_DEFAULT_POOL

[ ! -d $TEST_MNT ] && mkdir $TEST_MNT &> /dev/null
for fs in $TEST_FS; do
	# umounted test
	ssm add $TEST_DEVS
	size=$((TEST_MAX_SIZE/4))
	ssm create --fs $fs --size ${size}M $TEST_DEVS

	_test_resize
	ssm -f check $DEFAULT_VOLUME
	ssm -f remove $SSM_LVM_DEFAULT_POOL

        echo $fs
        if [ $fs == 'ext2' ]; then
            continue
        fi

        # Disable this for now, since fsadm does not handle -f and -y correctly
	# mounted test
	#ssm add $TEST_DEVS
	size=$((TEST_MAX_SIZE/4))
	#ssm create --fs $fs --size ${size}M $TEST_DEVS

	#mount ${DM_DEV_DIR}/$DEFAULT_VOLUME $TEST_MNT

	#_test_resize

	#umount $TEST_MNT
	#ssm -f check $DEFAULT_VOLUME
	#ssm -f remove $SSM_LVM_DEFAULT_POOL
done
not ssm  -f remove --all

ssm resize --help

# Some cases which should fail
not ssm resize
not ssm resize _garbage_
not ssm resize $dev1
ssm create $TEST_DEVS
not ssm resize $DEFAULT_VOLUME
not ssm -f resize --size +10G $DEFAULT_VOLUME
not ssm -f resize -s-10G $DEFAULT_VOLUME
