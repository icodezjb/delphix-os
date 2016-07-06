#!/bin/ksh -p
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

#
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

#
# Copyright (c) 2012, 2016 by Delphix. All rights reserved.
#

. $STF_SUITE/include/libtest.shlib
. $STF_SUITE/tests/functional/cli_root/zpool_create/zpool_create.shlib

#
# DESCRIPTION:
#	Create a pool with same devices twice or create two pools with same
#	devices, 'zpool create' should failed.
#
# STRATEGY:
#	1. Loop to create the following three kinds of pools.
#		- Regular pool
#		- Mirror
#		- Raidz
#	2. Create two pools but using the same disks, expect failed.
#	3. Create one pool but using the same disks twice, expect failed.
#

verify_runnable "global"

function cleanup
{
	typeset dtst
	typeset disk

	for dtst in $TESTPOOL $TESTPOOL1; do
		poolexists $dtst && destroy_pool $dtst
	done

	for disk in $DISKS; do
		partition_disk $SIZE $disk 6
	done
}

log_onexit cleanup

unset NOINUSE_CHECK
typeset opt
for opt in "" "mirror" "raidz" "raidz1"; do
	typeset disk="$DISKS"
	(( ${#opt} == 0 )) && disk=${DISKS%% *}

	typeset -i count=$(get_word_count $disk)
	if (( count < 2  && ${#opt} != 0 )) ; then
		continue
	fi

	# Create two pools but using the same disks.
	create_pool $TESTPOOL $opt $disk
	log_mustnot $ZPOOL create -f $TESTPOOL1 $opt $disk
	destroy_pool $TESTPOOL

	# Create two pools and part of the devices were overlapped
	create_pool $TESTPOOL $opt $disk
	log_mustnot $ZPOOL create -f $TESTPOOL1 $opt ${DISKS% *}
	destroy_pool $TESTPOOL

	# Create one pool but using the same disks twice.
	log_mustnot $ZPOOL create -f $TESTPOOL $opt $disk $disk
done

log_pass "Using overlapping or in-use disks to create a new pool fails as expected."
