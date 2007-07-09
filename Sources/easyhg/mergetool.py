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
# Last mod  : 09-Jul-2007
# -----------------------------------------------------------------------------

import os
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

def detectMergeTool():
	"""Detects the mergetool for this platform."""
	global MERGETOOL
	if MERGETOOL: return 
	if os.environ.has_key("MERGETOOL"):
		MERGETOOL = os.environ.get("MERGETOOL")
		return
	has_gvim	  = os.popen("gvimdiff --help").read()
	has_tkdiff	= os.popen("tkdiff --help").read()
	has_fm		= os.popen("which " + FM_APP).read()
	if  has_gvim:
		MERGETOOL = GVIMDIFF
	elif has_fm:
		MERGETOOL = FILEMERGE
	elif has_tkdiff:
		MERGETOOL = TKDIFF
	else:
		raise Exception(
			"No file merging utility. Please set the MERGETOOL variable\n"
			+ HELP
		)

def merge( a, b ):
	"""Merges file A with file B."""
	detectMergeTool()
	command = MERGETOOL % (a,b)
	return os.popen(command).read()

# EOF
