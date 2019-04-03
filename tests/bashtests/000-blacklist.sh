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

export test_name='000-blacklist'
export test_description='Test if blacklisting of devices works'

. lib/test

export COLUMNS=1024
DEV_COUNT=8
DEV_SIZE=200
aux prepare_devs $DEV_COUNT $DEV_SIZE
aux prepare_mnts 2
TEST_DEVS=$(cat DEVICES)
export LVOL_PREFIX="${SSM_PREFIX_FILTER}lvol"
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_BTRFS_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'
export SSM_BLACKLISTED_ITEMS=''
DEV="/dev/mapper"
lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002
lvol3=${LVOL_PREFIX}003

export TVOL_PREFIX="tvol"
tvol1=${TVOL_PREFIX}001
tpool1=${SSM_LVM_DEFAULT_POOL}_thin001
snap1="${SSM_PREFIX_FILTER}snap1"
snap2="${SSM_PREFIX_FILTER}snap2"

export SSM_BTRFS_DEFAULT_POOL=$vg1

cleanup() {
	aux teardown
}

trap cleanup EXIT

passwd="cai0ohMo8M"
pass() {
	echo -e "${passwd}\n${passwd}"
}

# print all the lines in $1 except exact match of $2
function remove_item () {
	lines="$1"
	item="$2"

	echo "$lines" | grep -v "^$item$"
}

# remove $1 from SSM_BLACKLISTED_ITEMS
function remove_from_blacklist () {
	item="$1"
	SSM_BLACKLISTED_ITEMS=$(remove_item "$SSM_BLACKLISTED_ITEMS" "$item")
}

# Fill blacklist with what ssm exports, optionally removing all items
# provided as arguments to this function.
# Usage:
# fill_blacklist [allowed1 [allowed2 [...]]]
function fill_blacklist () {
	SSM_BLACKLISTED_ITEMS=$(ssm list export-paths)
	while test ${#} -gt 0
	do
		remove_from_blacklist $1
		shift
	done
}

function empty_blacklist () {
	SSM_BLACKLISTED_ITEMS=''
}

# print dm dev for given vg/lv as $1
function get_dm_dev_lvm() {
	lvs --noheadings -o lv_dm_path "$1"
}

# print dm dev for any ssm test dev with filter
function get_dm_dev() {
	kname=$(lsblk "$1" -n -o KNAME)
	echo "/dev/$kname"
}


#if [ 0 -eq 1 ]; then

#bash
#exit 0

# LVM section
# A short test using default pool name
ssm add $dev1 $dev2
fill_blacklist
not ssm remove $dev2
empty_blacklist
ssm remove $dev2
ssm -f remove -a

# now make two pools so we can test only part of the storage items hidden
ssm create -p $vg1 -n $lvol1 --fstype ext4 --size $DEV_SIZE $dev1 $dev2 $dev3
ssm create -p $vg2 -n $lvol1 --fstype ext4 --size $DEV_SIZE $dev4 $dev5
ssm create -p $vg2 -n $lvol2

fill_blacklist

# no normal output - everything is blocked
test "$(ssm list)" = ""

# list all the blocked devices as we find them
out=$(ssm -v list)
test $(echo "$out" | grep "Item .* blacklisted" | wc -l ) != "0"

not ssm add -p $vg1 $dev6

# remove some items from the blacklist
# now ssm should see $vg2 and all its devices and volumes
remove_from_blacklist $vg2
remove_from_blacklist $dev4
remove_from_blacklist $dev5
remove_from_blacklist $DM_DEV_DIR/mapper/$vg2-$lvol1
remove_from_blacklist $DM_DEV_DIR/mapper/$vg2-$lvol2


out=$(ssm list dev)
check list_table "$out" $dev4
check list_table "$out" $dev5
not check list_table "$out" $dev1
not check list_table "$out" $dev2
not check list_table "$out" $dev3

out=$(ssm list pool)
check list_table "$out" $vg2
not check list_table "$out" $vg1

out=$(ssm list vol)
check list_table "$out" $vg2/$lvol1
check list_table "$out" $vg2/$lvol2
not check list_table "$out" $vg1/$lvol1

# We can't add to a blacklisted pool, but we can to an allowed one
not ssm add -p $vg1 $dev6
ssm add -p $vg2 $dev6

out=$(ssm list dev)
check list_table "$out" $dev6

# we can create a volume in an allowed pool
ssm create -p $vg2 -n $lvol3
out=$(ssm list vol)
check list_table "$out" $vg2/$lvol3

# but we can not create a volume in a blacklisted pool
not ssm create -p $vg1 -n $lvol2
out=$(ssm list vol)
not check list_table "$out" $vg1/$lvol2

ssm -f remove $vg2/$lvol2
ssm -f remove --all

out=$(ssm list pool | wc -l)
test "$out" = "0"

out=$(ssm list vol | wc -l)
test "$out" = "0"

out=$(ssm list dev)
check list_table "$out" $dev4
not check list_table "$out" $dev1

empty_blacklist

out=$(ssm list dev)
check list_table "$out" $dev1
check list_table "$out" $dev4

# when a PV is allowed, but it's VG is not, hide the PV as well
fill_blacklist $dev1
out=$(ssm list dev)
not check list_table "$out" $dev1
empty_blacklist

ssm -f remove --all
for dev in $dev1 $dev2 $dev3 $dev4 $dev5 $dev6; do
	wipefs -a  $dev
done

# Some basic thin tests

virtualsize=$(($DEV_SIZE*10))
ssm create --virtual-size ${virtualsize}M $dev1 $dev2 $dev3
virtualsize=$(align_size_up $virtualsize)
ssm snapshot --name $snap1 $SSM_LVM_DEFAULT_POOL/$tvol1

fill_blacklist
test "$(ssm list)" = ""

not ssm snapshot --name $snap2 $DM_DEV_DIR/$SSM_LVM_DEFAULT_POOL/$tvol1

empty_blacklist

ssm -f remove --all

# SNAPSHOTS
# Create volume with all devices at once
size=$(($DEV_SIZE*4))
ssm create --size ${size}M -p $vg1 -n $lvol1 $TEST_DEVS

# try to make a snapshot at a blacklisted pool
fill_blacklist
test "$(ssm list)" = ""
snap_size=$(($size/5))
not ssm snapshot --name $snap1 $vg1/$lvol1
not check lv_field $vg1/$snap1 lv_size ${snap_size}.00m

# now really make a snapshot and blacklist it too
empty_blacklist
ssm snapshot --name $snap1 $vg1/$lvol1
check lv_field $vg1/$snap1 lv_size ${snap_size}.00m
fill_blacklist
test "$(ssm list)" = ""

# Try to remove the snapshot volume
not ssm -f remove $vg1/$snap1

empty_blacklist
ssm  -f remove --all


# CRYPT
# cryptsetup will ask for password. If luks extension is used
# it will ask when creating header and then when opening the device


pass | ssm create -e luks -p $vg1 -n $lvol1 $dev1 --fstype ext4
fill_blacklist $dev2
pass | ssm create -e luks -p $vg2 -n $lvol2 $dev2 --fstype ext4

out=$(ssm list dev)
check list_table "$out" $dev2
not check list_table "$out" $dev1
out=$(ssm list vol)
check list_table "$out" $vg2/$lvol2
not check list_table "$out" $vg1/$lvol1


empty_blacklist

ssm -f remove $DEV/$lvol1
ssm -f remove $DEV/$lvol2
ssm -f remove --all

export SSM_DEFAULT_BACKEND='crypt'
export SSM_CRYPT_DEFAULT_POOL=$vg3
export CRYPT_VOL_PREFIX="${SSM_PREFIX_FILTER}enc"
export SSM_CRYPT_DEFAULT_VOL_PREFIX=$CRYPT_VOL_PREFIX
crypt_vol1=${CRYPT_VOL_PREFIX}001
crypt_vol2=${CRYPT_VOL_PREFIX}002


pass | ssm create $dev1
fill_blacklist $dev2
pass | ssm create $dev2

out=$(ssm list vol)
check list_table "$out" $crypt_vol2

empty_blacklist
ssm -f remove $DEV/$crypt_vol1 $DEV/$crypt_vol2

# clean pvs
for dev in $TEST_DEVS; do
	wipefs -a $dev
done

# btrfs
export SSM_DEFAULT_BACKEND='btrfs'

ssm create -p $vg1 $dev1 $dev2
fill_blacklist
test "$(ssm list)" = ""
ssm create -p $vg2 $dev3 $dev4

out=$(ssm list)
check list_table "$out" $(get_dm_dev $dev3)
check list_table "$out" $(get_dm_dev $dev4)
check list_table "$out" $vg2
not check list_table "$out" $(get_dm_dev $dev1)
not check list_table "$out" $(get_dm_dev $dev2)
not check list_table "$out" $vg1

# Allowed device from a blacklisted pool should be hidden too
empty_blacklist
fill_blacklist $dev1
out=$(ssm list dev)
not check list_table "$out" $(get_dm_dev $dev1)

exit 0
