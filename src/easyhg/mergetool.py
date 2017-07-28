#!/usr/bin/env python
#encoding: utf8
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

# FIXME: There's some thinking to be done about how to best merge files

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
	"APP"     : "opendiff",

	"REVIEW"  : "{app} {current} {other} {base}",
	"REVIEW3" : "{current} {other} -ancestor {base}",
	"MERGE"   : "{app} {current} {other} -merge {local}",
	"MERGE3"  : "{app} {current} {other} -ancestor {base} -merge {local}"

}

GVIMDIFF = {
	"APP"     : "gvimdiff",
	"REVIEW"  : "{app} {current} {other} {base}",
	"REVIEW3" : "{app} -f {current} {other} {base}",
	"MERGE"   : "{app} {current} {local} {other}",
	"MERGE3"  : "{app} {current} {local} {other}"
}

MELD = {
	"APP"     : "meld",
	"REVIEW"  : "{app} {current} {other} {base}",
	"REVIEW3" : "{app} {current} {other} {base}",
	"MERGE"   : "{app} {current} {local} {other}",
	"MERGE3"  : "{app} {current} {local} {other}"
}

TOOLS = {
	"fm"       : FILEMERGE,
	"filemerge": FILEMERGE,
	"gvimdiff" : GVIMDIFF,
	"vim"      : GVIMDIFF,
	"meld"     : MELD,
}

MERGETOOL = None

SHELL_ESCAPE            = " '\";`|"
def shell_safe( path ):
	"""Makes sure that the given path/string is escaped and safe for shell"""
	return "".join([("\\" + _) if _ in SHELL_ESCAPE else _ for _ in path])

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

def has(name):
	return name in TOOLS

def set(name):
	global MERGETOOL
	MERGETOOL = get(name)
	return MERGETOOL

def get(name=None):
	"""Detects the mergetool for this platform."""
	global MERGETOOL
	if name:
		return TOOLS[name]
	else:
		if MERGETOOL != None: return MERGETOOL
		if os.environ.has_key("MERGETOOL"):
			MERGETOOL = os.environ.get("MERGETOOL")
			return MERGETOOL
		else:
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

def _format( line, app=None, local=None, current=None, other=None, base=None ):
	"""Replaces '$0', '$1', '$2', ... occurences in 'line' with elements of
	args."""
	m = {}
	if app:     m["app"]     = app
	if local:   m["local"]   = shell_safe(local)
	if current: m["current"] = shell_safe(current)
	if other  : m["other"]   = shell_safe(other)
	if base   : m["base"]    = shell_safe(base)
	print ("FORMAT", line, m)
	print "==", line.format(**m)
	return line.format(**m)

def _do( command, local=None, current=None, other=None, base=None ):
	return os.popen(_cmd(command, local=local, current=current, other=other, base=base) +" &").read()

def _cmd( command, local=None, current=None, other=None, base=None ):
	tool    = get()
	app     = tool["APP"]
	assert app, "Missing APP entry in tool: {0}".format(tool)
	return _format(tool[command.upper()], app=app, local=local, current=current, other=other, base=base)

# FIXME: This should be local, current, other, base
def review( current, other, run=True ):
	return (_do if run else _cmd)("review", current=current, other=other)

def review3( current, other, base, run=True ):
	return (_do if run else _cmd)("review3", current=current, other=other, base=base)

def merge( destination, current, other, run=True ):
	return (_do if run else _cmd)("merge", local=destination, current=current, other=other)

def merge3( destination, current, other, base, run=True ):
	return (_do if run else _cmd)("merge3", local=destination, current=current, other=other, base=base)

# EOF - vim: tw=80 ts=4 sw=4 noet