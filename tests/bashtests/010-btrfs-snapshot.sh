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

export test_name='010-btrfs-snapshot'
test_description='Exercise ssm snapshot command with btrfs'

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

snap1="snap1"
snap2="snap2"
snap3="snap3"
snap4="snap4"
snap5="snap5"
snap6="snap6"


# Create volume with all devices at once
ssm create $TEST_DEVS $mnt1

# Take a snapshot with the default params
export SSM_DEFAULT_BACKEND='lvm'
ssm snapshot $mnt1
check btrfs_vol_field $mnt1 vol_count 1
check list_table "$(ssm list snap)" $SSM_BTRFS_DEFAULT_POOL:snap-....-..-..-....... $SSM_BTRFS_DEFAULT_POOL none btrfs $mnt1/snap-....-..-..-.......
export SSM_DEFAULT_BACKEND='btrfs'

umount $mnt1
# Remove entire pool
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Create volume with all devices at once
ssm create $TEST_DEVS

# Take a snapshot with the default params
ssm snapshot $SSM_BTRFS_DEFAULT_POOL
mount LABEL=$SSM_BTRFS_DEFAULT_POOL $mnt1
check btrfs_vol_field $mnt1 vol_count 1
umount $mnt1

# Remove entire pool
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Create volume with all devices at once
ssm create $TEST_DEVS

# Take a snapshot with defined name
ssm snapshot --name $snap1 $SSM_BTRFS_DEFAULT_POOL
ssm snapshot --name $snap2 $SSM_BTRFS_DEFAULT_POOL
ssm snapshot --name $snap3 $SSM_BTRFS_DEFAULT_POOL
mount LABEL=$SSM_BTRFS_DEFAULT_POOL $mnt1
check btrfs_vol_field $mnt1 vol_count 3
check btrfs_vol_field $mnt1 subvolume $snap1
check btrfs_vol_field $mnt1 subvolume $snap2
check btrfs_vol_field $mnt1 subvolume $snap3
ssm_output=$(ssm list vol)
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1
not check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap1 $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1/$snap1
not check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap2 $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1/$snap2
not check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap3 $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1/$snap3
ssm_output=$(ssm list snap)
not check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL $SSM_BTRFS_DEFAULT_POOL none btrfs btrfs $mnt1
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap1 $SSM_BTRFS_DEFAULT_POOL none btrfs $mnt1/$snap1
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap2 $SSM_BTRFS_DEFAULT_POOL none btrfs $mnt1/$snap2
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap3 $SSM_BTRFS_DEFAULT_POOL none btrfs $mnt1/$snap3

# Remove the snapshot volumes
ssm -f remove $SSM_BTRFS_DEFAULT_POOL:$snap1 $SSM_BTRFS_DEFAULT_POOL:$snap2 $SSM_BTRFS_DEFAULT_POOL:$snap3
not check btrfs_vol_field $mnt1 subvolume $snap1
not check btrfs_vol_field $mnt1 subvolume $snap2
not check btrfs_vol_field $mnt1 subvolume $snap3

# Take a snapshot with defined name when volume is mounted
ssm snapshot --name $snap1 $SSM_BTRFS_DEFAULT_POOL
ssm snapshot --name $snap2 $mnt1
ssm snapshot --name $snap3 $SSM_BTRFS_DEFAULT_POOL

ssm snapshot --name $snap4 $mnt1/$snap3
ssm snapshot --name $snap3/$snap4/$snap5 $mnt1
check btrfs_vol_field $mnt1 vol_count 5
check btrfs_vol_field $mnt1 subvolume $snap1
check btrfs_vol_field $mnt1 subvolume $snap2
check btrfs_vol_field $mnt1 subvolume $snap3
check btrfs_vol_field $mnt1 subvolume $snap3/$snap4
check btrfs_vol_field $mnt1 subvolume $snap3/$snap4/$snap5
ssm_output=$(ssm list vol)
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1
ssm_output=$(ssm list snap)
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap1 $SSM_BTRFS_DEFAULT_POOL none btrfs $mnt1/$snap1
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap2 $SSM_BTRFS_DEFAULT_POOL none btrfs $mnt1/$snap2
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap3 $SSM_BTRFS_DEFAULT_POOL none btrfs $mnt1/$snap3
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap3/$snap4 $SSM_BTRFS_DEFAULT_POOL none btrfs $mnt1/$snap3/$snap4
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$snap3/$snap4/$snap5 $SSM_BTRFS_DEFAULT_POOL none btrfs $mnt1/$snap3/$snap4/$snap5

umount_all

ssm -f remove --all
ssm snapshot --help

# Some cases which should fail
not ssm snapshot
ssm create $TEST_DEVS
not ssm snapshot $SSM_BTRFS_DEFAULT_POOL/$lvol1

ssm -f remove --all
