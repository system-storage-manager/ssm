#!/bin/bash
#
# (C)2013 Red Hat, Inc., Jimmy Pan <jipan@redhat.com>
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

if [ "$1" == "-h" -o "$1" == "--help" -o "$#" == 0 ] ; then
	echo "usage: runbashtests.sh [all|*.sh ...]"
	exit 1
fi

set -e
set -o pipefail
set +xv

. set.sh
rm -f lib/ssm

PS4='+$BASH_SOURCE $LINENO: '

export PS4

function runtest()
{
	echo "**************************************"
	echo "     RUNNING $1"
	echo "**************************************"
	if [ "$2" == "suppress_output" ] ; then
		./$1 >${i}.out 2>&1
	else
		./$1 2>&1 | tee ${i}.out
	fi
	if [ "$?" == "0" ] ; then
		echo "**************************************"
		echo "           TEST PASSED"
		echo "**************************************"
		return 0
	else
		echo "**************************************"
		echo "           TEST FAILED"
		echo "**************************************"
		return 1
	fi
}


set -i
set +e
if [ "$@" == "all" ] ; then
        for i in 0*.sh ; do
		runtest $i suppress_output
        done
else
        for i in "$@" ; do
                if ! [ -e $i ] ; then
                        echo file doesn\'t exist
                        continue;
                fi
		runtest $i
        done
fi
