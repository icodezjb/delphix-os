#!/usr/bin/ksh

#
# This file and its contents are supplied under the terms of the
# Common Development and Distribution License ("CDDL"), version 1.0.
# You may only use this file in accordance with the terms of version
# 1.0 of the CDDL.
#
# A full copy of the text of the CDDL should have accompanied this
# source.  A copy of the CDDL is also available via the Internet at
# http://www.illumos.org/license/CDDL.
#

#
# Copyright (c) 2012, 2017 by Delphix. All rights reserved.
# Copyright 2014, OmniTI Computer Consulting, Inc. All rights reserved.
# Copyright 2016 Nexenta Systems, Inc.
#

export PATH="/usr/bin"
export NOINUSE_CHECK=1
export STF_SUITE="/opt/zfs-tests"
export STF_TOOLS="/opt/test-runner/stf"
export PATHDIR=""
export TR_STOP_ON_FAILURE=false
runner="/opt/test-runner/bin/run"
search_dir="$STF_SUITE/tests"
auto_detect=false
do_runfile=false

if [[ -z "$TESTFAIL_CALLBACKS" ]] ; then
	export TESTFAIL_CALLBACKS="$STF_SUITE/callbacks/zfs_dbgmsg"
fi

function fail
{
	echo $1
	exit ${2:-1}
}

function usage
{
	typeset msg="$*"
	typeset prog=${0##*/}
	[[ -n "$msg" ]] && echo "$msg" 2>&1
	cat <<EOF 2>/dev/null
Usage:
    $prog [-aqrs] -c runfile
    $prog [-aqrs] pathname [pathname...]
    $prog -h
Options:
    -a         Find free disks on the system, and use them all
    -C script  Upon test failure (due to timeout only) run this script
    -c runfile Use the runfile to determine what tests to run
    -n nfsfile Use the nfsfile to determine the NFS configuration
    -h         This usage message
    -q         Print no output to the console during testing
    -r         Randomize the order of tests in each test group
    -s         Stop on failure, preserving state
EOF
       exit 2
}

function find_disks
{
	typeset all_disks=$(echo '' | sudo -k format | awk \
	    '/c[0-9]/ {print $2}' | grep c[0-9])
	typeset used_disks=$(zpool list -Hvpo name | awk \
	    '/c[0-9]+(t[0-9a-f]+)?d[0-9]+/ {print $1}' | sed -E \
	    's/(s|p)[0-9]+//g')

	typeset disk used avail_disks
	for disk in $all_disks; do
		# For Delphix, explicitly exclude IDE disks like `c3d0`
		# because in our Azure environment the disks are of a
		# different size, and have much worse performance.
		[[ $disk =~ 't' ]] || continue

		for used in $used_disks; do
			[[ "$disk" = "$used" ]] && continue 2
		done
		[[ -n $avail_disks ]] && avail_disks="$avail_disks $disk"
		[[ -z $avail_disks ]] && avail_disks="$disk"
	done

	echo $avail_disks
}

function find_rpool
{
	typeset ds=$(mount | awk '/^\/ / {print $3}')
	echo ${ds%%/*}
}

function verify_id
{
	[[ $(id -u) = "0" ]] && fail "This script must not be run as root."

	sudo -k -n id >/dev/null 2>&1
	[[ $? -eq 0 ]] || fail "User must be able to sudo without a password."
}

function verify_disks
{
	typeset disk
	typeset path
	for disk in $DISKS; do
		case $disk in
		/*) path=$disk;;
		*) path=/dev/rdsk/${disk}s0
		esac
		sudo -k prtvtoc $path >/dev/null 2>&1
		[[ $? -eq 0 ]] || return 1
	done
	return 0
}

function create_links
{
	typeset dir=$1
	typeset file_list=$2

	[[ -n $PATHDIR ]] || fail "PATHDIR wasn't correctly set"

	for i in $file_list; do
		[[ ! -e $PATHDIR/$i ]] || fail "$i already exists"
		ln -s $dir/$i $PATHDIR/$i || fail "Couldn't link $i"
	done

}

function constrain_path
{
	. $STF_SUITE/include/commands.cfg

	PATHDIR=$(/usr/bin/mktemp -d /var/tmp/constrained_path.XXXX)
	chmod 755 $PATHDIR || fail "Couldn't chmod $PATHDIR"

	create_links "/usr/bin" "$USR_BIN_FILES"
	create_links "/usr/sbin" "$USR_SBIN_FILES"
	create_links "/sbin" "$SBIN_FILES"
	create_links "/opt/zfs-tests/bin" "$ZFSTEST_FILES"

	# Special case links
	ln -s /usr/gnu/bin/dd $PATHDIR/gnu_dd
}

constrain_path
export PATH=$PATHDIR

verify_id
while getopts aC:c:hn:o:qrs c; do
	case $c in
	'a')
		auto_detect=true
		;;
	'C')
		[[ -x $OPTARG ]] || fail "File not executable: $OPTARG"
		runner_args+=" -C $OPTARG"
		;;
	'c')
		runfile=$OPTARG
		[[ -f $runfile ]] || fail "Cannot read file: $runfile"
		runner_args+=" -c $runfile"
		do_runfile=true
		;;
	'h')
		usage
		;;
	'n')
		nfsfile=$OPTARG
		[[ -f $nfsfile ]] || fail "Cannot read file: $nfsfile"
		export NFS=1
		. $nfsfile
                ;;
	'o')
		runner_args+=" -o $OPTARG"
		;;
	'q')
		runner_args+=' -q'
		;;
	'r')
		runner_args+=' -r'
		;;
	's')
		runner_args+=' -s'
		export TR_STOP_ON_FAILURE=true
		;;
	esac
done
shift $((OPTIND - 1))

if $do_runfile; then
	[[ $# -eq 0 ]] || fail "Extra parameters after runfile."
else
	[[ $# -ne 0 ]] || fail "No runfile or tests specified."
fi

# If there are remaining arguments, process each in turn, expanding
# filenames as needed.
if [[ $# -ne 0 ]]; then
	for pathname in "$@"; do
		# Most tests in the suite run as root, but those in the cli_user
		# directory must run as the non-root user that launched zfstest.
		# If we're processing pathnames here, specifying both types of
		# tests together is an error.
		# Note that the setup and cleanup tests always run as root.
		errstr="Cannot specify tests run by root and "
		errstr+="a regular user in the same run."
		if [[ $pathname =~ cli_user ]]; then
			[[ $test_user = "root" ]] && fail "$errstr"
			test_user="$USER"
		else
			[[ $test_user = "$USER" ]] && fail "$errstr"
			test_user="root"
		fi

		for expanded in $(eval echo $search_dir/$pathname); do
			[[ -e $expanded ]] || fail "Couldn't find $expanded"
			runner_tests+=" $expanded"
		done
	done

       # Specify pre and post scripts (to be run as root) with no timeout.
       runner_args+=" -g -p setup -P cleanup -u $test_user"
       runner_args+=" -x root -X root -t 0 $runner_tests"
fi

# If the user specified -a, then use free disks, otherwise use those in $DISKS.
if $auto_detect; then
	export DISKS=$(find_disks)
elif [[ -z $DISKS ]]; then
	fail "\$DISKS not set in env, and -a not specified."
else
	verify_disks || fail "Couldn't verify all the disks in \$DISKS"
fi

# Add the root pool to $KEEP according to its contents.
# It's ok to list it twice.
if [[ -z $KEEP ]]; then
	KEEP="$(find_rpool)"
else
	KEEP+=" $(find_rpool)"
fi

export __ZFS_POOL_EXCLUDE="$KEEP"
export KEEP="^$(echo $KEEP | sed 's/ /$|^/g')\$"

. $STF_SUITE/include/default.cfg

num_disks=$(echo $DISKS | awk '{print NF}')
[[ $num_disks -lt 3 ]] && fail "Not enough disks to run ZFS Test Suite"

# DelphixOS has a non-default coreadm configuration.
sudo -k coreadm -e process

# Ensure user has only basic privileges.
ppriv -s EIP=basic -e $runner $runner_args
ret=$?

rm -rf $PATHDIR || fail "Couldn't remove $PATHDIR"

exit $ret
