#!/usr/bin/env python
# Encoding: utf8
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easy tools
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                           <sebastien@xprima.com>
# -----------------------------------------------------------------------------
# Creation  : 31-Jul-2006
# Last mod  : 31-Jul-2006
# -----------------------------------------------------------------------------

import os, tempfile

MERGETOOL = 'gvimdiff -f'
if os.environ.has_key("MERGETOOL"): MERGETOOL = os.environ.get("MERGETOOL")

# ------------------------------------------------------------------------------
#
# MERCURIAL COMMAND REGISTRATION
#
# ------------------------------------------------------------------------------

def hg_lastmodrev( path ):
	rev = -1
	for num in os.popen("hg annotate '%s' | cut -d ':' -f1" %
	(path)).read().split("\n"):
		if not num.strip(): continue
		num = int(num)
		rev = max(num, rev)
	return rev

def hg_cat( rev, path ):
	res = os.popen("hg cat -r%d '%s'" % (rev, path)).read()
	return res

def command_main( ui, repo, *args, **opts ):
	print ("ARGS", args)
	#if not args: return
	path = args[0]
	fd, temp_path = tempfile.mkstemp(prefix="hg-changes-")
	rev = hg_lastmodrev(path)
	print "FUCK"
	os.write(fd, hg_cat(rev, path))
	os.close(fd)
	os.system("%s %s %s" % (MERGETOOL, path, temp_path))
	os.unlink(temp_path)

# This stores the Mercurial commit defaults, that will be used by the
# command_main
cmdtable = {
	"changes": ( command_main, [], 'hg changes', "TODO" )
}

# EOF - vim: tw=80 ts=4 sw=4 noet
