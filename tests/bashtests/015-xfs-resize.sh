#!/bin/bash
#
# (C)2019 Red Hat, Inc., Jan Tulak <jtulak@redhat.com>
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

export test_name='014-xfs-resize'
test_description='Ensure that resize is reflected immediately in filesystem list'

. lib/test

DEV_COUNT=1
DEV_SIZE=400
# The real size of the device which lvm will use is smaller
TEST_MAX_SIZE=$(($DEV_COUNT*($DEV_SIZE-4)))
aux prepare_devs $DEV_COUNT $DEV_SIZE
aux prepare_mnts 1
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export LVOL_PREFIX="lvol"
export SSM_NONINTERACTIVE='1'
lvol1=${LVOL_PREFIX}001

DEFAULT_VOLUME=${SSM_LVM_DEFAULT_POOL}/$lvol1
TEST_MNT=$TESTDIR/mnt

smallsize=$(($DEV_SIZE/2))
step=$(($smallsize/4))
steps=3
fullpath="$TESTDIR/dev//$SSM_LVM_DEFAULT_POOL/$lvol1"

function check_sizes() {
    pool="$1"
    vol="$2"
    fullpath="$TESTDIR/dev/$pool/$vol"

    output=$(ssm list fs)
    ssm list fs
    dfout=$(df $fullpath | tail -n1)
    fssize=$(echo "$dfout" | awk '{printf "%0.2f", $2/1024}')
    fsfree=$(echo "$dfout" | awk '{printf "%0.2f", $4/1024}')
    check list_table "$output" $pool/$vol none none none ${fssize}MB ${fsfree}MB

}

ssm create -s ${smallsize}M --fstype xfs $dev1 $mnt1
check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 lv_size ${smallsize}.00m
# before resize
check_sizes $SSM_LVM_DEFAULT_POOL $lvol1

# try it in a few steps, because we might be lucky with timing even when
# the issue is present
for i in $(seq 1 $steps); do
    echo "iteration $i"
    # After resize, the size should match what the rest of the system sees
    # immediately.
    ssm resize -s +${step}M $SSM_LVM_DEFAULT_POOL/$lvol1
    check_sizes $SSM_LVM_DEFAULT_POOL $lvol1
done
umount $mnt1
ssm -f remove -a

exit 0