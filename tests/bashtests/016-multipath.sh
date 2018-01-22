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
if mpath_verify; then
	echo "This test can't be run, because there already is an existing multipath configuration."
	exit 1
fi

export COLUMNS=1024
DEV_COUNT=1
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

mpath_setup $TEST_DEVS

# get devices used in multipath
USED_DEVS=$(multipath -ll | \
	grep "[0-9]\+:[0-9]\+:[0-9]\+:[0:9]\+" | \
	sed -e "s/.*[0-9]\+:[0-9]\+:[0-9]\+:[0:9]\+ //" -e "s/ .*//")
MPATH=$(multipath -ll | head -n1 | cut -d " " -f 1)
DM=$(multipath -ll | head -n1 | cut -d " " -f 3)

# some things the ssm should (not) list
ssm list vol | grep multipath
ssm list vol | grep $DM
for d in $USED_DEVS; do
	! ssm list dev |grep -c $dev
done
! ssm list dev |grep -c $MPATH
! ssm list pool |grep -c $MPATH
! ssm list vol | grep $MPATH

# Some cases which should fail
! ssm remove $MPATH

exit 0