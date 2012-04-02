# Copyright (C) 2011 Red Hat, Inc. All rights reserved.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# sanitize the environment
LANG=C
LC_ALL=C
TZ=UTC

unset CDPATH
export HERE=$(pwd)
export PATH=$HERE/lib:$PATH
export SSM="$HERE/../../bin/ssm"
chmod +x $SSM

# grab some common utilities
. lib/utils

export OLDDIR=$HERE
export COMMON_PREFIX="SSMTEST"
export PREFIX="${COMMON_PREFIX}$$"
export SSM_PREFIX_FILTER=$PREFIX

export TESTDIR=$(mkdtemp ${LVM_TEST_DIR-$(pwd)} $PREFIX.XXXXXXXXXX) \
	|| { echo "failed to create temporary directory in ${LVM_TEST_DIR-$(pwd)}"; exit 1; }

# check if coverage exists
export COVERAGE=$(which coverage) || unset COVERAGE
if test -n "$COVERAGE"; then
    export run_coverage="$COVERAGE run -a"
    export COVERAGE_FILE=$OLDDIR/.coverage
    $COVERAGE erase
fi

trap 'aux teardown' EXIT # don't forget to clean up

export LVM_SYSTEM_DIR=$TESTDIR/etc
DM_DEV_DIR=$TESTDIR/dev
mkdir $LVM_SYSTEM_DIR $TESTDIR/lib $DM_DEV_DIR
if test -n "$LVM_TEST_DEVDIR" ; then
	DM_DEV_DIR="$LVM_TEST_DEVDIR"
else
	mknod $DM_DEV_DIR/testnull c 1 3 || exit 1;
	echo >$DM_DEV_DIR/testnull || { echo "Filesystem does support devices in $DM_DEV_DIR (mounted with nodev?)"; exit 1; }
	mkdir -p $DM_DEV_DIR/mapper
fi
export DM_DEV_DIR

cd $TESTDIR

ln -s $HERE/lib/* $TESTDIR/lib

# re-do the utils now that we have TESTDIR/PREFIX/...
. lib/utils

set -eE -o pipefail
aux lvmconf
echo "@TESTDIR=$TESTDIR"
echo "@PREFIX=$PREFIX"
echo "@SSM_PREFIX_FILTER=$SSM_PREFIX_FILTER"

set -vx
