#!/bin/bash
# Copyright 2011 (C) Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# If we want to run coverage, we can't pass it a bash script.
# So, run coverage now only if $SSM is not the local bash script,
# othervise, just run the script and it will run coverage on its own.

if [ $(grep -c "ssm.local" $SSM) -eq 0 ]; then
	$run_coverage $SSM "$@"
else
	$SSM $@
fi
