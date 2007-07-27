#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easy tools
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                           <sebastien@type-z.org>
# -----------------------------------------------------------------------------
# Creation  : 09-Jul-2007
# Last mod  : 10-Jul-2007
# -----------------------------------------------------------------------------

import os, popen2
MERGETOOL = None

FM_APP    = "/Developer/Applications/Utilities/FileMerge.app/Contents/MacOS/FileMerge"
GVIMDIFF  = "gvimdiff '%s' '%s'"
TKDIFF    = "tkdiff '%s' '%s'"
FILEMERGE = FM_APP + " -left '%s' -right '%s'" 

HELP = """\
The 'mergetool' module was unable to locate a tool for doing the the merge.
Please define an environment variable named MERGETOOL that is like

MERGETOOL="mergeprogram '%s' '%s'"

where the first '%s' will correspond to the LEFT file and the '%s' to the RIGHT
file. The merge should happen in the LEFT file.

The supported merge applications are:

 - gvimdiff (default)
 - Apple FileMerge
 - tkdiff

"""

def popen(command):
	# FIXME: popen3[1] does not give the same results as popen !!
	out, sin = popen2.popen4(command)
	sin.close()
	res = out.read() ; out.close()
	return res

def which(program):
	"""Tells if the given program is available in the path."""
	res = popen("which %s" % (program))
	res = not res.startswith("no ")
	return res

def detectMergeTool():
	"""Detects the mergetool for this platform."""
	global MERGETOOL
	if MERGETOOL: return 
	if os.environ.has_key("MERGETOOL"):
		MERGETOOL = os.environ.get("MERGETOOL")
		return
	has_gvim    = which("gvimdiff")
	has_tkdiff  = which("tkdiff")
	has_fm      = which( FM_APP)
	if  has_gvim:
		MERGETOOL = GVIMDIFF
	elif has_tkdiff:
		MERGETOOL = TKDIFF
	elif has_fm:
		MERGETOOL = FILEMERGE
	else:
		raise Exception(
			"No file merging utility. Please set the MERGETOOL variable\n"
			+ HELP
		)

def review( a, b ):
	"""Reviews A and B (without allowing modifications)"""
	detectMergeTool()
	command = MERGETOOL % (a,b)
	return popen(command)

def merge( left, right, base=None ):
	"""Merges file A with file B."""
	detectMergeTool()
	# TODO: Some mergetool do not support destination
	command = MERGETOOL % (left, right)
	return popen(command)

# EOF
