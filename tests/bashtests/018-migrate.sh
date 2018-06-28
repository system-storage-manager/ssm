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
DEV_COUNT=6
DEV_SIZE=200
aux prepare_devs $DEV_COUNT $DEV_SIZE
aux prepare_mnts 2
TEST_DEVS=$(cat DEVICES)
export LVOL_PREFIX="lvol"
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_BTRFS_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'

cleanup() {
	aux teardown
}

trap cleanup EXIT


function compare_hash()
{
	a=$(sha1sum $1 | cut -f1 -d' ')
	b=$(sha1sum $2 | cut -f1 -d' ')
	test "$a" = "$b"
}

function reset_devs()
{
	# try to clean anything that could linger on any test dev
	yes 'c' | ssm -f remove $SSM_LVM_DEFAULT_POOL || true
	for dev in $TEST_DEVS; do
		pvremove $dev || umount $dev || true
		pvcreate -f $dev
	done

}

function test_mount()
{
	mount $1 $mnt1
	umount $mnt1
}

mkfs.ext4 $dev1
mkfs.ext4 $dev2
ssm migrate $dev1 $dev3
! ssm migrate $dev2 $dev3
ssm -f migrate $dev2 $dev3

reset_devs

# BTRFS
export SSM_DEFAULT_BACKEND='btrfs'

ssm create $dev1
ssm -f migrate $dev1 $dev2
test_mount $dev2
ssm -f migrate $dev2 $dev3
test_mount $dev3
reset_devs

ssm create -p $vg1 $dev1 $dev2
ssm create -p $vg2 $dev3 $dev4 $dev5
ssm list
ssm -f migrate $dev2 $dev6
test_mount $dev1
test_mount $dev6

! ssm migrate $dev1 $dev3
ssm -f migrate $dev1 $dev3
test_mount $dev3
test_mount $dev4
reset_devs

ssm create $dev1 $dev2
ssm -f migrate $dev1 $dev3
test_mount $dev2
test_mount $dev3
reset_devs

reset_devs
ssm -b btrfs create $dev1 $dev2 $dev3
ssm list
ssm migrate $dev1 $dev2

export SSM_DEFAULT_BACKEND='lvm'

# LVM
! ssm migrate foobar1 foobar2
ssm -f migrate $dev1 $dev2
reset_devs

# should not pass because there is already a signature and -f is not used
! ssm migrate $dev3 $dev4
! ssm migrate $dev5 foobar2
! ssm migrate foobar2 $dev5
reset_devs

ssm create --size $DEV_SIZE $dev1 $dev2
ssm migrate $dev1 $dev2
ssm -f migrate $dev2 $dev3
reset_devs

ssm create --size $DEV_SIZE $dev1 $dev2 $dev3
! ssm -n migrate $dev3 $dev3
reset_devs

# should fail - the target is already mounted or used in another pool
mkfs.ext4 $dev1
mount $dev1 $mnt1
ssm create $dev2
! ssm migrate $dev2 $dev1
! ssm migrate $dev1 $dev2
ssm -f migrate $dev2 $dev1
reset_devs

exit 0