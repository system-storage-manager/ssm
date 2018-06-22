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

export test_name='011-lvm-list'
export test_description='Check whether list command prints correct values for lvm'

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
which mkfs.ext2 && TEST_FS+="ext2 "
which mkfs.ext3 && TEST_FS+="ext3 "
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


# Test without a filesystem
ssm -f create -n $vol1 $dev1
ssm create -n $vol2 -p $pool1 -s ${size2}M $dev2
ssm create -n $vol3 -p $pool2 $dev3 $dev4
ssm add -p $pool3 $dev{5,6,7,8}
ssm create -p $pool3 -s ${size4}m -n $vol4
ssm create -p $pool3 -s ${size5}m -n $vol5
ssm create -p $pool3 -s ${size6}m -n $vol6
lvchange -an $pool3/$vol6

# We shouldn't see ssm list fs here
test `ssm list fs | wc -l` -le 1
# Check vol, dev, pool, resized vol, and snapshot
output=`ssm list vol`
check list_table "$output" $pool0/$vol1 $pool0 $((size1)).00MB linear
check list_table "$output" $pool1/$vol2 $pool1 $size2.00MB linear
check list_table "$output" $pool2/$vol3 $pool2 $((size3)).00MB linear
check list_table "$output" $pool3/$vol4 $pool3 $((size4)).00MB linear
check list_table "$output" $pool3/$vol5 $pool3 $((size5)).00MB linear
check list_table "$output" $pool3/$vol6 $pool3 $((size6)).00MB linear
output=`ssm list dev`
check list_table "$output" $dev1 0.00KB $((size1)).00MB 124.00MB $pool0
check list_table "$output" $dev2 $((maxvolsz-size2)).00MB $((size2)).00MB 124.00MB $pool1
check list_table "$output" $dev3 0.00KB $((maxvolsz)).00MB 124.00MB $pool2
check list_table "$output" $dev4 0.00KB $((maxvolsz)).00MB 124.00MB $pool2
check list_table "$output" $dev5 none none 124.00MB $pool3
check list_table "$output" $dev6 none none 124.00MB $pool3
check list_table "$output" $dev7 none none 124.00MB $pool3
check list_table "$output" $dev8 none none 124.00MB $pool3
output=`ssm list pool`
check list_table "$output" $pool0 lvm 1 0.00KB $((size1)).00MB $((maxvolsz)).00MB
check list_table "$output" $pool1 lvm 1 $((maxvolsz-size2)).00MB $((size2)).00MB $((maxvolsz)).00MB
check list_table "$output" $pool2 lvm 2 0.00KB $((size3)).00MB $((maxvolsz*2)).00MB
check list_table "$output" $pool3 lvm 4 $((maxvolsz*4-size4-size5-size6)).00MB $((size4+size5+size6)).00MB $((maxvolsz*4)).00MB

# Check ssm vol after resize
ssm -f resize $pool1/$vol2 -s ${size2r}M
ssm resize -s ${size5r}m $pool3/$vol5
output=`ssm list vol`
check list_table "$output" $pool1/$vol2 $pool1 $size2r.00MB linear
check list_table "$output" $pool3/$vol5 $pool3 $((size5r)).00MB linear

ssm snapshot $pool3/$vol4 -n snap1
ssm snapshot $pool3/$vol4 -s ${size4s}m -n snap2
output=`ssm list snap`
check list_table "$output" $pool3/snap1 $vol4 $pool3 none none linear
check list_table "$output" $pool3/snap2 $vol4 $pool3 $size4s.00MB none linear


ssm -f remove -a


# Test with filesystem
for fs in $TEST_FS ; do
	ssm -f create -n $vol1 $dev1 --fs $fs
	ssm create -n $vol2 -p $pool1 -s ${size2}M $dev2 --fs $fs
	ssm create -n $vol3 -p $pool2 $dev3 $dev4 --fs $fs
	ssm add -p $pool3 $dev{5,6,7,8}
	ssm create -p $pool3 -s ${size4}m -n $vol4 --fs $fs
	ssm create -p $pool3 -s ${size5}m -n $vol5 --fs $fs
	ssm create -p $pool3 -s ${size6}m -n $vol6 --fs $fs

	# Check fs, vol, dev, pool, resized vol, and snapshot
	output=`ssm list fs`
	# xfs has some strange used size, so we don't check it
	if [ $fs == xfs ] ; then
		check list_table "$output" $pool0/$vol1 $pool0 $size1.00MB $fs none none linear
		check list_table "$output" $pool1/$vol2 $pool1 $size2.00MB $fs none none linear
		check list_table "$output" $pool2/$vol3 $pool2 $size3.00MB $fs none none linear
		check list_table "$output" $pool3/$vol4 $pool3 $size4.00MB $fs none none linear
		check list_table "$output" $pool3/$vol5 $pool3 $size5.00MB $fs none none linear
		check list_table "$output" $pool3/$vol6 $pool3 $size6.00MB $fs none none linear
	else
		check list_table "$output" $pool0/$vol1 $pool0 $size1.00MB $fs $size1.00MB none linear
		check list_table "$output" $pool1/$vol2 $pool1 $size2.00MB $fs $size2.00MB none linear
		check list_table "$output" $pool2/$vol3 $pool2 $size3.00MB $fs $size3.00MB none linear
		check list_table "$output" $pool3/$vol4 $pool3 $size4.00MB $fs $size4.00MB none linear
		check list_table "$output" $pool3/$vol5 $pool3 $size5.00MB $fs $size5.00MB none linear
		check list_table "$output" $pool3/$vol6 $pool3 $size6.00MB $fs $size6.00MB none linear
	fi

	output=`ssm list vol`
	# xfs has some strange used size, so we don't check it
	if [ $fs == xfs ] ; then
		check list_table "$output" $pool0/$vol1 $pool0 $size1.00MB $fs none none linear
		check list_table "$output" $pool1/$vol2 $pool1 $size2.00MB $fs none none linear
		check list_table "$output" $pool2/$vol3 $pool2 $size3.00MB $fs none none linear
		check list_table "$output" $pool3/$vol4 $pool3 $size4.00MB $fs none none linear
		check list_table "$output" $pool3/$vol5 $pool3 $size5.00MB $fs none none linear
		check list_table "$output" $pool3/$vol6 $pool3 $size6.00MB $fs none none linear
	else
		check list_table "$output" $pool0/$vol1 $pool0 $size1.00MB $fs $size1.00MB none linear
		check list_table "$output" $pool1/$vol2 $pool1 $size2.00MB $fs $size2.00MB none linear
		check list_table "$output" $pool2/$vol3 $pool2 $size3.00MB $fs $size3.00MB none linear
		check list_table "$output" $pool3/$vol4 $pool3 $size4.00MB $fs $size4.00MB none linear
		check list_table "$output" $pool3/$vol5 $pool3 $size5.00MB $fs $size5.00MB none linear
		check list_table "$output" $pool3/$vol6 $pool3 $size6.00MB $fs $size6.00MB none linear
	fi

	output=`ssm list dev`
	check list_table "$output" $dev1 0.00KB $((size1)).00MB 124.00MB $pool0
	check list_table "$output" $dev2 $((maxvolsz-size2)).00MB $((size2)).00MB 124.00MB $pool1
	check list_table "$output" $dev3 0.00KB $((maxvolsz)).00MB 124.00MB $pool2
	check list_table "$output" $dev4 0.00KB $((maxvolsz)).00MB 124.00MB $pool2
	check list_table "$output" $dev5 none none 124.00MB $pool3
	check list_table "$output" $dev6 none none 124.00MB $pool3
	check list_table "$output" $dev7 none none 124.00MB $pool3
	check list_table "$output" $dev8 none none 124.00MB $pool3
	output=`ssm list pool`
	check list_table "$output" $pool0 lvm 1 0.00KB $((size1)).00MB $((maxvolsz)).00MB
	check list_table "$output" $pool1 lvm 1 $((maxvolsz-size2)).00MB $((size2)).00MB $((maxvolsz)).00MB
	check list_table "$output" $pool2 lvm 2 0.00KB $((size3)).00MB $((maxvolsz*2)).00MB
	check list_table "$output" $pool3 lvm 4 $((maxvolsz*4-size4-size5-size6)).00MB $((size4+size5+size6)).00MB $((maxvolsz*4)).00MB

	# Check ssm vol after resize
	# xfs size cannot reduce
	if [ "$fs" != xfs ] ; then
		ssm -f resize $pool1/$vol2 -s ${size2r}M
	fi
	ssm resize -s ${size5r}m $pool3/$vol5

	output=`ssm list vol`
	# xfs has some strange used size, so we don't check it
	if [ "$fs" != xfs ] ; then
		check list_table "$output" $pool1/$vol2 $pool1 $size2r.00MB $fs $size2r none linear
		check list_table "$output" $pool3/$vol5 $pool3 $size5r.00MB $fs $size5r none linear
	else
		check list_table "$output" $pool3/$vol5 $pool3 $size5r.00MB $fs none none linear
	fi

	ssm snapshot $pool3/$vol4 -n snap1
	ssm snapshot $pool3/$vol4 -s ${size4s}m -n snap2

	output=`ssm list snap`
	check list_table "$output" $pool3/snap1 $vol4 $pool3 none none linear
	check list_table "$output" $pool3/snap2 $vol4 $pool3 $size4s.00MB none linear

	ssm -f remove -a

done

# Test with a mountpoint
for fs in $TEST_FS ; do
	ssm -f create -n $vol1 --fs $fs $dev1 $mnt1
	ssm create -n $vol2 -p $pool1 -s ${size2}M --fs $fs $dev2 $mnt2
	ssm create -n $vol3 -p $pool2 --fs $fs $dev3 $dev4 $mnt3
	ssm add -p $pool3 $dev{5,6,7,8}
	ssm create -p $pool3 -s ${size4}m -n $vol4 --fs $fs $mnt4
	ssm create -p $pool3 -s ${size5}m -n $vol5 --fs $fs $mnt5
	ssm create -p $pool3 -s ${size6}m -n $vol6 --fs $fs $mnt6

	# Check fs, vol, dev, pool, resized vol, and snapshot
	output=`ssm list fs`
	# xfs has some strange used size, so we don't check it
	if [ $fs == xfs ] ; then
		check list_table "$output" $pool0/$vol1 $pool0 $size1.00MB $fs none none linear $mnt1
		check list_table "$output" $pool1/$vol2 $pool1 $size2.00MB $fs none none linear $mnt2
		check list_table "$output" $pool2/$vol3 $pool2 $size3.00MB $fs none none linear $mnt3
		check list_table "$output" $pool3/$vol4 $pool3 $size4.00MB $fs none none linear $mnt4
		check list_table "$output" $pool3/$vol5 $pool3 $size5.00MB $fs none none linear $mnt5
		check list_table "$output" $pool3/$vol6 $pool3 $size6.00MB $fs none none linear $mnt6
	else
		check list_table "$output" $pool0/$vol1 $pool0 $size1.00MB $fs $size1.00MB none linear $mnt1
		check list_table "$output" $pool1/$vol2 $pool1 $size2.00MB $fs $size2.00MB none linear $mnt2
		check list_table "$output" $pool2/$vol3 $pool2 $size3.00MB $fs $size3.00MB none linear $mnt3
		check list_table "$output" $pool3/$vol4 $pool3 $size4.00MB $fs $size4.00MB none linear $mnt4
		check list_table "$output" $pool3/$vol5 $pool3 $size5.00MB $fs $size5.00MB none linear $mnt5
		check list_table "$output" $pool3/$vol6 $pool3 $size6.00MB $fs $size6.00MB none linear $mnt6
	fi

	output=`ssm list vol`
	# xfs has some strange used size, so we don't check it
	if [ $fs == xfs ] ; then
		check list_table "$output" $pool0/$vol1 $pool0 $size1.00MB $fs none none linear $mnt1
		check list_table "$output" $pool1/$vol2 $pool1 $size2.00MB $fs none none linear $mnt2
		check list_table "$output" $pool2/$vol3 $pool2 $size3.00MB $fs none none linear $mnt3
		check list_table "$output" $pool3/$vol4 $pool3 $size4.00MB $fs none none linear $mnt4
		check list_table "$output" $pool3/$vol5 $pool3 $size5.00MB $fs none none linear $mnt5
		check list_table "$output" $pool3/$vol6 $pool3 $size6.00MB $fs none none linear $mnt6
	else
		check list_table "$output" $pool0/$vol1 $pool0 $size1.00MB $fs $size1.00MB none linear $mnt1
		check list_table "$output" $pool1/$vol2 $pool1 $size2.00MB $fs $size2.00MB none linear $mnt2
		check list_table "$output" $pool2/$vol3 $pool2 $size3.00MB $fs $size3.00MB none linear $mnt3
		check list_table "$output" $pool3/$vol4 $pool3 $size4.00MB $fs $size4.00MB none linear $mnt4
		check list_table "$output" $pool3/$vol5 $pool3 $size5.00MB $fs $size5.00MB none linear $mnt5
		check list_table "$output" $pool3/$vol6 $pool3 $size6.00MB $fs $size6.00MB none linear $mnt6
	fi

	output=`ssm list dev`
	check list_table "$output" $dev1 0.00KB $((size1)).00MB 124.00MB $pool0
	check list_table "$output" $dev2 $((maxvolsz-size2)).00MB $((size2)).00MB 124.00MB $pool1
	check list_table "$output" $dev3 0.00KB $((maxvolsz)).00MB 124.00MB $pool2
	check list_table "$output" $dev4 0.00KB $((maxvolsz)).00MB 124.00MB $pool2
	check list_table "$output" $dev5 none none 124.00MB $pool3
	check list_table "$output" $dev6 none none 124.00MB $pool3
	check list_table "$output" $dev7 none none 124.00MB $pool3
	check list_table "$output" $dev8 none none 124.00MB $pool3
	output=`ssm list pool`
	check list_table "$output" $pool0 lvm 1 0.00KB $((size1)).00MB $((maxvolsz)).00MB
	check list_table "$output" $pool1 lvm 1 $((maxvolsz-size2)).00MB $((size2)).00MB $((maxvolsz)).00MB
	check list_table "$output" $pool2 lvm 2 0.00KB $((size3)).00MB $((maxvolsz*2)).00MB
	check list_table "$output" $pool3 lvm 4 $((maxvolsz*4-size4-size5-size6)).00MB $((size4+size5+size6)).00MB $((maxvolsz*4)).00MB

	# Check ssm vol after resize
	# xfs size cannot reduce
	if [ "$fs" != xfs ] ; then
		umount $mnt2
		ssm -f resize $pool1/$vol2 -s ${size2r}M
	fi
	ssm resize -s ${size5r}m $pool3/$vol5

	output=`ssm list vol`
	# xfs has some strange used size, so we don't check it
	if [ "$fs" != xfs ] ; then
		check list_table "$output" $pool1/$vol2 $pool1 $size2r.00MB $fs $size2r none linear
		check list_table "$output" $pool3/$vol5 $pool3 $size5r.00MB $fs $size5r none linear
	else
		check list_table "$output" $pool3/$vol5 $pool3 $size5r.00MB $fs none none linear
	fi

	ssm snapshot $pool3/$vol4 -n snap1
	ssm snapshot $pool3/$vol4 -s ${size4s}m -n snap2

	output=`ssm list snap`
	check list_table "$output" $pool3/snap1 $vol4 $pool3 none none linear
	check list_table "$output" $pool3/snap2 $vol4 $pool3 $size4s.00MB none linear

	for i in {1..6} ; do
		mntdir=`eval echo '$mnt'$i`
		umount $mntdir || true
	done

	ssm -f remove -a

done

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

# Check how ssm handles exported volume groups
# This was originally fixed by commit
# 7449db6 ("ssm: add a workaround for lvm and exported volumes")
ssm add $TEST_DEVS
vgexport $SSM_LVM_DEFAULT_POOL
ssm list
vgimport $SSM_LVM_DEFAULT_POOL
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Some situation should fail
not ssm list wrong_type
