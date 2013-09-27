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

export test_name='007-btrfs-create'
test_description='Exercise ssm create command with btrfs backend'

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

# Create volume with all devices at once
ssm create $TEST_DEVS $mnt1
not ssm create $TEST_DEVS -p $pool1

#Create subvolume with nonexisting path
not ssm create -n $vol1/$vol2

check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count $DEV_COUNT
check list_table "$(ssm list vol)" $SSM_BTRFS_DEFAULT_POOL $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1
ssm create
ssm create --name $vol1
ssm create --name $vol1/$vol2
check btrfs_vol_field $mnt1 vol_count 3
check btrfs_vol_field $mnt1 subvolume $vol1
check btrfs_vol_field $mnt1 subvolume $vol1/$vol2
ssm_output=$(ssm list vol)
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:....-..-..-....... $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1/....-..-..-.......
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$vol1 $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1/$vol1
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$vol1/$vol2 $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1/$vol1/$vol2
umount $mnt1
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Create volume with just one device
ssm create $dev1
not ssm create $dev1 -p $pool1
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Specify backend
ssm --backend btrfs create $dev1
not ssm create $dev1 -p $pool1
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

export SSM_DEFAULT_BACKEND='lvm'
ssm -b btrfs create $dev1
not ssm create $dev1 -p $pool1
ssm -f remove $SSM_BTRFS_DEFAULT_POOL
export SSM_DEFAULT_BACKEND='btrfs'

# Create raid 0 volume with just one device
ssm create -r 0 $dev1 $dev2 $dev3 $dev4
not ssm create $dev1 -p $pool1
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Create raid 1 volume with just one device
ssm create -r 1 $dev1 $dev2 $dev3 $dev4
not ssm create $dev1 -p $pool1
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Create raid 10 volume with just one device
ssm create -r 10 $dev1 $dev2 $dev3 $dev4
ssm check $SSM_BTRFS_DEFAULT_POOL
not ssm create $dev1 -p $pool1
ssm -f remove $SSM_BTRFS_DEFAULT_POOL

# Create several volumes with several pools
ssm create $dev1 $mnt1
ssm create --name $vol1
check btrfs_fs_field $SSM_BTRFS_DEFAULT_POOL dev_count 1
check btrfs_vol_field $mnt1 subvolume $vol1

ssm create --pool $pool1 $dev2 $dev3 $mnt2
ssm create --name $vol2 --pool $pool1
# Also try to mount the subvolume somewhere else
ssm create --name $vol3 --pool $pool1 $mnt3
check btrfs_fs_field $pool1 dev_count 2
check btrfs_vol_field $mnt2 subvolume $vol2
check btrfs_vol_field $mnt1 vol_count 1
check btrfs_vol_field $mnt2 vol_count 2
not check btrfs_vol_field $mnt2 subvolume $vol1

ssm create --name $vol1 --pool $pool2 $dev4 $dev5 $dev6
check btrfs_fs_field $pool2 dev_count 3
ssm create --name $vol2 --pool $pool2 $dev7 $dev8
ssm create --name $vol1 --pool $pool2 $dev9 $mnt4
check btrfs_fs_field $pool2 dev_count 6
check btrfs_vol_field $mnt2 subvolume $vol2
check btrfs_vol_field $mnt4 subvolume $vol1
check btrfs_vol_field $mnt2 vol_count 2
check btrfs_vol_field $mnt4 vol_count 2
not check btrfs_vol_field $mnt2 subvolume $vol1
ssm_output=$(ssm list vol)
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$vol1 $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1/$vol1
check list_table "$ssm_output" $pool1 $pool1 none btrfs none none btrfs $mnt2
check list_table "$ssm_output" $pool1:$vol2 $pool1 none btrfs none none btrfs $mnt2/$vol2
check list_table "$ssm_output" $pool1:$vol3 $pool1 none btrfs none none btrfs $mnt3
check list_table "$ssm_output" $pool2 $pool2 none btrfs none none btrfs
check list_table "$ssm_output" $pool2:$vol1 $pool2 none btrfs none none btrfs $mnt4
check list_table "$ssm_output" $pool2:$vol2 $pool2 none btrfs none none btrfs
ssm_output=$(ssm list pool)
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL btrfs 1 none none none
check list_table "$ssm_output" $pool1 btrfs 2 none none none
check list_table "$ssm_output" $pool2 btrfs 6 none none none

umount_all
ssm -f remove $SSM_BTRFS_DEFAULT_POOL $pool1 $pool2

# Create root mounted soubvolume and then another subvolume mounted at different mount point
ssm create $TEST_DEVS $mnt1
ssm create --name $vol1 $mnt2
ssm create --name $vol1/$vol2 $mnt3

# Create subvolume with already existing path
not ssm create --name $vol1/$vol2
not ssm create --name $vol1 $mnt3
ssm_output=$(ssm list vol)
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt1
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$vol1 $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt2
check list_table "$ssm_output" $SSM_BTRFS_DEFAULT_POOL:$vol1/$vol2 $SSM_BTRFS_DEFAULT_POOL none btrfs none none btrfs $mnt3
umount_all
ssm  -f remove $SSM_BTRFS_DEFAULT_POOL

ssm create --help

# Some cases which should fail
not ssm create
not ssm  -f remove --all
