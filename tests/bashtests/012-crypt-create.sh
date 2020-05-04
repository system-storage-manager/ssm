#!/bin/bash
#
# (C)2013 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
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

export test_name='012-crypt-create'
test_description='Exercise crypt create'

. lib/test

DEV_COUNT=10
DEV_SIZE=100
TEST_MAX_SIZE=$(($DEV_COUNT*$DEV_SIZE))
aux prepare_devs $DEV_COUNT $DEV_SIZE
aux prepare_mnts 4
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='crypt'
export SSM_CRYPT_DEFAULT_POOL=$vg1
export CRYPT_VOL_PREFIX="${SSM_PREFIX_FILTER}enc"
export SSM_NONINTERACTIVE='1'
export SSM_CRYPT_DEFAULT_VOL_PREFIX=$CRYPT_VOL_PREFIX
crypt_vol1=${CRYPT_VOL_PREFIX}001
crypt_vol2=${CRYPT_VOL_PREFIX}002
crypt_vol3=${CRYPT_VOL_PREFIX}003
crypt_vol4=${CRYPT_VOL_PREFIX}004
passwd="cai0ohMo8M"

pool1=$vg2
pool2=$vg3
DEV="/dev/mapper"

# cryptsetup will ask for password. If luks extension is used
# it will ask when creating header and then when opening the device
pass() {
	echo -e "${passwd}\n${passwd}"
}

crypt_vers() {
	vers=$(cryptsetup luksDump $1 | grep "^Version:" | cut -f2)
	echo "LUKS$vers"
}

fs1=ext4
fs2=ext4
fs3=ext4
fs4=ext4
which mkfs.ext2 && grep -E "^\sext[234]$" /proc/filesystems && fs2=ext2
which mkfs.ext3 && grep -E "^\sext[34]$" /proc/filesystems && fs3=ext3
which mkfs.xfs  && grep -E "^\sxfs$" /proc/filesystems && fs4=xfs

# Try a short password with DEFAULT_BACKEND=crypt
# Later in this test, check it again with a different backend, because
# there are two paths in the code.
! echo -e "a\na" | ssm create $dev1 -e luks
! check list_table "$(ssm list vol)" $crypt_vol1 $SSM_CRYPT_DEFAULT_POOL none crypt
# force it - not it should pass
echo -e "a\na" | ssm -f create $dev1 -e luks
check list_table "$(ssm list vol)" $crypt_vol1 $SSM_CRYPT_DEFAULT_POOL none crypt
ssm remove ${DEV}/$crypt_vol1

# Create encrypted volume
pass | ssm create $dev1
check crypt_vol_field $crypt_vol1 type $(crypt_vers $dev1)
check crypt_vol_field $crypt_vol1 device $dev1
check list_table "$(ssm list vol)" $crypt_vol1 $SSM_CRYPT_DEFAULT_POOL none crypt

pass | ssm create $dev2 -e
check crypt_vol_field $crypt_vol2 type $(crypt_vers $dev2)
check crypt_vol_field $crypt_vol2 device $dev2
check list_table "$(ssm list vol)" $crypt_vol2 $SSM_CRYPT_DEFAULT_POOL none crypt

pass | ssm create -e luks $dev3
mkswap ${DEV}/$crypt_vol3 && swapon ${DEV}/$crypt_vol3
check crypt_vol_field $crypt_vol3 type $(crypt_vers $dev3)
check crypt_vol_field $crypt_vol3 device $dev3
check list_table "$(ssm list vol)" $crypt_vol3 $SSM_CRYPT_DEFAULT_POOL none crypt SWAP
swapoff ${DEV}/$crypt_vol3

pass | ssm create --fs $fs1 -e plain $dev4 $mnt1
check mountpoint $crypt_vol4 $mnt1
check crypt_vol_field $crypt_vol4 type PLAIN
check crypt_vol_field $crypt_vol4 device $dev4
check list_table "$(ssm list vol)" $crypt_vol4 $SSM_CRYPT_DEFAULT_POOL none $fs1 none none crypt
ssm list
umount $mnt1
ssm -f remove ${DEV}/$crypt_vol1

pass | ssm create --fs $fs2 -s 50M -e plain $dev1 $mnt1
check mountpoint $crypt_vol1 $mnt1
check crypt_vol_field $crypt_vol1 type PLAIN
check crypt_vol_field $crypt_vol1 device $dev1
check crypt_vol_field $crypt_vol1 size 102400
check list_table "$(ssm list vol)" $crypt_vol1 $SSM_CRYPT_DEFAULT_POOL none $fs2 none none crypt
umount $mnt1

ssm remove ${DEV}/$crypt_vol1 ${DEV}/$crypt_vol3 ${DEV}/$crypt_vol2 ${DEV}/$crypt_vol4

# Try non existing extension
not ssm create -e enigma $dev1


# Create encrypted lvm volume
export SSM_LVM_DEFAULT_POOL=${vg1}_lvm
export LVOL_PREFIX="lvol"
lvol1=${LVOL_PREFIX}001
lvol2=${LVOL_PREFIX}002
lvol3=${LVOL_PREFIX}003
lvol4=${LVOL_PREFIX}004
export SSM_DEFAULT_BACKEND='lvm'

# Try a short password with backend different than crypt
! echo -e "a\na" | ssm create $dev1 -e luks
! check crypt_vol_field $crypt_vol1 type $(crypt_vers $dev1)
# force it
echo -e "a\na" | ssm -f create $dev1 -e luks
check crypt_vol_field $crypt_vol1 type $(crypt_vers ${DEV}/${SSM_LVM_DEFAULT_POOL}-$lvol1)
ssm remove ${DEV}/$crypt_vol1
ssm -f remove $SSM_LVM_DEFAULT_POOL || true

pass | ssm create --fs $fs3 $dev1 $dev2 $mnt1 -e
check mountpoint $crypt_vol1 $mnt1
check crypt_vol_field $crypt_vol1 type $(crypt_vers ${DEV}/${SSM_LVM_DEFAULT_POOL}-$lvol1)
check crypt_vol_field $crypt_vol1 device ${SSM_LVM_DEFAULT_POOL}-$lvol1
check list_table "$(ssm list vol)" $crypt_vol1 $SSM_CRYPT_DEFAULT_POOL none $fs3 none none crypt
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL none linear
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 2

pass | ssm create -r0 $dev3 $dev4 -e plain
check crypt_vol_field $crypt_vol2 type PLAIN
check crypt_vol_field $crypt_vol2 device ${SSM_LVM_DEFAULT_POOL}-$lvol2
check list_table "$(ssm list vol)" $crypt_vol2 $SSM_CRYPT_DEFAULT_POOL none crypt
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol2 $SSM_LVM_DEFAULT_POOL none striped
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol2 pv_count 4

pass | ssm create $dev5 -e luks
check crypt_vol_field $crypt_vol3 type $(crypt_vers ${DEV}/${SSM_LVM_DEFAULT_POOL}-$lvol3)
check crypt_vol_field $crypt_vol3 device ${SSM_LVM_DEFAULT_POOL}-$lvol3
check list_table "$(ssm list vol)" $crypt_vol3 $SSM_CRYPT_DEFAULT_POOL none crypt
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol3 $SSM_LVM_DEFAULT_POOL none linear
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol3 pv_count 5

pass | ssm create -e plain --fs $fs4 -r10 -s ${DEV_SIZE}M $dev6 $dev7 $dev8 $dev9 $mnt2
check mountpoint $crypt_vol4 $mnt2
check crypt_vol_field $crypt_vol4 type PLAIN
check crypt_vol_field $crypt_vol4 device ${SSM_LVM_DEFAULT_POOL}-$lvol4
check list_table "$(ssm list vol)" $crypt_vol4 $SSM_CRYPT_DEFAULT_POOL 104.00M $fs4 none none crypt
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol4 $SSM_LVM_DEFAULT_POOL 104.00M raid10
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol4 pv_count 9

ssm list
umount $mnt1
umount $mnt2
ssm -f remove ${DEV}/$crypt_vol1 ${DEV}/$crypt_vol3 ${DEV}/$crypt_vol2 ${DEV}/$crypt_vol4
ssm  -f remove $SSM_LVM_DEFAULT_POOL

ssm create $dev1 $dev2
ssm list
pass | ssm -b crypt create $DM_DEV_DIR/$SSM_LVM_DEFAULT_POOL/$lvol1
check crypt_vol_field $crypt_vol1 type $(crypt_vers ${DEV}/${SSM_LVM_DEFAULT_POOL}-$lvol1)
check crypt_vol_field $crypt_vol1 device ${SSM_LVM_DEFAULT_POOL}-$lvol1
check list_table "$(ssm list vol)" $crypt_vol1 $SSM_CRYPT_DEFAULT_POOL none crypt
check list_table "$(ssm list vol)" $SSM_LVM_DEFAULT_POOL/$lvol1 $SSM_LVM_DEFAULT_POOL none linear

ssm remove ${DEV}/$crypt_vol1
ssm  -f remove $SSM_LVM_DEFAULT_POOL
