#!/usr/bin/env python
# Encoding: utf8
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easy tools
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                           <sebastien@xprima.com>
# -----------------------------------------------------------------------------
# Creation  : 05-May-2006
# Last mod  : 30-Jul-2007
# -----------------------------------------------------------------------------

# TODO: cache the hg_get_merge_revisions in the conflict file

# Origins:
#  - http://marc.info/?l=mercurial&m=114719261130043&w=2
#  - http://marc.info/?t=114719277400001&r=1&w=2

import os, sys, re, shutil, difflib, stat, hashlib, json
import easyhg.mergetool
from easyhg.output import *
try:
	import urwide, urwid
except:
	urwide = None

__version__ = "0.9.4"
PROGRAM_NAME = "easymerge"

USAGE = """\
%s %s

    %s is tool for Subversion-like merging in Mercurial. It gives more
    freedom to the resolution of conflicts, the user can individually pick the
    changes and resolve them with its preferred set of tools.

    The tool used to do the merging has to be set into this script or into the
    $MERGETOOL environment variable. By default, it is 'gvimdiff'

Commands :

    list      [DIRECTORY]                     - list registered conflicts
    resolve   [CONFLICT] [keep|update|merge]  - resolves all/given conflict(s)
    unresolve [CONFLICT]                      - sets a conflict as unresolve
    clean     [DIRECTORY]                     - cleans up the conflict files
    commit                                    - try to commit the changes (TODO)

Usage:

    Edit your ~/.hgrc file and set [ui] merge=easymerge:

        [ui]
        merge = easymerge
        ‥

    Mercurial will automatically invoke this command when merging, so that it
    creates three files in the same directory as the ORIGINAL file with
    extensions '.current', '.base' or '.other' corresponding to copies of the
    CURRENT, PARENT and OTHER files.

    You can then proceed to `resolve` the different conflicts that may have
    happened when merging. You can `list` the conflicts, and then `resolve` them
    one by one. Whenever you made a mistake, and want to quickly unresolve a
    conflict, use the `unresolve` command.

    Once you resolved all conflicts, you can `commit` to save your changes in
    your repository. Committing automatically cleans the current directory from
    files created by %s, but you can also `clean` the directory
    whenever you want (for instance, when you do not want to merge anymore).
""" % (PROGRAM_NAME, __version__, PROGRAM_NAME, PROGRAM_NAME)

CONFLICTS_FILE = ".hgconflicts"
BASE           = "base"
CURRENT        = "current"
OTHER          = "other"
CLEAN_MATCH    = re.compile("^.+\.(orig|(base|current|other|" + "|".join([OTHER, CURRENT, BASE]) + ")((-r|-pro)\d+)(-\w+)?(\.\d+)?)$")

# -----------------------------------------------------------------------------
#
# UTILITIES
#
# -----------------------------------------------------------------------------

def readlines(p):
	"""Reads the content of the file at the given path and returns a list of its
	lines."""
	f = open(p, 'rt') ; t = f.read() ; f.close()
	return t.split("\n")

def cutpath( root, path ):
	"""Cuts the root from the given path if the path is prefixed with the
	root."""
	if not root[-1] == "/": root = root + "/"
	if path.startswith(root): return path[len(root):]
	else: return path

def copy( source, dest ):
	"""Copies the content of the source to the dest, preserving the permissions
	of the dest file."""
	dest = file(dest, 'w')
	source = file(source, 'r')
	dest.write(source.read())
	dest.close()
	source.close()

def backup_existing( path ):
	"""If the given path exists and is a file, the path will be copied to a file
	in the same directory, with the same name suffixed by a number (.1, .2, .3),
	depending on the number of already existing backups."""
	if not os.path.isfile(path): return
	new_path = path ; i = 1
	while os.path.exists(new_path):
		new_path = "%s.%s" % (path, i)
		i += 1
	copy(path, new_path)
	return new_path

def ensure_notexists( path ):
	if os.path.exists(path):
		raise Exception(path)

def diff_count( a, b ):
	"""Returns the number of lines conflicting between a and b and the total
	number of lines in a."""
	# We count the lines with no conflict
	no_conflict = 0
	a, b		= readlines(a), readlines(b)
	for line in difflib.ndiff(a, b):
		if line.startswith(" "):
			no_conflict += 1
	return no_conflict / float(len(a)) * 100

# -----------------------------------------------------------------------------
#
# UI
#
# -----------------------------------------------------------------------------

CONSOLE_STYLE = u"""\
Frame         : WH, DB, SO
header        : WH, DC, BO
footer        : WH, DB, SO
info          : BL, DC, SO
tooltip       : Lg, DB, BO

label         : Lg, DB, SO
title         : WH, DB, BO

resolved      : DG, DB, SO
unresolved    : LR, DB, SO

dialog        : BL, Lg, SO
dialog.shadow : DB, BL, SO
dialog.border : Lg, DB, SO

Edit          : WH, DB, BO
Edit*         : WH, DM, BO
Button        : LC, DB, BO
Button*       : WH, DM, BO
Divider       : LB, DB, SO
Text          : WH, DB, SO
Text*         : WH, DM, BO

#edit_summary : DM, DB, SO
"""

DIALOG_STYLE = """
header        : BL, Lg, BO
Hdr           : BL, Lg, BO
"""

CONSOLE_UI = u"""\
Hdr MERCURIAL - Easymerge %s

Txt  Merging  ○ CURRENT(theirs) + ● OTHER(yours) = ◌ LOCAL
Txt           △ BASE(ancestor)

$REVINFO

---

Col
    Txt Path
    Txt Status
    Txt Details
End

Col                                 #conflicts
    Ple                             #conflict
    End
    Ple                             #state
    End
    Ple                             #details
    End
End

___

GFl
    Btn [Leave]                      #btn_leave  &press=leave
    Btn [Commit]                     #btn_commit &press=commit
End
""" % (__version__)

DLG_RESOLVE = u"""\

Hdr
Hdr  RESOLVE CONFLICT
Hdr  %s
Hdr

Txt Merge

Chc [X:R] Merge ○ R%-3s CURRENT and ● R%-3s OTHER

Txt Choose

Chc [ :R] Use ○ R%-3s (yours/current)
Chc [ :R] Use ● R%-3s (theirs/other)
Chc [ :R] Use △ R%-3s (base)

Txt Keep

Chc [ :R] Keep ◌ LOCAL (if you made/make changes manually) &key=doMayResolve

---

GFl
    Btn [Cancel]             #btn_cancel_resolve &press=cancel
    Btn [RESOLVE]            #btn_do_resolve     &press=doResolve
End\
"""

ASK_RESOLVED = """
Hdr Conflict resolution

Txt Did you resolve the conflict ?

GFl
    Btn [No]                        #no
    Btn [Yes]                       #yes
End
"""

ASK_UNRESOLUTION = """
Hdr Undo conflict resolution

Txt Unresolving a conflict will change
Txt the state of your conflict file
Txt to where it was. This is the equivalent
Txt of an `hg revert` on your
Txt conflict file.

Txt However, your changes will be saved in as
Txt
Txt %s
Txt
Txt so you can copy it over your current
Txt
Txt %s
Txt
Txt to redo the resolution.
---
Txt Would you like to proceed ?
GFl
    Btn [No]                        #no
    Btn [Yes]                       #yes
End
"""

INFO_UNRESOLUTION = """
Hdr Conflict unresolved

Txt Your changes were saved to
Txt
Txt   %s
Txt
Txt The local file was reverted to current
Txt
Txt   %s

GFl
    Btn [OK]                        #ok
End
"""

INFO_TEMPLATE = u"""\
  ◌┄┄┄╮  LOCAL
  │   │
  ○   │  CURRENT  R%-3s by %s on %s
  │   ●  OTHER    R%-3s by %s on %s
  │───╯
  │
  △      BASE     R%-3s on %s by %s\
"""

class ResolutionHandler(urwide.Handler):

	def __init__(self, merge, dialog, conflict ):
		urwide.Handler.__init__(self)
		self.merge = merge
		self.dialog    = dialog
		self.conflict  = conflict

	def onCancel(self, widget):
		self.dialog.end()

	def onKeyPress( self, widget, key) :
		focus = urwide.original_focus(widget)
		if key == "enter":
			for radio in self.dialog.groups.R:
				if radio == focus and radio.get_state():
					self.onDoResolve(widget)
					return True
		return False

	def getSelection( self ):
		selected = 0
		for radio in self.dialog.groups.R:
			if radio.get_state(): break
			else: selected += 1
		return selected

	def onDoResolve(self, widget):
		self.dialog.end()
		selected = self.getSelection()
		if  selected == 0:
			self.merge.ops.resolveConflictByMerging(self.conflict.number)
			self.merge.main_ui.tooltip("Conflict was resolved by merging {0} and {1}".format(CURRENT, OTHER))
		elif selected == 1:
			self.merge.ops.resolveConflictByReplacing(self.conflict.number, "current")
			self.merge.main_ui.tooltip("Conflict was resolved by updating to {0}".format(CURRENT))
		elif selected == 2:
			self.merge.ops.resolveConflictByReplacing(self.conflict.number, "other")
			self.merge.main_ui.tooltip("Conflict was resolved by updating to {0}".format(OTHER))
		elif selected == 3:
			self.merge.ops.resolveConflictByReplacing(self.conflict.number, "base")
			self.merge.main_ui.tooltip("Conflict was resolved by updating to {0}".format(BASE))
		elif selected == 4:
			self.merge.main_ui.tooltip("Conflict was resolved by keeping the local file")
			self.merge.ops.resolveConflictByKeepingLocal(self.conflict.number)
		else:
			raise Exception("Internal error")
		self.merge.updateConflicts()

class ConsoleUI(urwide.Handler):
	"""Main user interface for merge."""

	def __init__(self, conflicts):
		urwide.Handler.__init__(self)
		# Operations configuration for Console UI
		self.ops = Operations(conflicts)
		self.ops.command = self.command
		self.ops.output  = self.log
		self.ops.info    = self.log
		self.ops.log     = self.log
		self.ops.error   = self.log
		self.ops.ask     = self.ask
		self.ops.warning = self.log
		self.ops.color   = False
		# Names are confusing
		self.ui = urwide.Console()
		self.main_ui = self.ui
		self.ui.handler(self)
		self.ui.data.conflicts = conflicts
		self.ui.strings.RESOLVED   = "RESOLVED    [U]nresolve | Re[V]iew | Diff: [C]urrent, [O]ther | [S]ources | [Q]uit"
		self.ui.strings.UNRESOLVED = "UNRESOLVED  [R]esolve   | Re[V]iew | Diff: [C]urrent, [O]ther | [S]ources | [Q]uit"

	def conflicts( self ):
		"""Returns the conflicts associated with this UI."""
		return self.main_ui.data.conflicts

	def conflictsInfo( self ):
		"""Return '(CURRENT_INFO, PARENT_INFO, OTHER_INFO)' from the
		conflicts."""
		c = self.conflicts()
		cur = c.getCurrentInfo()
		oth = c.getOtherInfo()
		par = c.getBaseInfo()
		assert cur, "Missing CURRENT information"
		assert oth, "Missing OTHER information"
		assert par, "Missing PARENT information"
		return cur, par, oth

	def mergeInfo( self ):
		"""Returns a user-friendly descirption of the merge"""
		cur, par, oth = self.conflictsInfo()
		print (cur,par,oth)
		return INFO_TEMPLATE % (
			cur[0],  cur[1], cur[2],
			oth[0],  oth[1], oth[2],
			par[0],  par[1], par[2]
		)

	def main( self ):
		if self.main_ui.data.conflicts.all():
			console_ui = CONSOLE_UI.replace("$REVINFO", "\n".join(["Txt  " + l for l in self.mergeInfo().split("\n")]))
			self.ui.create(CONSOLE_STYLE, console_ui)
			self.updateConflicts()
			self.ui.main()
		else:
			print ("No conflicts found.")

	def conflictStateChanged( self, button, state ):
		if not state == True: return
		conflict = button.conflict
		if conflict.getState() == conflict.RESOLVED:
			conflict._ui_state.set_text(('resolved', "RESOLVED"))
		else:
			conflict._ui_state.set_text(('unresolved', "UNRESOLVED"))

	def updateConflicts( self ):
		# Utility classes to manage the widgets
		def clear( widget ):
			urwide.remove_widgets(self.main_ui._widgets[widget])
		def add( conflict, base, *args, **kwargs ):
			widget = self.main_ui.new(*args, **kwargs)
			self.main_ui.unwrap(widget).conflict = conflict
			urwide.add_widget(self.main_ui._widgets[base], widget)
			return widget
		def finish( widget ):
			self.main_ui._widgets[widget].set_focus(0)
		# We clear the Ple (Piles)
		map(clear, "conflict state details".split())
		# We register the conflicts
		for c in self.main_ui.data.conflicts.all():
			group = []
			edit    = add(c, "conflict", urwid.Edit, " " + c.path())
			state   = add(c, "state",    urwid.Text, (c.state.lower(), c.state))
			# FIXME: Update this
			details = add(c, "details",  urwid.Text, c.describe())
			c._ui_state = state
			c._ui_group = group
			for w in (edit,):
				self.main_ui.setTooltip(w, c.state.upper())
				self.main_ui.onKey(w, self.onConflict)
				self.main_ui.onFocus(w, self.onConflictFocus)
			self._updateConflictView(c)
			#conflict.add_widget(self.ui.wrap(conflict, "@unresolved &key=resolve ?UNRESOLVED"))
		# We notify that the Ple (Piles) construction is finished
		map(finish, "conflict state details".split())

	def _updateConflictView( self, conflict ):
		# TODO: Change resolution type
		pass

	def onResolveConflict( self, conflict ):
		"""Resolves the given conflict by popping up a dialog."""
		# TODO: Get widget conflict
		c, p, o = self.conflictsInfo()
		ui = DLG_RESOLVE % (
			conflict.path(),
			c[0], o[0],
			c[0],
			o[0],
			p[0]
		)
		dialog = urwide.Dialog(self.ui, ui=ui,palette=DIALOG_STYLE,width=60)
		self.main_ui.dialog(dialog)
		# NOTE: If I move this elsewhere, it will fail ! (Python bug)
		handler = ResolutionHandler(self,dialog,conflict)
		dialog.handler(handler)

	def onConflictFocus( self, widget ):
		conflict = widget.conflict
		def info( path ):
			if path == conflict.path():
				return "This is the local file"
			sig_local = conflict._sig(conflict.current())
			sig_right = hashlib.sha256(conflict._read(path)).hexdigest()
			if sig_local == sig_right: return "Same content as the local file"
			else: return "Not same content as local file: " + sig_right
		if conflict.state == Conflict.RESOLVED:
			self.main_ui.setInfo(widget, "RESOLVED")
		else:
			self.main_ui.setInfo(widget, "UNRESOLVED")

	def onUnresolveConflict( self, conflict, callback=False ):
		# If the current resolved version was resolved form base or other, we
		# do not need to save a backup
		if conflict._sig(conflict.path()) in (conflict._sig(conflict.base()),
		conflict._sig(conflict.other()), conflict._sig(conflict.current())):
			callback = True
		if callback:
			backup = self.ops.unresolve(conflict.number)
			conflict._ui_state.set_text((conflict.state.lower(), conflict.state))
			self._updateConflictView(conflict)
			if backup:
				dialog = urwide.Dialog(self.ui, ui=INFO_UNRESOLUTION % (backup[0], conflict.current()), style=DIALOG_STYLE)
				dialog.onPress(dialog.widgets.ok , lambda x:dialog.end())
				self.main_ui.dialog(dialog)
		else:
			dialog = urwide.Dialog(self.ui,
				ui=ASK_UNRESOLUTION % (conflict.nextMerge(), conflict.path() ),
				width=45,
				height=23,
				style=DIALOG_STYLE
			)
			dialog.onPress(dialog.widgets.yes, lambda x:cmp(dialog.end(), self.onUnresolveConflict(conflict, True)))
			dialog.onPress(dialog.widgets.no , lambda x:dialog.end())
			self.main_ui.dialog(dialog)
		return True

	def onConflict( self, widget, key ):
		if key in ('left', 'right', 'up', 'down'): return False
		conflict = widget.conflict
		if conflict.state == Conflict.RESOLVED:
			# Undoes the conflict
			if   key == "u":
				self.onUnresolveConflict(conflict)
			# Reviews what as changed
			elif key == "v":
				self.ops.reviewConflict(conflict)
			elif key == "o":
				self.ops.reviewConflict(conflict, "local", "other")
			elif key == "c":
				self.ops.reviewConflict(conflict, "local", "current")
			elif key == "s":
				self.ops.reviewConflictSources(conflict)
		else:
			# Reviews the conflict
			if   key == "v":
				self.ops.reviewConflict(conflict)
			elif key == "o":
				self.ops.reviewConflict(conflict, "local", "other")
			elif key == "c":
				self.ops.reviewConflict(conflict, "local", "current")
			elif key == "s":
				self.ops.reviewConflictSources(conflict)
			# Selects the current choice
			# Selects the current choice
			elif key == "enter" or key == "r":
				group = conflict._ui_group
				if widget.conflict.isResolved():
					self.onUnResolve(widget, conflict)
				else:
					self.onResolveConflict(conflict)
				self._updateConflictView(conflict)
		return True

	def onKeyPress( self, widget, key ):
		if  key == "q":
			self.ui.end()
			return True
		elif key == "c":
			if not self.ui.data.conflicts.unresolved():
				# TODO: Detect if commit was successful or not
				#self.ui.end()
				#res = os.popen("hg commit").read()
				pass
		else:
			return False

	def onLeave( self, widget ):
		self.main_ui.tooltip("Leave")
		resolved   = len(self.conflicts().resolved())
		unresolved = len(self.conflicts().unresolved())
		if unresolved:
			self.main_ui.end("{0} resolved conflicts, {1} left to resolve.\nTo continue: {2} resolve ".format(resolved, unresolved, PROGRAM_NAME))
		else:
			self.main_ui.end("{0} resolved conflicts.\nDon't forget to commit your changes with {1} commit".format(resolved, PROGRAM_NAME))

	def onCommit( self, widget ):
		os.system("hg commit")
		self.main_ui.end()
		self.ops.clean()

	# Operations bindings
	# ------------------------------------------------------------------------

	def ask( self, message ):
		return "y"

	def command( self, command ):
		os.popen(command).read()

	def format( self, format, **kwargs ):
		return format(message, **kwargs)

	def log( self, *args ):
		self.main_ui.info(u" ".join(u"{0}".format(_) for _ in args))
		self.main_ui.draw()

# -----------------------------------------------------------------------------
#
# CONFLICT CLASS
#
# -----------------------------------------------------------------------------

class Conflict:
	"""Represents a conflict between two files."""

	RESOLVED   = "RESOLVED"
	UNRESOLVED = "UNRESOLVED"
	SEPARATOR  = " -- "

	def __init__( self, number, path, currentPath, basePath, otherPath,
	state=None, description="", provisional=False ):
		if not state: state = Conflict.UNRESOLVED
		assert type(number) == int
		self.conflicts    = None
		self.provisional  = provisional
		self.number       = number
		self.state        = state
		self._path        = path
		self._currentPath = currentPath
		self._basePath    = basePath
		self._otherPath   = otherPath
		self.description  = description

	def toJSON( self ):
		return dict(
			number      = self.number,
			path        = self._path,
			currentPath = self._currentPath,
			basePath    = self._basePath,
			otherPath   = self._otherPath,
			state       = self.state,
			description = self.description,
			provisional = self.provisional,
		)

	@classmethod
	def fromJSON( self, kwargs ):
		return Conflict(**kwargs)

	def getState( self ):
		"""Returns the state for this conflict (Conflict.RESOLVED or
		Conflict.UNRESOLVED)"""
		return self.state

	def provision( self, current, other, base ):
		# TODO: provisional data should be stored in the .hgconflicts file,
		# so that the files can't be removed from the fs
		if not self.provisional: return self
		local        = self._path
		base_path    = self._basePath
		current_path = self._currentPath
		other_path   = self._otherPath
		current_copy = local + ".current-r" + current[0]
		other_copy   = local + ".other-r"   + other[0]
		base_copy    = local + ".base-r"    + base[0]
		# We backup .orig, .base and .new that may already be tehre
		backups = []
		for p,o in ((base_copy, base_path), (current_copy, current_path), (other_copy, other_path)):
			if os.path.exists(p):
				with open(p) as f: pt = f.read()
				with open(o) as f: ot = f.read()
				if pt != ot:
					suffix  = 0
					prefix  = p + ".backup"
					path    = prefix
					while os.path.exists(path):
						path = prefix + suffix
						suffix += 1
					backups.append((p,path))
		for o,n in backups:
			warning("Previous conflict files present and differ, backing up {0} as {1}".format(o,n))
			shutil.move(o, n)
		# And we create the new ones
		info(u"Provisioning conflict for {0}".format(self._path))
		info(u"◌ LOCAL   = {0}".format(self._path))
		info(u"○ CURRENT = {0}".format(current_copy))
		info(u"● OTHER   = {0}".format(other_copy))
		info(u"△ BASE    = {0}".format(base_copy))
		for n,o in ((base_copy, base_path), (current_copy, current_path), (other_copy, other_path)):
			if n != o:
				if not os.path.exists(o):
					warning("Missing provisional conflict file: {0}".format(o))
				else:
					shutil.move(o, n)
					os.chmod(n, stat.S_IREAD|stat.S_IRUSR|stat.S_IRGRP)
		self.provisional  = False
		self._currentPath = current_copy
		self._basePath    = base_copy
		self._otherPath   = other_copy
		return self

	def describe( self ):
		l,c,b,o = self._sigs()
		if not self.conflicts:
			return "Error: no conflicts registered/found"
		if l == c:
			return "No modifications (R%s)" % (self.conflicts.getCurrentInfo()[0])
		elif l == b:
			return "Same as BASE     (R%s)" % (self.conflicts.getBaseInfo()[0])
		elif l == o:
			return "Same as OTHER    (R%s)" % (self.conflicts.getOtherInfo()[0])
		else:
			return "Merged           (R%s+R%s)" % (
				(self.conflicts.getCurrentInfo()[0]),
				(self.conflicts.getOtherInfo()[0])
			)

	def resolve(self):
		self.state = self.RESOLVED

	def unresolve(self):
		self.state = self.UNRESOLVED

	def path( self ):
		return self._path

	def current( self ):
		return self._currentPath

	def base( self ):
		return self._basePath

	def other( self ):
		return self._otherPath

	def get( self, path ):
		if path == "current": return self.current()
		if path == "local":   return self.path()
		if path == "base":    return self.base()
		if path == "other":   return self.other()
		raise Exception("Unknown path type: {0}".format(path))

	def nextMerge(self):
		number = 0
		while os.path.exists(self.path() + ".merge-" + str(number)):
			number += 1
		return self.path() + ".merge-" + str(number)

	def merges(self):
		number = 0
		path   = self.path() + ".merge-" + str(number)
		res	= []
		while os.path.exists(path):
			res.append(path)
			path = self.path() + ".merge-" + str(number)
		return res

	def _read( self, path ):
		# FIXME: The file was removed by accident
		if not os.path.exists(path):
			return ''
		f = file(path, 'r')
		r = f.read()
		f.close()
		return r

	def _sig( self, path ):
		return hashlib.sha256(self._read(path)).hexdigest()

	def _sigs( self ):
		return self._sig(self.path()), self._sig(self.current()), \
		self._sig(self.base()), self._sig(self.other())

	def isResolved( self ):
		return self.state == self.RESOLVED

	def asString( self ):
		a = cutpath(os.path.abspath(os.getcwd()), self.path())
		b = cutpath(os.path.abspath(os.getcwd()), self.current())
		c = cutpath(os.path.abspath(os.getcwd()), self.other())
		d = cutpath(os.path.abspath(os.getcwd()), self.base())
		p = self.state == self.RESOLVED and "R" or " "
		# TODO: Add explanation for resolution (like "same as other")
		s = " " * len(d.rsplit("-",1)[-1])
		return ("%-4s\t%s %s"% ( self.number, a, p,))

	def asExplanation( self ):
		a = cutpath(os.path.abspath(os.getcwd()), self.path())
		b = cutpath(os.path.abspath(os.getcwd()), self.current())
		c = cutpath(os.path.abspath(os.getcwd()), self.other())
		d = cutpath(os.path.abspath(os.getcwd()), self.base())
		p = self.state == self.RESOLVED and "R" or " "
		# TODO: Add explanation for resolution (like "same as other")
		s = u" " * len(d.rsplit("-",1)[-1])
		return (
			u"   %s     ╭───● %s = yours\n"
			u"   %s ▷───│\n"
			u"   %s     ╰───◀ %s ← to merge"
		% (
			s, c.rsplit("-",1)[-1],
			d.rsplit("-",1)[-1],
			s, b.rsplit("-",1)[-1],
		))

	def asCommand( self ):
		loc = cutpath(os.path.abspath(os.getcwd()), self.path())
		cur = cutpath(os.path.abspath(os.getcwd()), self.current())
		oth = cutpath(os.path.abspath(os.getcwd()), self.other())
		bse = cutpath(os.path.abspath(os.getcwd()), self.base())
		res = self.state == self.RESOLVED and "R" or " "
		# TODO: Add explanation for resolution (like "same as other")
		return easyhg.mergetool.review3(cur,loc,oth,run=False)

	def __str__( self ):
		a = cutpath(os.path.abspath(os.getcwd()), self.path())
		b = cutpath(os.path.abspath(os.getcwd()), self.current())
		c = cutpath(os.path.abspath(os.getcwd()), self.base())
		d = cutpath(os.path.abspath(os.getcwd()), self.other())
		p = self.state == self.RESOLVED and "R" or " "
		return "%s%4s : %s : %s : %s : %s : %s" % (p, self.number,
		a,b,c,d,self.description)

# -----------------------------------------------------------------------------
#
# CONFLICTS CLASS
#
# -----------------------------------------------------------------------------

class Conflicts:
	"""This is a utility class that represents the list of conflicts, and
	whether they are resolved or not. It is used by all commands, and makes it
	 to manage the conflicts file."""

	def __init__( self, path="." ):
		# We look for the base directory where the conflicts file is located
		search_path = path = self.root = os.path.abspath(path)
		last_path   = None
		while search_path != last_path:
			conflicts_path = os.path.join(search_path, CONFLICTS_FILE)
			hg_path        = os.path.join(search_path, ".hg")
			if os.path.isfile(conflicts_path): break
			if os.path.isdir(hg_path): break
			last_path   = search_path
			search_path = os.path.basename(last_path)
		# We modify the path to be the search path if we found either a HG repo
		# or a conflicts file
		if last_path != search_path: path = search_path
		# Now we can initialize the object
		self._path        = os.path.join(path, CONFLICTS_FILE)
		self._conflicts   = None
		self._currentInfo = None
		self._baseInfo    = None
		self._otherInfo   = None
		self.load()

	def getCurrentInfo(self):
		return self._currentInfo

	def setCurrentInfo(self, info):
		self._currentInfo = info

	def getBaseInfo(self):
		return self._baseInfo

	def setBaseInfo(self, info):
		self._baseInfo = info

	def getOtherInfo(self):
		return self._otherInfo

	def setOtherInfo(self,info):
		self._otherInfo = info

	def getRevs( self ):
		return hg_get_merge_revisions(os.path.dirname(self._path))

	def load( self ):
		"""Reads the conflicts from the file, if it exists"""
		self._conflicts = []
		revs = hg_get_merge_revisions(os.path.dirname(self._path))
		if not os.path.isfile(self._path):
			self.setCurrentInfo(revs[0])
			if len(revs) < 3:
				return False
			# NOTE: Sometimes we might have more than 3 revisions, not sure
			# what to do then.
			ci, oi, pi =  revs[0:3]
			self.setCurrentInfo(ci)
			self.setBaseInfo(pi)
			self.setOtherInfo(oi)
			return True
		else:
			with open(self._path, "r") as f:
				data = json.load(f)
			self.setCurrentInfo(data["current"])
			self.setBaseInfo(data["base"])
			self.setOtherInfo(data["other"])
			self._conflicts = [
				Conflict.fromJSON(_) for _ in data["conflicts"]
			]
			# If we have no base then we need to expand the conflicts now
			if data["base"] is None and len(revs) >= 3:
				self.setCurrentInfo(revs[0])
				self.setOtherInfo  (revs[1])
				self.setBaseInfo   (revs[2])
				self._conflicts = [_.provision(revs[0], revs[1], revs[2]) for _ in self._conflicts]
				self.save()
			else:
				if len(revs) >= 0:
					self.setCurrentInfo(revs[0])
				else:
					self.setCurrentInfo(("N/A","N/A","N/A"))
				if len(revs) >= 2:
					self.setOtherInfo(revs[1])
				else:
					self.setOtherInfo(("N/A","N/A","N/A"))
				if len(revs) >= 3:
					self.setBaseInfo(revs[2])
				else:
					self.setBaseInfo(("N/A","N/A","N/A"))
				# Sometimes we don't have all this.
				pass
			for c in self._conflicts:
				c.conflicts = self

	def save( self ):
		"""Writes back the conflicts to the file, overwriting it."""
		with open(self._path, "w") as f:
			 json.dump(dict(
				current = self.getCurrentInfo(),
				other   = self.getOtherInfo(),
				base    = self.getBaseInfo(),
				conflicts = [_.toJSON() for _ in self._conflicts]
			), f)

	def all( self ):
		return self._conflicts

	def resolved( self, number=None ):
		"""Returns the list of resolved conflicts"""
		if number == None:
			return filter(lambda c:c.state == Conflict.RESOLVED, self._conflicts)
		else:
			res = filter(lambda c:c.state == Conflict.RESOLVED and c.number == number, self._conflicts)
			if not res: return None
			else: return res[0]

	def unresolved( self, number=None):
		"""Returns the list of unresolved conflicts"""
		if number == None:
			return tuple(c for c in self._conflicts if c.state == Conflict.UNRESOLVED)
		else:
			res = filter(lambda c:c.state == Conflict.UNRESOLVED and c.number == number, self._conflicts)
			if not res: return None
			else: return res[0]

	def register( self, current, base, other ):
		"""Registers a new conflict, which creates provisional files for the
		merge. At this stage, all the revisions are not known (mercurial being
		in the process of merging). The provisional conflicts will be
		completed on the next run when the parents are known."""
		for p in (current, base, other):
			if not os.path.exists(p):
				error("Cannot register conflict as file is missing: {0}".format(p))
				return False
		rev = hg_get_merge_revisions(os.path.dirname(self._path))[0]
		base_provisional     = current + ".base-pro"    + rev[0]
		current_provisional  = current + ".current-pro" + rev[0]
		other_provisional    = current + ".other-pro"   + rev[0]
		shutil.copyfile(base,  base_provisional)
		shutil.copyfile(other, other_provisional)
		shutil.copyfile(current, current_provisional)
		self.add(current, current_provisional, base_provisional, other_provisional, True)

	def add( self, path, currentPath, basePath, otherPath, provisional=False ):
		"""Adds a new conflict between the given files, and returns the conflict
		as a (STATE, ID, FILES) triple."""
		path    = os.path.abspath(path) if path else None
		base    = os.path.abspath(basePath)
		other   = os.path.abspath(otherPath)
		current = os.path.abspath(currentPath)
		next    = 0
		# We do not add a conflict twice
		for c in self._conflicts:
			if  c.path()  != path \
			and c.other() != other:
				next += 1
			else:
				return c
		# Eventually adds the conflict
		next     = len(self.unresolved())
		conflict = Conflict(next, path, current, base, other, provisional=provisional)
		assert other   == conflict.other(), "Internal error"
		assert current == conflict.current(), "Internal error"
		assert base    == conflict.base(), "Internal error"
		self._conflicts.append(conflict)
		return conflict

	def asString(self, color=False):
		# TODO: Use join instead
		res = ""
		unresolved = self.unresolved()
		resolved   = self.resolved()
		# We handle unresolved conflicts
		if unresolved:
			for conflict in unresolved:
				if color:
					res += format(conflict.asString(), color=RED) + "\n"
				else:
					res += conflict.asString() + "\n"
				res += conflict.asCommand() + "\n"
		# And handle resolved conflicts
		if resolved:
			for conflict in resolved:
				if color:
					res += format(conflict.asString(), color=GREEN) + "\n"
				else:
					res += conflict.asString() + "\n"
		# We remove the trailing EOL
		return res[:-1]

	def __str__( self ):
		return self.asString(color=False)

# -----------------------------------------------------------------------------
#
# COMMANDS
#
# -----------------------------------------------------------------------------

class Operations:
	"""Implements operations that can be triggered either from the UI and from
	the command line"""

	def __init__( self, conflicts ):
		self.conflicts = conflicts
		self.color     = True

	def output( self, message ):
		print (message)

	def ask( self, message ):
		return ask(message)

	def error( self, message ):
		error(message)

	def log( self, *args ):
		log(*args)

	def info( self, *args):
		info(*args)

	def format( self, message, **kwargs ):
		return format(message, **kwargs)

	def warning( self, message ):
		warning(message)

	def command( self, command ):
		os.system(command)

	# FIXME
	# def addConflict( self, path, currentPath, basePath, otherPath ):
	# 	"""Adds the given conflict to the list of conflicts (stored in a
	# 	'.hgconflicts' file), in the given root directory."""
	# 	c = self.conflicts.add(path, currentPath, basePath, otherPath)
	# 	self.conflicts.save()
	# 	return c

	def listConflicts( self ):
		"""Lists the conflicts in the given directory."""
		self.output(self.conflicts.asString(self.color))

	def reviewConflict( self, conflict, *args ):
		"""Reviews the given conflict, by comparing its current revision to the
		base revision."""
		if type(conflict) == int:
			conflict = self.getUnresolvedConflict(number)
		if len(args) == 0:
			# NOTE: We don't show the ancestor in the diff3, we show both versions
			# to be merged and the current one.
			easyhg.mergetool.review3( conflict.path(), conflict.current(), conflict.other())
		elif len(args) == 2:
			easyhg.mergetool.review( *[conflict.get(_) for _ in args] )
		elif len(args) == 3:
			easyhg.mergetool.review3( *[conflict.get(_) for _ in args] )
		else:
			error ("Unsupported number or arugments: {0}".format(args))

	def reviewConflictSources( self, conflict ):
		easyhg.mergetool.review3( conflict.current(), conflict.other(), conflict.base())

	def getUnresolvedConflict( self, number ):
		"""Returns an unresolved Conflict instance corresponding to the given
		number, or returns False and takes care of displaying the proper error
		messages."""
		conflicts = self.conflicts
		number    = int(number)
		conflict  = conflicts.unresolved(number)
		if not conflict:
			self.info("No conflict found: %s" % (number))
			return False
		elif conflict.state == Conflict.RESOLVED:
			self.warning("Conflict already resolved. Doing nothing.")
			return False
		return conflict

	def resolveConflictByMerging( self, number ):
		"""Resolves the given conflict by merging the local file with the given
		merge. This fires the mergetool to do
		the merge."""
		conflict = self.getUnresolvedConflict(number)
		if not conflict: return
		paths = {
			"local"   :conflict.path(),
			"current" :conflict.current(),
			"other"   :conflict.other(),
			"base"    :conflict.base(),
		}
		self.log("Resolving conflict", conflict.path() ,"by", self.format("merging",color=BLUE,  weight=BOLD))
		self.info(conflict.asExplanation())
		# FIXME: ASCII error
		# for rev in self.conflicts.getRevs():
		# 	self.info(u"{0} {1} {2}".format(*rev))
		self.log("$ " + conflict.asCommand())
		# TODO: Should add detail about the revision (auth
		easyhg.mergetool.merge3(paths["local"], paths["current"], paths["other"], paths["base"])
		res = self.ask("Did you resolve the conflict (y/n) ? ")
		if res == "y":
			self.info("Conflict resolved")
			conflict.resolve()
		self.conflicts.save()

	def resolveConflictByReplacing( self, number, replaceWith ):
		"""Resolves the conflict by updating the local file with the given
		'replaceWith'"""
		conflict = self.getUnresolvedConflict(number)
		if not conflict: return
		paths = {
			"local"   : conflict.path(),
			"current" : conflict.current(),
			"other"   : conflict.other(),
			"base"    : conflict.base(),
		}
		replace_with = paths.get(replaceWith.lower())
		if not replace_with:
			raise Exception("Unknown merge target: " + replaceWith)
		self.log("Resolving conflict", conflict.path() ,"by",
				self.format("replacing with",color=BLUE,  weight=BOLD),
				replaceWith)
		copy(replace_with, conflict.path())
		res = self.ask("Did you resolve the conflict (y/n) ? ")
		if res == "y":
			self.info("Conflict resolved")
			conflict.resolve()
		self.conflicts.save()

	def resolveConflictByKeepingLocal( self, number, ):
		"""Resolves the conflict by updating the local file."""
		conflict = self.getUnresolvedConflict(number)
		if not conflict: return
		conflict.resolve()
		self.conflicts.save()

	def resolveConflicts( self, *numbers):
		"""Resolves the given list of conflicts"""
		conflicts = self.conflicts
		numbers   = map(int, numbers)
		if not numbers:
			unresolved = conflicts.unresolved()
			if not unresolved:
				warning("No conflict to resolve")
				return
			for conflict in unresolved:
				# FIXME: Add choice of action
				self.resolveConflict(conflict.number)
		else:
			for number in numbers:
				# FIXME: Add choice of action
				self.resolveConflict(number)

	def resolveConflict( self, number, method="merge" ):
		if method == "keep":
			return self.resolveConflictByKeepingLocal(number)
		elif method == "merge":
			return self.resolveConflictByMerging(number)
		elif method == "use":
			error("resolve use expects either 'base', 'other' 'current' or revision number")
		else:
			error("resolve expects a list of conflicts, or a conflict and an action")

	def unresolve( self, *numbers):
		"""Unresolve the given conflicts."""
		conflicts = self.conflicts
		numbers   = map(int, numbers)
		self.warning(
			"NOTE: Unresolving a conflict will revert your conflict"
			" file back to the original state. "
			"However, your current changes will be backed up."
		)
		backups = []
		for number in numbers:
			conflict = conflicts.resolved(number) or conflicts.unresolved(number)
			if not conflict:
				self.error("No resolved conflict with id: %s" % (number))
				continue
			if conflict.state == Conflict.UNRESOLVED:
				self.info("Conflict is already unresolved: %s" % (number))
				continue
			res = self.ask("Do you want to unresolve conflict on %s (y/n) ? " % (conflict.path()))
			if res == "y":
				self.log("Unresolving conflict, using %s as original data" % (conflict.current()))
				if conflict._sig(conflict.path()) not in (conflict._sig(conflict.base()),
				conflict._sig(conflict.other()), conflict._sig(conflict.current())):
					next_merge = conflict.nextMerge()
					self.log("Backing up current resolution conflict as: %s" % (next_merge))
					copy(conflict.path(), next_merge)
					backups.append(next_merge)
				conflict.unresolve()
				copy(conflict.current(), conflict.path())
			else:
				self.log("Conflict left as it is.")
		conflicts.save()
		return backups

	def clean( self ):
		"""Cleans the given directory from the conflict backup files and from the
		conflicts file itself."""
		rootdir = self.conflicts.root
		# If there is a conflicts file, we remove it
		conflicts_file = os.path.join(rootdir, CONFLICTS_FILE)
		to_clean = []
		if os.path.isfile(conflicts_file): to_clean.append(conflicts_file)
		# And we clean the directory
		for root, dirs, files in os.walk(rootdir):
			for name in files:
				if CLEAN_MATCH.match(name):
					path = os.path.join(root, name)
					to_clean.append(cutpath(rootdir, path))
			# if ".hg" in dirs:
			# 	dirs.remove(".hg")
		for _ in to_clean:
			self.info("Cleaning up: " + _)
			os.unlink(_)
		if len(to_clean) == 0:
			self.info("No leftover merge files to cleanup")

# -----------------------------------------------------------------------------
#
# MAIN
#
# -----------------------------------------------------------------------------

def hg_get_revision_info(rev, path="."):
	detail = os.popen("cd '%s' ; hg log -r%s" % (path,rev)).read().decode("utf-8")
	info  = []
	for line in detail.split("\n"):
		if line.startswith("user:"):
			info.append(line[5:].strip())
		elif line.startswith("date:"):
			info.append(line[5:].strip())
	return info

# FIXME: This should not be necessary once I get the proper values from
# Mercurial
def hg_get_merge_revisions(path="."):
	"""Returns a tuple (CURRENT, PARENT, OTHER) where each value is a couple
	(REV, CHANGESET ID)."""
	lines = os.popen("hg --repository {0} id -n".format(path)).read().decode("utf8").split("\n")
	revs  = [_ for _ in lines[0].split("+") if _]
	if len(revs) >= 2:
		ancestor = os.popen( "hg --repository {0} id -n -r'ancestor({1},{2})'".format(path, revs[0], revs[1])).read().decode("utf8")
		revs.append(ancestor.split("\n")[0])
	res   = []
	for rev in revs:
		if rev:
			info = [rev]
			info.extend(hg_get_revision_info(rev, path))
			res.append(info)
	return res

RE_NUMBER = re.compile("\d+")
def run(args):
	"""Runs the command with the given arguments."""
	if not args and urwide:
		ui = ConsoleUI(Conflicts())
		return ui.main()
	root = os.path.abspath(os.getcwd())
	# Command: list [DIRECTORY]
	if len(args) in (1,2) and args[0] == "list":
		if len(args) == 2: root = os.path.abspath(args[1])
		# We list the conflicts in the directory
		ops  = Operations(Conflicts(root))
		ops.listConflicts()
		return 0
	# Command: resolve [CONFLICT...]
	elif len(args) >= 1 and args[0] == "resolve":
		ops       = Operations(Conflicts(root))
		conflicts = []
		actions   = []
		tool      = None
		for i,a in enumerate(args[1:]):
			if RE_NUMBER.match(a):
				conflicts.append([int(a), "merge"])
			elif a[0] == "@":
				tool = a[1:]
			elif a in ("keep", "base", "other", "current"):
				conflicts[-1][1] = a
		if tool: easyhg.mergetool.set(tool)
		# TODO: Implement this properly
		for number, method in conflicts:
			ops.resolveConflict(number, method)
		return 0
	# Command: unresolved CONFLICT...
	elif len(args) >= 2 and args[0] == "unresolve":
		conflicts = args[1:]
		# We list the conflicts in the directory
		ops  = Operations(Conflicts(root))
		ops.unresolve(*conflicts)
		return 0
	# Command: clean [DIRECTORY]
	elif len(args) in (1,2) and args[0].startswith("clean"):
		# The directory to be cleaned up may be given, so we ensure it is
		# present
		if len(args) == 2: root = os.path.abspath(args[1])
		ops  = Operations(Conflicts(root))
		# We clean the directory
		ops.clean()
		return 0
	# Command: commit
	elif len(args) == 1 and args[0] == "commit":
		tip	    = os.popen("hg tip").read()
		success = os.system("hg commit")
		success = os.popen("hg tip").read() != tip
		# We clean the directory
		if success:
			info("Commit successful, cleaning up conflict resolution data.")
			Operations(Conflicts(root)).clean()
			return 0
		else:
			info("Commit aborted, nothing done")
			return -1
	# Command: CURRENT BASE OTHER (invoked by 'hg merge')
	elif len(args) == 3:
		# We prepare the destination paths
		local, base, other = map(os.path.abspath, args)
		info("Registering conflict: {0}".format(cutpath(root, local)))
		# We print the conflict
		cnf  = Conflicts(root)
		ops  = Operations(cnf)
		cnf.register(local, base, other)
		cnf.save()
		info(
			u"You can:\n"
			u"- resolve conflicts   :", PROGRAM_NAME, u"resolve N (keep|update|merge)\n"
			u"- unresolve conflicts :", PROGRAM_NAME, u"unresolve N‥\n"
			u"- list conflicts      :", PROGRAM_NAME, u"list\n"
			u"- commit your merge   :", PROGRAM_NAME, u"commit"
		)
		return 0
	else:
		print (USAGE)
		return -1

if __name__ == "__main__":
	sys.exit(run(sys.argv[1:]))

# EOF - vim: tw=80 ts=4 sw=4 noet
