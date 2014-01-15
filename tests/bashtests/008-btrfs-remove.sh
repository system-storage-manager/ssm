#!/bin/bash
#
# (C)2012 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
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

export test_name='008-btrfs-remove'
test_description='Exercise ssm remove command with btrfs backend'

. lib/test

DEV_COUNT=10
DEV_SIZE=300
TEST_MAX_SIZE=$(($DEV_COUNT*$DEV_SIZE))
aux prepare_devs $DEV_COUNT $DEV_SIZE
aux prepare_mnts 10
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='btrfs'
export SSM_BTRFS_DEFAULT_POOL=$vg1
export VOL_PREFIX="vol"
export SSM_NONINTERACTIVE='1'
vol1=${VOL_PREFIX}001
vol2=${VOL_PREFIX}002
vol3=${VOL_PREFIX}003

pool1=$vg2
pool2=$vg3

# Remove subvolume
ssm create $TEST_DEVS
ssm create --name $vol1
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL label $SSM_BTRFS_DEFAULT_POOL
ssm -f remove $SSM_BTRFS_DEFAULT_POOL
not check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL label $SSM_BTRFS_DEFAULT_POOL

# Remove volume group
ssm create $TEST_DEVS $mnt1
ssm create --name $vol1
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $DEV_COUNT
check btrfs_vol_field $mnt1 subvolume $vol1
ssm list
ssm -f remove $mnt1/$vol1
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $DEV_COUNT
not check btrfs_vol_field $mnt1 subvolume $vol1
umount $mnt1
ssm  -f remove $SSM_BTRFS_DEFAULT_POOL

# Remove unused devices from the pool
ssm create $dev1
btrfs filesystem show
ssm add $TEST_DEVS
btrfs filesystem show
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $DEV_COUNT
ssm -f remove $TEST_DEVS
btrfs filesystem show
ssm list
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count 1
ssm -f remove --all

# Remove multiple things
ssm add $dev1 $dev2 -p $pool1
ssm create --pool $pool2 $dev3 $dev4 $mnt1
ssm create --name $vol1 -p $pool2
ssm create --name $vol1 $dev5 $dev6 $mnt3
ssm create --name $vol2 $dev7 $dev8
ssm add $dev9

check btrfs_fs_field $pool1 dev_count 2
check btrfs_fs_field $pool2 dev_count 2
check btrfs_vol_field $mnt1 vol_count 1
check btrfs_vol_field $mnt1 subvolume $vol1
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count 5
check btrfs_vol_field $mnt3 vol_count 1
check btrfs_vol_field $mnt3 subvolume $vol2

ssm list

export SSM_DEFAULT_BACKEND='lvm'
ssm -f remove $pool1 ${pool2}:$vol1 $mnt3/$vol2 $dev9
export SSM_DEFAULT_BACKEND='btrfs'

not check btrfs_fs_field $pool1 label $pool1
not check btrfs_vol_field $mnt1 subvolume $vol1
not check btrfs_vol_field $mnt2 subvolume $vol2
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count 4
umount_all
ssm -f remove --all

# Remove all
ssm add $dev1 $dev2 -p $pool1
ssm create --pool $pool2 $dev3 $dev4 $mnt1
ssm create --name $vol1 -p $pool2
ssm create --name $vol1 $dev5 $dev6 $mnt3
ssm create --name $vol2 $dev7 $dev8
ssm create --name $vol3 $mnt2
ssm add $dev9

# We can not remove mounted fs
not ssm remove $pool2

# We can not remove mounted subvolume
not ssm remove ${SSM_BTRFS_DEFAULT_POOL}:${vol3}

check btrfs_fs_field $pool1 dev_count 2
check btrfs_fs_field $pool2 dev_count 2
check btrfs_vol_field $mnt1 vol_count 1
check btrfs_vol_field $mnt1 subvolume $vol1
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count 5
check btrfs_vol_field $mnt3 vol_count 2
check btrfs_vol_field $mnt3 subvolume $vol2
check btrfs_vol_field $mnt2 subvolume $vol3

# but we can force it
ssm -f remove ${SSM_BTRFS_DEFAULT_POOL}:${vol3}
not check btrfs_vol_field $mnt2 subvolume $vol3

umount_all
ssm -f remove --all

#Remove subvolume which is not mounted
ssm create $dev1 $dev2
ssm create --name $vol1
ssm create --name $vol2
ssm create --name ${vol1}/${vol3} $mnt1

check btrfs_vol_field $mnt1 vol_count 3
ssm remove ${SSM_BTRFS_DEFAULT_POOL}:$vol2
ssm list

check btrfs_vol_field $mnt1 vol_count 2
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count 2
check btrfs_vol_field $mnt1 subvolume $vol1
not check btrfs_vol_field $mnt1 subvolume $vol2
check btrfs_vol_field $mnt1 subvolume ${vol1}/${vol3}

umount_all
ssm -f remove --all

not check btrfs_fs_field $pool1 label $pool1
not check btrfs_fs_field $pool2 label $pool2
not check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL label $SSM_BTRFS_DEFAULT_POOL

ssm remove --help

# Some cases which should fail
not ssm remove
not ssm -f remove --all
