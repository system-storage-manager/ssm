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

set -e

die() { echo >&2 "$@"; exit 1; }

MAX_TRIES=4

rand_bytes()
{
  n=$1

  chars=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789

  dev_rand=/dev/urandom
  if test -r "$dev_rand"; then
    # Note: 256-length($chars) == 194; 3 copies of $chars is 186 + 8 = 194.
    head -c$n "$dev_rand" | tr -c $chars 01234567$chars$chars$chars
    return
  fi

  cmds='date; date +%N; free; who -a; w; ps auxww; ps ef; netstat -n'
  data=$( (eval "$cmds") 2>&1 | gzip )

  n_plus_50=$(expr $n + 50)

  # Ensure that $data has length at least 50+$n
  while :; do
    len=$(echo "$data"|wc -c)
    test $n_plus_50 -le $len && break;
    data=$( (echo "$data"; eval "$cmds") 2>&1 | gzip )
  done

  echo "$data" \
    | dd bs=1 skip=50 count=$n 2>/dev/null \
    | tr -c $chars 01234567$chars$chars$chars
}

mkdtemp()
{
  case $# in
  2);;
  *) die "Usage: mkdtemp DIR TEMPLATE";;
  esac

  destdir=$1
  template=$2

  case $template in
  *XXXX) ;;
  *) die "invalid template: $template (must have a suffix of at least 4 X's)";;
  esac

  fail=0

  # First, try to use mktemp.
  d=$(env -u TMPDIR mktemp -d -t -p "$destdir" "$template" 2>/dev/null) \
    || fail=1

  # The resulting name must be in the specified directory.
  case $d in "$destdir"*);; *) fail=1;; esac

  # It must have created the directory.
  test -d "$d" || fail=1

  # It must have 0700 permissions.
  perms=$(ls -dgo "$d" 2>/dev/null) || fail=1
  case $perms in drwx------*) ;; *) fail=1;; esac

  test $fail = 0 && {
    echo "$d"
    return
  }

  # If we reach this point, we'll have to create a directory manually.

  # Get a copy of the template without its suffix of X's.
  base_template=$(echo "$template"|sed 's/XX*$//')

  # Calculate how many X's we've just removed.
  nx=$(expr length "$template" - length "$base_template")

  err=
  i=1
  while :; do
    X=$(rand_bytes $nx)
    candidate_dir="$destdir/$base_template$X"
    err=$(mkdir -m 0700 "$candidate_dir" 2>&1) \
      && { echo "$candidate_dir"; return; }
    test $MAX_TRIES -le $i && break;
    i=$(expr $i + 1)
  done
  die "$err"
}

init_udev_transaction() {
    if test "$DM_UDEV_SYNCHRONISATION" = 1; then
	COOKIE=$(dmsetup udevcreatecookie)
	# Cookie is not generated if udev is not running!
	if test -n "$COOKIE"; then
	    export DM_UDEV_COOKIE=$COOKIE
	fi
    fi
}

finish_udev_transaction() {
    if test "$DM_UDEV_SYNCHRONISATION" = 1 -a -n "$DM_UDEV_COOKIE"; then
	dmsetup udevreleasecookie
	unset DM_UDEV_COOKIE
    fi
}

teardown_udev_cookies() {
    if test "$DM_UDEV_SYNCHRONISATION" = 1; then
	# Delete any cookies created more than 10 minutes ago 
	# and not used in the last 10 minutes.
	dmsetup udevcomplete_all -y 10
    fi
}

skip() {
    touch SKIP_THIS_TEST
    exit 200
}

kernel_at_least() {
    major=$(uname -r |cut -d. -f1)
    minor=$(uname -r |cut -d. -f2 | cut -d- -f1)

    test $major -gt $1 && return 0
    test $major -lt $1 && return 1
    test $minor -gt $2 && return 0
    test $minor -lt $2 && return 1
    test -z "$3" && return 0

    minor2=$(uname -r | cut -d. -f3 | cut -d- -f1)
    test -z "$minor2" -a $3 -ne 0 && return 1
    test $minor2 -ge $3 2>/dev/null && return 0

    return 1
}

align_size_up() {
    size=$1
    [ -z $2 ] && stripes=0
    [ -z $3 ] && extent=4

    [ -z $size ] || [ -z $stripes ] || [ -z $extent ] && exit 1

    tmp=$((size%extent))
    if [ $tmp -ne 0 ]; then
        size=$(($size+($extent-$tmp)))
    fi
    if [ $stripes -eq 0 ]; then
        echo "$size"
        return 0
    fi
    extents=$(($size/$extent))
    tmp=$(($extents%$stripes))
    if [ $tmp -ne 0 ]; then
        extents=$(($extents-$tmp+$stripes))
    fi
    echo "$(($extents*$extent))"
}

umount_all() {
    [ ! -d $TEST_MNT ] && return
    for mp in $(ls $TEST_MNT); do
        mount | grep " $TEST_MNT/$mp " 2>&1> /dev/null && {
		while umount $TEST_MNT/$mp 2> /dev/null; do continue; done
	} || true
    done
}

if test -n "$PREFIX"; then
    vg=${PREFIX}vg
    lv=LV

    for i in `seq 1 16`; do
        name="${PREFIX}pv$i"
        dev="$DM_DEV_DIR/mapper/$name"
        mnt="$TEST_MNT/test$i"
        eval "dev$i=$dev"
        eval "lv$i=LV$i"
        eval "vg$i=${PREFIX}vg$i"
        eval "mnt$i=$mnt"
    done
fi


