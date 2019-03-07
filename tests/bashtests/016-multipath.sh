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

export test_name='015-multipath'
export test_description='Check multipath parsing'

. lib/test
. lib/mpath

if ! mpath_is_configured; then
	echo "Multipath is not installed or configured!"
	echo "If it is installed, then you need to have an empty configuration created with this:"
	echo "sudo mpathconf --enable --with_multipathd y"
	exit 1
fi
if [ mpath_verify -eq 0]; then
	echo "This test can't be run, because there already is an existing multipath configuration."
	exit 1
fi

export COLUMNS=1024
DEV_COUNT=5
DEV_SIZE=10
aux prepare_devs $DEV_COUNT $DEV_SIZE
TEST_DEVS=$(cat DEVICES)
export SSM_DEFAULT_BACKEND='lvm'
export SSM_LVM_DEFAULT_POOL=$vg1
export SSM_NONINTERACTIVE='1'

SSM_PREFIX_FILTER_BAK=$SSM_PREFIX_FILTER
unset SSM_PREFIX_FILTER

cleanup() {
	mpath_cleanup || true
	export SSM_PREFIX_FILTER=$SSM_PREFIX_FILTER_BAK
	aux teardown
}

trap cleanup EXIT

mpdev=$dev1
mpath_setup $mpdev

# get devices used in multipath
USED_DEVS=$(multipath -ll | \
	grep "[0-9]\+:[0-9]\+:[0-9]\+:[0:9]\+" | \
	sed -e "s/.*[0-9]\+:[0-9]\+:[0-9]\+:[0:9]\+ //" -e "s/ .*//")
MPATH=$(multipath -ll | head -n1 | cut -d " " -f 1)
DM="/dev/$(multipath -ll | head -n1 | cut -d " " -f 3)"

# basic listing
check list_table "$(ssm list dev)" "^$DM" 9.80MB
for dev in $USED_DEVS; do
	check list_table "$(ssm list dev)" $dev 9.80MB $DM MULTIPATH
done

# We can't test it here automatically, because lvm filters preventing us from
# touching anything outside of $TESTDIR slaps our hands. And I did not find
# a reliable way how to make a link/DM to $TESTDIR that would work and ssm
# would not try to use the /dev/foo as the real name.
#
# TODO: When the testing infrastructure gets around of this issue, this test
# suite has to be expanded.

# use the device
#ssm create $DM
#check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 1
#ssm -f remove -a
#
#ssm create $DM $dev2
#check lv_field $SSM_LVM_DEFAULT_POOL/$lvol1 pv_count 2
#ssm -f remove -a


# things not supported
not ssm -f remove $MPATH
not ssm -f remove $dev1
not ssm -f remove $DM
not ssm -b multipath list
not ssm -b multipath create $dev1

exit 0