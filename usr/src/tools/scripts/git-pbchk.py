#!/usr/bin/python2.6
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2
#  as published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

#
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
# Copyright 2008, 2012 Richard Lowe
# Copyright 2014 Garrett D'Amore <garrett@damore.org>
# Copyright (c) 2014, Joyent, Inc.
# Copyright (c) 2012, 2015 by Delphix. All rights reserved.
#

import getopt
import os
import re
import subprocess
import sys
import tempfile

from cStringIO import StringIO

#
# Adjust the load path based on our location and the version of python into
# which it is being loaded.  This assumes the normal onbld directory
# structure, where we are in bin/ and the modules are in
# lib/python(version)?/onbld/Scm/.  If that changes so too must this.
#
sys.path.insert(1, os.path.join(os.path.dirname(__file__), "..", "lib",
                                "python%d.%d" % sys.version_info[:2]))

#
# Add the relative path to usr/src/tools to the load path, such that when run
# from the source tree we use the modules also within the source tree.
#
sys.path.insert(2, os.path.join(os.path.dirname(__file__), ".."))

from onbld.Scm import Ignore
from onbld.Checks import Comments, Copyright, CStyle, HdrChk
from onbld.Checks import JStyle, Keywords, ManLint, Mapfile


class GitError(Exception):
    pass

def git(command):
    """Run a command and return a stream containing its stdout (and write its
    stderr to its stdout)"""

    if type(command) != list:
        command = command.split()

    command = ["git"] + command

    try:
        tmpfile = tempfile.TemporaryFile(prefix="git-nits")
    except EnvironmentError, e:
        raise GitError("Could not create temporary file: %s\n" % e)

    try:
        p = subprocess.Popen(command,
                             stdout=tmpfile,
                             stderr=subprocess.PIPE)
    except OSError, e:
        raise GitError("could not execute %s: %s\n" (command, e))

    err = p.wait()
    if err != 0:
        raise GitError(p.stderr.read())

    tmpfile.seek(0)
    return tmpfile


def git_root():
    """Return the root of the current git workspace"""

    p = git('rev-parse --git-dir')

    if not p:
        sys.stderr.write("Failed finding git workspace\n")
        sys.exit(err)

    return os.path.abspath(os.path.join(p.readlines()[0],
                                        os.path.pardir))


def git_branch():
    """Return the current git branch"""

    p = git('rev-parse --symbolic-full-name HEAD')

    if not p:
        sys.stderr.write("Failed finding git branch\n")
        sys.exit(err)

    output = p.readline().strip()
    return output if output != 'HEAD' else None

def git_parent_branch(branch):
    """Return the parent of the current git branch.

    If this branch tracks a remote branch, return the remote branch which is
    tracked.  If not, default to origin/master."""

    assert branch is not None

    p = git("for-each-ref --format=%%(upstream:short) %s" % branch)

    if not p:
        sys.stderr.write("Failed finding git parent branch\n")
        sys.exit(err)

    parent = p.readline().strip()
    return parent if parent else None


def git_comments(parent):
    """Return a list of any checkin comments on this git branch"""

    p = git('log --pretty=tformat:%%B:SEP: %s..' % parent)

    if not p:
        sys.stderr.write("Failed getting git comments\n")
        sys.exit(err)

    return [x.strip() for x in p.readlines() if x != ':SEP:\n']


def git_file_list(parent, paths=None):
    """Return the set of files which have ever changed on this branch.

    NB: This includes files which no longer exist, or no longer actually
    differ."""

    p = git("log --name-only --pretty=format: %s.. %s" %
             (parent, ' '.join(paths)))

    if not p:
        sys.stderr.write("Failed building file-list from git\n")
        sys.exit(err)

    ret = set()
    for fname in p:
        res = git("diff %s HEAD %s" % (parent, fname))
        empty = not res.readline()
        if fname and not fname.isspace() and fname not in ret and not empty:
            ret.add(fname.strip())

    return ret


def not_check(root, cmd):
    """Return a function which returns True if a file given as an argument
    should be excluded from the check named by 'cmd'"""

    ignorefiles = filter(os.path.exists,
                         [os.path.join(root, ".git", "%s.NOT" % cmd),
                          os.path.join(root, "exception_lists", cmd)])
    return Ignore.ignore(root, ignorefiles)


def gen_files(root, parent, paths, exclude):
    """Return a function producing file names, relative to the current
    directory, of any file changed on this branch (limited to 'paths' if
    requested), and excluding files for which exclude returns a true value """

    # Taken entirely from Python 2.6's os.path.relpath which we would use if we
    # could.
    def relpath(path, here):
        c = os.path.abspath(os.path.join(root, path)).split(os.path.sep)
        s = os.path.abspath(here).split(os.path.sep)
        l = len(os.path.commonprefix((s, c)))
        return os.path.join(*[os.path.pardir] * (len(s)-l) + c[l:])

    def ret(select=None):
        if not select:
            select = lambda x: True

        for f in git_file_list(parent, paths):
            f = relpath(f, '.')
            if (os.path.exists(f) and select(f) and not exclude(f)):
                yield f
    return ret


def comchk(root, parent, flist, output):
    output.write("Comments:\n")

    return Comments.comchk(git_comments(parent), check_db=False,
                           output=output)


def mapfilechk(root, parent, flist, output):
    ret = 0

    # We are interested in examining any file that has the following
    # in its final path segment:
    #    - Contains the word 'mapfile'
    #    - Begins with 'map.'
    #    - Ends with '.map'
    # We don't want to match unless these things occur in final path segment
    # because directory names with these strings don't indicate a mapfile.
    # We also ignore files with suffixes that tell us that the files
    # are not mapfiles.
    MapfileRE = re.compile(r'.*((mapfile[^/]*)|(/map\.+[^/]*)|(\.map))$',
        re.IGNORECASE)
    NotMapSuffixRE = re.compile(r'.*\.[ch]$', re.IGNORECASE)

    output.write("Mapfile comments:\n")

    for f in flist(lambda x: MapfileRE.match(x) and not
                   NotMapSuffixRE.match(x)):
        fh = open(f, 'r')
        ret |= Mapfile.mapfilechk(fh, output=output)
        fh.close()
    return ret


def copyright(root, parent, flist, output):
    ret = 0
    output.write("Copyrights:\n")
    for f in flist():
        fh = open(f, 'r')
        ret |= Copyright.copyright(fh, output=output)
        fh.close()
    return ret


def hdrchk(root, parent, flist, output):
    ret = 0
    output.write("Header format:\n")
    for f in flist(lambda x: x.endswith('.h')):
        fh = open(f, 'r')
        ret |= HdrChk.hdrchk(fh, lenient=True, output=output)
        fh.close()
    return ret


def cstyle(root, parent, flist, output):
    ret = 0
    output.write("C style:\n")
    for f in flist(lambda x: x.endswith('.c') or x.endswith('.h')):
        fh = open(f, 'r')
        ret |= CStyle.cstyle(fh, output=output, picky=True,
                             check_posix_types=True,
                             check_continuation=True)
        fh.close()
    return ret


def jstyle(root, parent, flist, output):
    ret = 0
    output.write("Java style:\n")
    for f in flist(lambda x: x.endswith('.java')):
        fh = open(f, 'r')
        ret |= JStyle.jstyle(fh, output=output, picky=True)
        fh.close()
    return ret


def manlint(root, parent, flist, output):
    ret = 0
    output.write("Man page format:\n")
    ManfileRE = re.compile(r'.*\.[0-9][a-z]*$', re.IGNORECASE)
    for f in flist(lambda x: ManfileRE.match(x)):
        fh = open(f, 'r')
        ret |= ManLint.manlint(fh, output=output, picky=True)
	fh.close()
    return ret

def keywords(root, parent, flist, output):
    ret = 0
    output.write("SCCS Keywords:\n")
    for f in flist():
        fh = open(f, 'r')
        ret |= Keywords.keywords(fh, output=output)
        fh.close()
    return ret


def run_checks(root, parent, cmds, paths='', opts={}):
    """Run the checks given in 'cmds', expected to have well-known signatures,
    and report results for any which fail.

    Return failure if any of them did.

    NB: the function name of the commands passed in is used to name the NOT
    file which excepts files from them."""

    ret = 0

    for cmd in cmds:
        s = StringIO()

        exclude = not_check(root, cmd.func_name)
        result = cmd(root, parent, gen_files(root, parent, paths, exclude),
                     output=s)
        ret |= result

        if result != 0:
            print s.getvalue()

    return ret


def nits(root, parent, paths):
    cmds = [copyright,
            cstyle,
            hdrchk,
            jstyle,
            keywords,
	    manlint,
            mapfilechk]
    return run_checks(root, parent, cmds, paths)


def pbchk(root, parent, paths):
    cmds = [comchk,
            copyright,
            cstyle,
            hdrchk,
            jstyle,
            keywords,
	    manlint,
            mapfilechk]
    return run_checks(root, parent, cmds)


def main(cmd, args):

    try:
        opts, args = getopt.getopt(args, 'b:', ['no-comment-check'])
    except getopt.GetoptError, e:
        sys.stderr.write(str(e) + '\n')
        sys.stderr.write("Usage: %s [-b branch] [path...]\n" % cmd)
        sys.exit(1)

    func = nits
    if cmd == 'git-pbchk':
        func = pbchk
        if args:
            sys.stderr.write("only complete workspaces may be pbchk'd\n");
            sys.exit(1)
    parent_branch = None

    for opt, arg in opts:
        if opt == '-b':
            parent_branch = arg
        if opt == '--no-comment-check':
            func = nits

    if not parent_branch:
        branch = git_branch()
        if not branch:
            sys.stderr.write("not currently on any branch, cannot infer " +
                             "parent branch to diff against\n" +
                             "use the '-b <branch>' option to specify the " +
                             "parent branch\n")
            sys.exit(1)
        parent_branch = git_parent_branch(branch)
        if not parent_branch:
            sys.stderr.write(("current branch '%s' has no remote tracking " +
                             "information\ncannot infer parent to diff " +
                             "against, use the '-b <branch>' option to " +
                             "specify the parent branch\n") % branch)
            sys.exit(1)

    print "Comparing to branch: " + parent_branch
    sys.exit(func(git_root(), parent_branch, args))

if __name__ == '__main__':
    try:
        main(os.path.basename(sys.argv[0]), sys.argv[1:])
    except GitError, e:
        sys.stderr.write("failed to run git:\n %s\n" % str(e))
        sys.exit(1)
