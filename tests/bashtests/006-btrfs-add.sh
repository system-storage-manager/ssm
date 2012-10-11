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

export test_name='006-btrfs-add'
test_description='Exercise ssm add with btrfs backend'

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

# Create default pool with all devices at once
ssm add $TEST_DEVS
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $DEV_COUNT
check list_table "$(ssm list pool)" $SSM_BTRFS_DEFAULT_POOL btrfs 10 none none none
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Specify backend
ssm -b btrfs add $TEST_DEVS
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $DEV_COUNT
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

export SSM_DEFAULT_BACKEND='lvm'
ssm --backend btrfs add $TEST_DEVS
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $DEV_COUNT
ssm -f remove $SSM_BTRFS_DEFAULT_POOL
export SSM_DEFAULT_BACKEND='btrfs'



ssm add $TEST_DEVS
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $DEV_COUNT
check list_table "$(ssm list pool)" $SSM_BTRFS_DEFAULT_POOL btrfs $DEV_COUNT none none none
ssm remove $dev1 $dev2 $dev3
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $(($DEV_COUNT-3))
ssm remove $dev4
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $(($DEV_COUNT-4))
check list_table "$(ssm list pool)" $SSM_BTRFS_DEFAULT_POOL btrfs $(($DEV_COUNT-4)) none none none
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Create default pool by adding devices one per a call
for i in $TEST_DEVS; do
        ssm add $i
done
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $DEV_COUNT
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Create different groups from different devices
ssm add $dev4
ssm add $dev1 $dev2 $dev3 -p $pool1
ssm add --pool $pool2 $dev7 $dev8
ssm add $dev5 $dev6
not ssm add $dev5 $dev6 $dev1 -p $pool1
ssm add $dev9 $dev1 -p $pool1
ssm add $dev10 -p $pool2
not ssm add $dev10 -p $pool1
not ssm add $dev10 $pool2 -p $pool1

check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count 3
check btrfs_fs_field $pool1 dev_count 4
check btrfs_fs_field $pool2 dev_count 3
ssm_output=$(ssm list pool)
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL btrfs 3 none none none
check list_table "$ssm_output" $pool1 btrfs 4 none none none
check list_table "$ssm_output" $pool2 btrfs 3 none none none

ssm -f remove --all

ssm add --help

# Some cases which should fail
not ssm _garbage_
not ssm add
not ssm add _garbage_
not ssm add $dev1 ${dev1}not_exist
not check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL label $SSM_BTRFS_DEFAULT_POOL
not ssm add _somepool
not ssm add $dev1 $dev2 $dev3 -p $pool1 _otherpool
