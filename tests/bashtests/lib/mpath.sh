#!/bin/bash
# Copyright (C) 2011 Red Hat, Inc. All rights reserved.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

#set -euo pipefail
set -e


mpath_is_configured() {
	# test if multipath is configured and kernel modules loaded.
	multipath -ll &>/dev/null || return 1
	return 0
}

mpath_setup() {
	filename="$1"
	mpath_setup_targets "$filename"
	if [ mpath_verify -ne 0 ]; then
		1>&2 echo "An error occured with multipath configuration."
		return 1
	fi
	udevadm settle --timeout 15
	return 0
}

# return 0 if mpath devices are configured
mpath_verify() {
	multipath -ll | grep "mpath" &>/dev/null || return 1
	return 0
}


mpath_setup_targets() {
	filename="$1"
	hostiqn=$(cat /etc/iscsi/initiatorname.iscsi | grep -o "iqn.*$")
	targetcli backstores/block create md_block0 "$filename"
	targetcli /iscsi create
	iqn=$(targetcli /iscsi ls |\
		grep  "o- iqn" |\
		head -n1 |\
		tr -s ' ' |\
		cut -d' ' -f3)
	targetcli /iscsi/$iqn/tpg1/luns create /backstores/block/md_block0
	targetcli /iscsi/$iqn/tpg1/portals delete 0.0.0.0 3260
	targetcli /iscsi/$iqn/tpg1/portals create 127.0.0.1 3260
	targetcli /iscsi/$iqn/tpg1/portals create 127.0.0.2 3260
	targetcli /iscsi/$iqn/tpg1/portals create 127.0.0.3 3260
	targetcli /iscsi/$iqn/tpg1/acls create $hostiqn
	targetcli /iscsi/$iqn/tpg1 set attribute authentication=0

	iscsiadm -m discovery -t sendtargets -p 127.0.0.1 -o new -o delete >/dev/null
	iscsiadm -m node -L all >/dev/null

	# give it few seconds to propagate
	tries=5
	while [ $tries -gt 0 ]; do
		found=$(multipath -ll | wc -l)
		tries=$((tries - 1))
		if [ $found -gt 0 ]; then
			return 0
		fi
		sleep 1
	done
	return 1
}

mpath_cleanup() {
	set +e
	hostiqn=$(cat /etc/iscsi/initiatorname.iscsi | grep -o "iqn.*$")
	iqn=$(targetcli /iscsi ls |\
		grep  "o- iqn" |\
		head -n1 |\
		tr -s ' ' |\
		cut -d' ' -f3)
	mdev=$(multipath -ll | head -n1 | cut -d' ' -f1)
	to_delete=$(lsblk | grep -B 1 $mdev | grep -v $mdev | cut -f1 -d ' ')
	targetcli /iscsi/$iqn/tpg1/acls delete $hostiqn
	targetcli /iscsi/$iqn/tpg1/portals delete 127.0.0.1 3260
	targetcli /iscsi/$iqn/tpg1/portals delete 127.0.0.2 3260
	targetcli /iscsi/$iqn/tpg1/portals delete 127.0.0.3 3260
	targetcli /iscsi/$iqn/tpg1/portals create 0.0.0.0 3260
	targetcli /iscsi/$iqn/tpg1/luns delete lun0
	targetcli /iscsi delete $iqn
	targetcli backstores/block delete md_block0

	multipath -f $mdev
	iscsiadm -m node -u
	set -e

	return 0
}
