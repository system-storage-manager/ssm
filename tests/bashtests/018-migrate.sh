#!/bin/bash
#
# (C)2017 Red Hat, Inc., Jan Tulak <jtulak@redhat.com>
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

export test_name='018-migrate'
export test_description='Test the migrate command.'

. lib/test

export COLUMNS=1024
DEV_COUNT=8
DEV_SIZE=200
aux prepare_devs $DEV_COUNT $DEV_SIZE
aux prepare_mnts 2
TEST_DEVS=$(cat DEVICES)
export LVOL_PREFIX="lvol"
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_BTRFS_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'
lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002

cleanup() {
	aux teardown
}

trap cleanup EXIT

function compare_hash()
{
	a=$(cksum $1 | awk '{print $1 $2}')
	b=$(cksum $2 | awk '{print $1 $2}')
	test "$a" = "$b"
}

function test_volume()
{
	ssm check $1
	ssm mount $1 $mnt1
	umount $mnt1
}

# Test some nonsense
not ssm migrate foobar1 foobar2
not ssm migrate foobar1
not ssm migrate $dev1 $mnt1
not ssm migrate $mnt1 $dev1

# FIXME the commented-out tests are not used, because of how the testing filter
# interfere. When the SSM sandboxing is rewritten to work correctly, they should
# be uncommented.

# Migrate plain device
#dd if=/dev/urandom of=$dev1 bs=1k count=1
#dd if=/dev/urandom of=$dev2 bs=1k count=1
#sync
#ssm -f migrate $dev1 $dev2
#compare_hash $dev1 $dev2
#
# Migrate filesystem on plain device
#mkfs.ext4 -F $dev1
#mkfs.ext4 -F $dev2
#ssm migrate $dev1 $dev3
#not ssm migrate $dev2 $dev3
#ssm -f migrate $dev2 $dev3
#wipefs -a $dev1
#wipefs -a $dev2

# BTRFS
export SSM_DEFAULT_BACKEND='btrfs'

# Simple btrfs migrate to plain device
#ssm create $dev1
#check btrfs_devices $SSM_BTRFS_DEFAULT_POOL $dev1
#ssm migrate $dev1 $dev2
#check btrfs_devices $SSM_BTRFS_DEFAULT_POOL $dev2
#test_volume $SSM_BTRFS_DEFAULT_POOL
# Btrfs migrate on device with signature (ext4)
#not ssm migrate $dev2 $dev3
#ssm -f migrate $dev2 $dev3
#check btrfs_devices $SSM_BTRFS_DEFAULT_POOL $dev3
#test_volume $SSM_BTRFS_DEFAULT_POOL
#ssm -f remove --all

# Simple btrfs migrate of mounted fs
ssm create $dev1 $mnt1
check btrfs_devices $SSM_BTRFS_DEFAULT_POOL $dev1
not ssm migrate $mnt1 $dev2
ssm migrate $dev1 $dev2
check btrfs_devices $SSM_BTRFS_DEFAULT_POOL $dev2
umount $mnt1
ssm check $SSM_BTRFS_DEFAULT_POOL
ssm -f remove --all

# Migrate device from multi-device btrfs
ssm create -p $vg1 $dev1 $dev2
ssm create -p $vg2 $dev3 $dev4 $dev5
ssm -f migrate $dev2 $dev6
check btrfs_devices $vg1 $dev1 $dev6
check btrfs_devices $vg2 $dev3 $dev4 $dev5
test_volume $vg1
test_volume $vg2

# Migrate to a device already used in btrfs pool
not ssm migrate $dev1 $dev3
ssm -f migrate $dev1 $dev3
check btrfs_devices $vg1 $dev3 $dev6
check btrfs_devices $vg2 $dev4 $dev5
test_volume $vg1
test_volume $vg2
ssm -f remove --all

# Do not allow migrate between devices within a single pool in btrfs
ssm create $dev1 $dev2 $dev3 $dev4
not ssm migrate $dev1 $dev2
not ssm -f migrate $dev1 $dev2
check btrfs_devices $SSM_BTRFS_DEFAULT_POOL $dev1 $dev2 $dev3 $dev4
ssm -f remove --all

# migrate plain device to a device in btrfs pool - not used
#ssm create -p $vg1 $dev1 $dev2 $dev3
#mkfs.ext4 -F $dev4
#not ssm migrate $dev4 $dev3
#ssm -f migrate $dev4 $dev3
#check btrfs_devices $vg1 $dev1 $dev2
#test_volume $vg1
#fsck.ext4 -fn $dev3

# migrate plain device to a device in btrfs pool - used completely
#ssm -f add -p $vg1 $dev3
#ssm mount $vg1 $mnt1
# Fill it up as much as we can, we do not care if dd fails
#! dd if=/dev/zero of=$mnt1/file bs=1M
#sync
#umount $mnt1
#not ssm migrate $dev4 $dev1
#not ssm -f migrate $dev4 $dev1
#check btrfs_devices $vg1 $dev1 $dev2 $dev3
#test_volume $vg1
#ssm -f remove --all

export SSM_DEFAULT_BACKEND='lvm'

# LVM

# Simple lvm migrate to plain device
#ssm create --fs ext4 $dev1
#check vg_devices $SSM_LVM_DEFAULT_POOL $dev1
#ssm migrate $dev1 $dev2
#check vg_devices $SSM_LVM_DEFAULT_POOL $dev1 $dev2
#test_volume $SSM_LVM_DEFAULT_POOL/$lvol1
#mkfs.ext4 -F $dev3
# lvm migrate to a device with signature (ext4)
#not ssm migrate $dev2 $dev3
#ssm -f migrate $dev2 $dev3
#check vg_devices $SSM_LVM_DEFAULT_POOL $dev1 $dev2 $dev3
#test_volume $SSM_LVM_DEFAULT_POOL/$lvol1
#ssm -f remove --all

# Simple lvm migrate without pv being used
ssm add $dev1 $dev2 $dev3
ssm migrate $dev1 $dev5
check vg_devices $SSM_LVM_DEFAULT_POOL $dev1 $dev2 $dev3 $dev5
# Migrate to a device in the same pool
ssm migrate $dev2 $dev3
# Try to migrate with source/target being the same device
not ssm migrate $dev3 $dev3
ssm -f remove --all

# Migrate used device to free that's already in the pool
ssm create $dev1 $dev2
ssm -f add $dev3 $dev4
ssm migrate $dev1 $dev3
check vg_devices $SSM_LVM_DEFAULT_POOL $dev1 $dev2 $dev3 $dev4
ssm -f remove --all

# All devices are used
ssm create $dev1
ssm create $dev2
not ssm migrate $dev1 $dev2
# Only specified devices are used
ssm add $dev3
not ssm migrate $dev1 $dev2
ssm migrate $dev2 $dev3
check vg_devices $SSM_LVM_DEFAULT_POOL $dev1 $dev2 $dev3
ssm -f remove --all

# Simple lvm migrate of mounted fs
ssm create --fs ext4 $dev1 $mnt1
wipefs -a $dev2
not ssm migrate $mnt1 $dev2
ssm migrate $dev1 $dev2
check vg_devices $SSM_LVM_DEFAULT_POOL $dev1 $dev2
umount $mnt1
ssm check $SSM_LVM_DEFAULT_POOL/$lvol1
ssm -f remove --all

# Migrate to a device from different pool
ssm create -p $vg1 $dev1 $dev2 $dev3
ssm add -p $vg1 $dev7
ssm create -p $vg2 $dev4 $dev5 $dev6
ssm add -p $vg2 $dev8
not ssm migrate $dev1 $dev8
ssm -f migrate $dev1 $dev8
check vg_devices $vg1 $dev1 $dev8 $dev2 $dev3 $dev7
check vg_devices $vg2 $dev4 $dev5 $dev6
# Migrate device that is not used
not ssm migrate $dev4 $dev7
ssm -f migrate $dev4 $dev7
check vg_devices $vg1 $dev1 $dev8 $dev2 $dev3
check vg_devices $vg2 $dev4 $dev5 $dev6 $dev7
# Migrate device that is used
not ssm add -p $vg1 $dev1 # We're not removing the pv after migrate
not ssm migrate $dev5 $dev1
ssm -f migrate $dev5 $dev1
ssm -f remove --all

# Migrate plain device to a device in lvm
ssm create $dev1 $dev2 $dev3
ssm add -p $SSM_LVM_DEFAULT_POOL $dev4 $dev5
# target device used
not ssm migrate $dev6 $dev3
not ssm -f migrate $dev6 $dev3
# target device not used
not ssm migrate $dev6 $dev4
ssm -f migrate $dev6 $dev4
check vg_devices $SSM_LVM_DEFAULT_POOL $dev1 $dev2 $dev3 $dev5
# Migrate plain device with a file system
#mkfs.ext4 -F $dev4
# target device used
#not ssm migrate $dev4 $dev1
#not ssm -f migrate $dev4 $dev1
# target not used
#not ssm migrate $dev4 $dev5
#ssm -f migrate $dev4 $dev5
#check vg_devices $SSM_LVM_DEFAULT_POOL $dev1 $dev2 $dev3
#fsck.ext4 -fn $dev5
#test_volume $dev5
ssm -f remove --all

# migrate from btrfs pool to lvm
wipefs -a $dev4 $dev5
ssm -b btrfs create -p $vg1 $dev1 $dev2 $dev3
ssm -b lvm create --fs ext4 -p $vg2 $dev4 $dev5
not ssm migrate $dev5 $dev3
ssm -f migrate $dev5 $dev3
check btrfs_devices $vg1 $dev1 $dev2
check vg_devices $vg2 $dev4 $dev5 $dev3
test_volume $vg1
test_volume $vg2/$lvol1
ssm -f remove --all

# migrate from lvm to btrfs pool
ssm -b btrfs create -p $vg1 $dev1 $dev2 $dev3
ssm -b lvm create --fs ext4 -p $vg2 $dev4 $dev5
ssm add -p $vg2 $dev6
not ssm migrate $dev3 $dev6
ssm -f migrate $dev3 $dev6
check btrfs_devices $vg1 $dev1 $dev2 $dev6
check vg_devices $vg2 $dev4 $dev5
test_volume $vg1
test_volume $vg2/$lvol1
ssm -f remove --all

# CRYPT

# cryptsetup will ask for password. If luks extension is used
# it will ask when creating header and then when opening the device
pass() {
	echo -e "${passwd}\n${passwd}"
}

export SSM_DEFAULT_BACKEND='crypt'
export SSM_CRYPT_DEFAULT_POOL=$vg3
export CRYPT_VOL_PREFIX="${SSM_PREFIX_FILTER}enc"
export SSM_CRYPT_DEFAULT_VOL_PREFIX=$CRYPT_VOL_PREFIX
crypt_vol1=${CRYPT_VOL_PREFIX}001

passwd="cai0ohMo8M"
pass | ssm create $dev1
check crypt_vol_field $crypt_vol1 type LUKS1
check crypt_vol_field $crypt_vol1 device $dev1
check list_table "$(ssm list vol)" $crypt_vol1 $SSM_CRYPT_DEFAULT_POOL none crypt

# Migrate in crypt is not currently supported so this whould both fail
not ssm migrate $dev1 $dev2
not ssm -f migrate $dev1 $dev2

# Device can't be simply removed from the crypt backend so this should fail
not ssm migrate $dev2 $dev1
not ssm -f migrate $dev2 $dev1

exit 0
