#!/bin/bash
#
# (C)2013 Red Hat, Inc., Jimmy Pan <jipan@redhat.com>
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


export test_name='013-lvm-check'
export test_description='Exercise ssm lvm check'

. lib/test

DEV_COUNT=10
DEV_SIZE=100
aux prepare_devs $DEV_COUNT $DEV_SIZE
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='lvm'
export LVOL_PREFIX="lvol"
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'
lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002
lvol3=${LVOL_PREFIX}003


pool1=$vg2
pool2=$vg3

TEST_FS=
which mkfs.ext2 && grep -E "^\sext[234]$" /proc/filesystems && TEST_FS+="ext2 "
which mkfs.ext3 && grep -E "^\sext[34]$" /proc/filesystems && TEST_FS+="ext3 "
which mkfs.ext4 && grep -E "^\sext4$" /proc/filesystems && TEST_FS+="ext4 "
which mkfs.xfs  && grep -E "^\sxfs$" /proc/filesystems && TEST_FS+="xfs"

filesystem_check()
{
	if [ $# -lt 3 ] ; then
		echo Usage: filesystem_check pool volume filesystem
		exit 1
	fi
	local pool=$1
	local vol=$2
	local fs=$3
	local name=$pool/$vol
	local path=`lvs --noheadings -o lv_path $name`
	if [[ $fs == ext[234] ]] ; then
		e2fsck -n $path
	elif [[ $fs == xfs ]] ; then
		xfs_repair -n $path
	else
		echo Invalid fs type
		exit 1
	fi
}


# No filesystem should fail
ssm create $dev1
not ssm check $SSM_LVM_DEFAULT_POOL/$lvol1
ssm -f remove -a

# Loop for different filesystems
for fs in $TEST_FS ; do
	# Test check of a volume with one device
	ssm create --fs $fs -p $SSM_LVM_DEFAULT_POOL $dev1
	ret1=0
	filesystem_check $SSM_LVM_DEFAULT_POOL $lvol1 $fs || ret1=$?
	ret2=0
	ssm check $SSM_LVM_DEFAULT_POOL/$lvol1 || ret2=$?
	test "$ret1" -eq "$ret2" || [[ "$ret1" -ne 0 && "$ret2" -ne 0 ]]
	ret2=0
	ssm check `lvs --noheadings -o lv_path $SSM_LVM_DEFAULT_POOL/$lvol1` || ret2=$?
	test "$ret1" -eq "$ret2" || [[ "$ret1" -ne 0 && "$ret2" -ne 0 ]]

	# Test check of a volume with one device with one device has specified
	# size and on two devices
	ssm create -p $pool1 --fs $fs -s $((DEV_SIZE+20))m $dev{2,3}
	ret1=0
	filesystem_check $pool1 $lvol1 $fs || ret1=$?
	ret2=0
	ssm check $pool1/$lvol1 || ret2=$?
	test "$ret1" -eq "$ret2" || [[ "$ret1" -ne 0 && "$ret2" -ne 0 ]]
	ret2=0
	ssm check `lvs --noheadings -o lv_path $pool1/$lvol1` || ret2=$?
	test "$ret1" -eq "$ret2" || [[ "$ret1" -ne 0 && "$ret2" -ne 0 ]]

	# Test check of volumes from the same pools
	ssm create -p $pool2 --fs $fs $dev{4,5,6}
	ssm create --fs $fs $dev{7,8} -p $pool2
	ret1=0
	filesystem_check $pool2 $lvol1 $fs || ret1=$?
	ret2=0
	ssm check $pool2/$lvol1 || ret2=$?
	test "$ret1" -eq "$ret2" || [[ "$ret1" -ne 0 && "$ret2" -ne 0 ]]
	ret2=0
	ssm check `lvs --noheadings -o lv_path $pool2/$lvol1` || ret2=$?
	test "$ret1" -eq "$ret2" || [[ "$ret1" -ne 0 && "$ret2" -ne 0 ]]
	ret1=0
	filesystem_check $pool2 $lvol2 $fs || ret1=$?
	ret2=0
	ssm check $pool2/$lvol2 || ret2=$?
	test "$ret1" -eq "$ret2" || [[ "$ret1" -ne 0 && "$ret2" -ne 0 ]]

	# Test check of volumes from different pools at once
	ret2=0
	ssm check `lvs --noheadings -o lv_path $pool2/$lvol2` || ret2=$?
	test "$ret1" -eq "$ret2" || [[ "$ret1" -ne 0 && "$ret2" -ne 0 ]]
	vols="$SSM_LVM_DEFAULT_POOL/$lvol1 $pool1/$lvol1 $pool2/$lvol1 $pool2/$lvol2"
	ssm check $vols | not grep -i fail
	ssm check `lvs --noheadings -o lv_path $vols` | not grep -i fail

	# Check invalid volume name should fail
	not ssm check $pool2/$lvol2"nsdf"
	ssm -f remove -a
done

# Some should fail
not ssm check
not ssm check non_existing
