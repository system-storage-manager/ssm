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

export test_name='001-add'
export test_description='Exercise ssm add'

. lib/test

export COLUMNS=1024
DEV_COUNT=10
aux prepare_devs $DEV_COUNT 10
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'

pool1=$vg2
pool2=$vg3

ssm list dev

# Create default pool with all devices at once
ssm add $TEST_DEVS
check vg_field $SSM_LVM_DEFAULT_POOL pv_count $DEV_COUNT
ssm_output=$(ssm list dev)
check list_table "$ssm_output" $dev1 none none 8.00MB $vg1
check list_table "$ssm_output" $dev2 none none 8.00MB $vg1
check list_table "$ssm_output" $dev3 none none 8.00MB $vg1
check list_table "$ssm_output" $dev4 none none 8.00MB $vg1
check list_table "$ssm_output" $dev5 none none 8.00MB $vg1
check list_table "$ssm_output" $dev6 none none 8.00MB $vg1
check list_table "$ssm_output" $dev7 none none 8.00MB $vg1
check list_table "$ssm_output" $dev8 none none 8.00MB $vg1
check list_table "$ssm_output" $dev9 none none 8.00MB $vg1
check list_table "$ssm_output" $dev10 none none 8.00MB $vg1
ssm -f remove $SSM_LVM_DEFAULT_POOL


# Specify backend
ssm -b lvm add $TEST_DEVS
check vg_field $SSM_LVM_DEFAULT_POOL pv_count $DEV_COUNT
ssm -f remove $SSM_LVM_DEFAULT_POOL

export SSM_DEFAULT_BACKEND='btrfs'
ssm --backend lvm add $TEST_DEVS
check vg_field $SSM_LVM_DEFAULT_POOL pv_count $DEV_COUNT
ssm -f remove $SSM_LVM_DEFAULT_POOL
export SSM_DEFAULT_BACKEND='lvm'

ssm add $TEST_DEVS
check vg_field $SSM_LVM_DEFAULT_POOL pv_count $DEV_COUNT
ssm remove $dev1 $dev2 $dev3
check vg_field $SSM_LVM_DEFAULT_POOL pv_count $(($DEV_COUNT-3))
ssm_output=$(ssm list dev)
check list_table "$ssm_output" $dev1 9.90MB
check list_table "$ssm_output" $dev2 9.90MB
check list_table "$ssm_output" $dev3 9.90MB
check list_table "$ssm_output" $dev4 none none 8.00MB $vg1
check list_table "$ssm_output" $dev5 none none 8.00MB $vg1
check list_table "$ssm_output" $dev6 none none 8.00MB $vg1
check list_table "$ssm_output" $dev7 none none 8.00MB $vg1
check list_table "$ssm_output" $dev8 none none 8.00MB $vg1
check list_table "$ssm_output" $dev9 none none 8.00MB $vg1
check list_table "$ssm_output" $dev10 none none 8.00MB $vg1
ssm remove $dev4
check vg_field $SSM_LVM_DEFAULT_POOL pv_count $(($DEV_COUNT-4))
ssm_output=$(ssm list dev)
check list_table "$ssm_output" $dev1 9.90MB
check list_table "$ssm_output" $dev2 9.90MB
check list_table "$ssm_output" $dev3 9.90MB
check list_table "$ssm_output" $dev4 9.90MB
check list_table "$ssm_output" $dev5 none none 8.00MB $vg1
check list_table "$ssm_output" $dev6 none none 8.00MB $vg1
check list_table "$ssm_output" $dev7 none none 8.00MB $vg1
check list_table "$ssm_output" $dev8 none none 8.00MB $vg1
check list_table "$ssm_output" $dev9 none none 8.00MB $vg1
check list_table "$ssm_output" $dev10 none none 8.00MB $vg1
ssm -f remove $SSM_LVM_DEFAULT_POOL

# Create default pool by adding devices one per a call
for i in $TEST_DEVS; do
        ssm add $i
done
check vg_field $SSM_LVM_DEFAULT_POOL pv_count $DEV_COUNT
ssm -f remove $SSM_LVM_DEFAULT_POOL

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
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 3
check vg_field $pool1 pv_count 4
check vg_field $pool2 pv_count 3
ssm_output=$(ssm list dev)
check list_table "$ssm_output" $dev1 none none 8.00MB $vg2
check list_table "$ssm_output" $dev2 none none 8.00MB $vg2
check list_table "$ssm_output" $dev3 none none 8.00MB $vg2
check list_table "$ssm_output" $dev4 none none 8.00MB $vg1
check list_table "$ssm_output" $dev5 none none 8.00MB $vg1
check list_table "$ssm_output" $dev6 none none 8.00MB $vg1
check list_table "$ssm_output" $dev7 none none 8.00MB $vg3
check list_table "$ssm_output" $dev8 none none 8.00MB $vg3
check list_table "$ssm_output" $dev9 none none 8.00MB $vg2
check list_table "$ssm_output" $dev10 none none 8.00MB $vg3
ssm -f remove --all

ssm add $dev1 $dev2
ssm -f remove $SSM_LVM_DEFAULT_POOL
# Try to use device with existing file system
mkfs.ext3 $dev1
# Default answer is No
not ssm add $dev1
not check vg_field $SSM_LVM_DEFAULT_POOL pv_count 1
ssm add $dev1 $dev2
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 1
ssm -f remove --all

# Try to use device with existing file system with force
mkfs.ext3 $dev1
# Default answer is No
ssm -f add $dev1
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 1
ssm -f remove $SSM_LVM_DEFAULT_POOL
mkfs.ext3 $dev1
ssm -f add $dev1 $dev2
check vg_field $SSM_LVM_DEFAULT_POOL pv_count 2
ssm -f remove --all

ssm add --help

# Some cases which should fail
not ssm _garbage_
not ssm add
not ssm add $dev1 ${dev1}not_exist
not check vg_field $SSM_LVM_DEFAULT_POOL vg_name $SSM_LVM_DEFAULT_POOL
not ssm add _somepool
not ssm add $dev1 $dev2 $dev3 -p $pool1 _otherpool
