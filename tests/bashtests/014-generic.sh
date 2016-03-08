#!/bin/bash
#
# (C)2014 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
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

export test_name='014-generic'
export test_description='Various simple test cases'

. lib/test

export COLUMNS=1024
DEV_COUNT=10
aux prepare_devs $DEV_COUNT 10
aux prepare_mnts 2
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export LVOL_PREFIX="lvol"
export SSM_NONINTERACTIVE='1'
lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002

# e5057e5be14226fd65f8f43bbc08f989b3bf2c58 Fix traceback when calling 'ssm list' with empty dm tables
ssm list
dmsetup create $vg2 --notable
ssm list
dmsetup remove $vg2

# test ssm create with mount
ssm create --fs ext3 $dev1 $mnt1
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol1 $mnt1
ssm -f create --fs ext3 $dev2 $mnt2
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol2 $mnt2
umount $mnt1 $mnt2
ssm  -f remove --all

# test ssm create with mount and non existent directory
ssm create --fs ext3 $dev1 ${mnt1}a
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol1 ${mnt1}a
ssm -f create --fs ext3 $dev2 ${mnt2}b
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol2 ${mnt2}b
umount ${mnt1}a ${mnt2}b

# test ssm mount command
ssm mount $SSM_LVM_DEFAULT_POOL/$lvol1 $mnt1
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol1 $mnt1
ssm -f mount $SSM_LVM_DEFAULT_POOL/$lvol2 $mnt2
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol2 $mnt2
umount $mnt1 $mnt2

# test ssm mount command with non existent directory
ssm mount $SSM_LVM_DEFAULT_POOL/$lvol1 ${mnt1}c
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol1 ${mnt1}c
ssm -f mount $SSM_LVM_DEFAULT_POOL/$lvol2 ${mnt2}d
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol2 ${mnt2}d
umount ${mnt1}c ${mnt2}d

# test ssm mount command with options
ssm mount -o ro,data=journal $SSM_LVM_DEFAULT_POOL/$lvol1 ${mnt1}
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol1 ${mnt1} "ro,data=journal"
umount ${mnt1}
ssm mount -o ro,data=journal $SSM_LVM_DEFAULT_POOL/$lvol2 ${mnt2}e
check mountpoint $SSM_LVM_DEFAULT_POOL-$lvol2 ${mnt2}e "ro,data=journal"
umount ${mnt2}e

ssm  -f remove --all
