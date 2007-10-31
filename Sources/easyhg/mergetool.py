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
# Last mod  : 27-Jul-2007
# -----------------------------------------------------------------------------

# TODO: Add async support 

import os, popen2
MERGETOOL = None

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

FILEMERGE = {
	"APP"     :"opendiff",

	"REVIEW"  :"$0 '$1' '$2'",
	"REVIEW3" :"$0 '$1' '$2' -ancestor '$3'",

	"MERGE"   :"$0 '$2' '$3' -merge '$1' ",
	"MERGE3"  :"$0 '$2' '$3' -ancestor '$4' -merge '$1'"

}

GVIMDIFF = {
	"APP"     : "gvimdiff",

	"REVIEW"  : "$0 '$1' '$2'  " 
	,

	"REVIEW3"   : "$0 -f '$1' '$2' '$3' " \
	,

	"MERGE"  : "$0 '$1' '$3'  " \
	,

	"MERGE3"  : "$0 '$1' '$3' '$4' " \

}

MERGETOOL = None

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
	if MERGETOOL != None: return MERGETOOL
	#if os.environ.has_key("MERGETOOL"):
	#	MERGETOOL = os.environ.get("MERGETOOL")
	#	return
	has_gvim    = which(GVIMDIFF["APP"])
	has_fm      = which(FILEMERGE["APP"])
	if  has_gvim:
		MERGETOOL = GVIMDIFF
	elif has_fm:
		MERGETOOL = FILEMERGE
	else:
		raise Exception(
			"No file merging utility. Please set the MERGETOOL variable\n"
			+ HELP
		)
	return MERGETOOL

def _format( line, *args ):
	"""Replaces '$0', '$1', '$2', ... occurences in 'line' with elements of
	args."""
	for i in range(len(args)):
		line = line.replace("$%d" % (i), args[i])
	return line

def _do( command, *args ):
	tool    = detectMergeTool()
	_args   = [tool["APP"]]
	_args.extend(args)
	program = _format(tool[command.upper()], *_args)
	return os.popen(program +" &").read()

def review( current, other ):
	return _do("review", current, other)

def review3( current, other, base ):
	return _do("review3", current, other, base)

def merge( destination, current, other ):
	return _do("merge", destination, current, other)

def merge3( destination, current, other, base ):
	return _do("merge3", destination, current, other, base)

# EOF
