#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 et
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easy tools
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                           <sebastien@xprima.com>
# -----------------------------------------------------------------------------
# Creation  : 05-May-2006
# Last mod  : 10-Jul-2007
# -----------------------------------------------------------------------------

import os, sys, re, shutil, difflib, stat, sha
import mergetool
try:
	import urwide, urwid
except:
	urwide = None

__version__ = "0.9.3"
PROGRAM_NAME = os.path.splitext(os.path.basename(__file__))[0]

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

    Mercurial will automatically invoke this command when merging, so that it
    creates three files in the same directory as the ORIGINAL file with
    extensions '.current', '.parent' or '.other' corresponding to copies of the
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

CLEAN_MATCH    = re.compile("^.+\.(current|parent|other|merge|orig)(\.\d+)?$")
CONFLICTS_FILE = ".hgconflicts"

# ------------------------------------------------------------------------------
#
# COLORED TERMINAL OUTPUT
#
# ------------------------------------------------------------------------------

BLACK = "BK"; RED = "RE"; BLUE="BL";  GREEN = "GR"; MAGENTA="MG"; CYAN = "CY"
BROWN = "BW"
PLAIN = ""  ; BOLD = "BOLD" 
CODES = {
  BLACK         :"00;30", BLACK+BOLD    :"01;30",
  RED           :"00;31", RED+BOLD      :"01;31",
  GREEN         :"00;32", GREEN+BOLD    :"01;32",
  BROWN         :"00;33", BROWN+BOLD    :"01;33",
  BLUE          :"00;34", BLUE+BOLD     :"01;34",
  MAGENTA       :"00;35", MAGENTA+BOLD  :"01;35",
  CYAN          :"00;36", CYAN+BOLD     :"01;36",
}

def format( message, color=BLACK, weight=PLAIN ):
  """Formats the message to be printed with the following color and weight"""
  return '[0m[' + CODES[color+weight] + 'm' + str(message) + '[0m'

# -----------------------------------------------------------------------------
#
# LOGGING
#
# -----------------------------------------------------------------------------

def ask( question ):
	print format(question, weight=BOLD) + " ",
	return sys.stdin.readline().lower().strip()

def error( *args ):
	print format("ERROR: ", color=RED, weight=BOLD) + format(
	" ".join(map(str,args)), color=RED)

def warning( *args ):
	print format(" ".join(map(str,args)),MAGENTA)

def info( *args ):
	print format(" ".join(map(str,args)),CYAN)

def log( *args ):
	print " ".join(map(str,args))

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

CONSOLE_STYLE = """\
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
"""

CONSOLE_UI = """\
Hdr MERCURIAL - Easymerge %s

Txt  Easymerge allows you to easily merge two branches.
Txt  Merging is done using the merge tool specified by the MERGETOOL environment variable

Txt  When merging a file (ex: 'src/file.py'), here are some important terms: args:@label
Txt 
Txt  LOCAL/MERGED    -> the file 'src/file.py' as it is on the filesystem args:@label
Txt  CURRENT         -> the file 'src/file.py.current', correspond to the the current version args:@label
Txt  PARENT          -> the file 'src/file.py.parent', corresponding to the parent version args:@label
Txt  OTHER           -> the file 'src/file.py.other', corresponding to the other (pulled/merged) version args:@label

---

Col
    Txt  Path
    Txt Status
    Txt Diff from local to
    Txt 
    Txt 
End

Col                                 #conflicts
    Ple                             #conflict
    End
    Ple                             #state
    End
    Ple                             #current
    End
    Ple                             #parent
    End
    Ple                             #other
    End
End

___

GFl
    Btn [Leave]                                   #btn_leave   &press=leave
    Btn [Commit]                                  #btn_commit  &press=commit
End
""" % (__version__)


ASK_RESOLVED = """
Hdr Conflict resolution

Txt Did you resolve the conflict ?

GFl
    Btn [No]                        #no
    Btn [Yes]                       #yes
End
"""
ASK_UNRESOLUTION = """
Hdr Conflict resolution undo

Txt Unresolving a conflict will change the state of your conflict file
Txt to where it was. This is the equivalent of an `hg revert` on your
Txt conflict file.

Txt However, your changes will be saved in a `.merge` file, so you
Txt can copy it over your current files to redo the resolution.

Txt Would you like to proceed ?

GFl
    Btn [No]                        #no
    Btn [Yes]                       #yes
End
"""

SHOW_MESSAGE = """
Hdr %s

Txt %s

GFl
    Btn [OK]                        #ok
End
"""
class ConsoleUI(urwide.Handler):
	"""Main user interface for easymerge."""

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
		self.ui = urwide.Console()
		self.ui.handler(self)
		self.ui.data.conflicts = conflicts
		self.ui.strings.RESOLVED   = "RESOLVED   [V]iew | [U]nresolve | [Q]uit"
		self.ui.strings.UNRESOLVED = "UNRESOLVED [V]iew | Resolve by [R]eplacing or [M]erging | [Q]uit"

	def main( self ):
		if self.ui.data.conflicts.all():
			self.ui.create(CONSOLE_STYLE, CONSOLE_UI)
			self.updateConflicts()
			self.ui.main()
		else:
			print "No conflicts found."

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
			self.ui._widgets[widget].remove_widgets()
		def add( conflict, parent, *args ):
			widget = self.ui.new(*args)
			if isinstance(widget, urwid.RadioButton):
				widget.on_state_change = self.conflictStateChanged
			self.ui.unwrap(widget).conflict = conflict
			self.ui._widgets[parent].add_widget(widget)
			return widget
		def finish( widget ):
			self.ui._widgets[widget].set_focus(0)
		# We clear the Ple (Piles)
		map(clear, "conflict state current parent other".split())
		# We register the conflicts
		for c in self.ui.data.conflicts.all():
			group = []
			edit  = add(c, "conflict", urwid.Edit, " " + c.path())
			state = add(c, "state",	urwid.Text, (c.state.lower(), c.state))
			cur   = add(c, "current",  urwid.RadioButton, group, "current", False)
			par   = add(c, "parent",   urwid.RadioButton, group, "parent", False)
			oth   = add(c, "other" ,   urwid.RadioButton, group, "other",  False)
			c._ui_state = state
			c._ui_group = group
			for w in (edit, cur, par, oth):
				self.ui.setTooltip(w, c.state.upper())
				self.ui.onKey(w, self.onConflict)
				self.ui.onFocus(w, self.onConflictFocus)
			self._updateConflictView(c)
			#conflict.add_widget(self.ui.wrap(conflict, "@unresolved &key=resolve ?UNRESOLVED"))
		# We notify that the Ple (Piles) construction is finished
		map(finish, "conflict state current parent other".split())

	def _updateConflictView( self, conflict ):
		loc, cur, par, oth = conflict._sigs()
		map(lambda w:w.set_state(False), conflict._ui_group)
		if conflict.getState() == conflict.UNRESOLVED:
			map(lambda w:w.set_state(False), conflict._ui_group)
		else:
			if loc == cur:
				conflict._ui_group[0].set_state( True )
			elif loc == par:
				conflict._ui_group[1].set_state( True )
			elif loc == oth:
				conflict._ui_group[2].set_state( True )

	def onConflictFocus( self, widget ):
		conflict = widget.conflict
		def info( path ):
			if path == conflict.path():
				return "This is the local file"
			sig_local = conflict._sig(conflict.current())
			sig_right = sha.new(conflict._read(path)).hexdigest()
			if sig_local == sig_right: return "Same content as the local file"
			else: return "Not same content as local file: " + sig_right
		if conflict.state == Conflict.RESOLVED:
			self.ui.setInfo(widget, "RESOLVED")
		else:
			self.ui.setInfo(widget, "UNRESOLVED")
		if   widget == conflict._ui_group[0]:
			self.ui.setTooltip(widget, info(conflict.current()))
		elif widget == conflict._ui_group[1]:
			self.ui.setTooltip(widget, info(conflict.parent()))
		elif widget == conflict._ui_group[2]:
			self.ui.setTooltip(widget, info(conflict.other()))
		else:
			self.ui.setTooltip(widget, info(conflict.path()))

	def _unresolveConflict( self, conflict, callback=False ):
		# If the current resolved version was resolved form parent or other, we
		# do not need to save a backup
		if conflict._sig(conflict.path()) in (conflict._sig(conflict.parent()),
		conflict._sig(conflict.other()), conflict._sig(conflict.current())):
			callback = True
		if callback:
			backup = self.ops.unresolve(conflict.number)
			conflict._ui_state.set_text((conflict.state.lower(), conflict.state))
			self._updateConflictView(conflict)
			if backup:
				dialog = urwide.Dialog(self.ui, ui=SHOW_MESSAGE % (
					"Conflict unresolved",
					"Your changes were saved to `%s`" % (backup[0])
				), style=DIALOG_STYLE)
				dialog.onPress(dialog.widgets.ok , lambda x:dialog.end())
				self.ui.dialog(dialog)
		else:
			dialog = urwide.Dialog(self.ui, ui=ASK_UNRESOLUTION, style=DIALOG_STYLE)
			dialog.onPress(dialog.widgets.yes, lambda x:cmp(dialog.end(), self._unresolveConflict(conflict, True)))
			dialog.onPress(dialog.widgets.no , lambda x:dialog.end())
			self.ui.dialog(dialog)
		return True

	def onConflict( self, widget, key ):
		if key in ('left', 'right', 'up', 'down'): return False
		conflict = widget.conflict
		if conflict.state == Conflict.RESOLVED:
			# Undoes the conflict
			if   key == "u":
				self._unresolveConflict(conflict)
			# Reviews what as changed
			elif key == "enter" or key == "v":
				self.ops.reviewConflict(conflict, left="local", right=widget.get_label())
		else:
			# Reviews the conflict
			if   key == "v": 
				self.ops.reviewConflict(conflict, left="local", right=widget.get_label())
			# Merges the parent and other manually
			elif key == "m":
				self.ops.resolveConflictByMerging( widget.conflict.number, widget.get_label())
				self._updateConflictView(conflict)
			elif key == "r":
				self.ops.resolveConflictByReplacing( widget.conflict.number, widget.get_label())
				self._updateConflictView(conflict)
			# Selects the current choice
			elif key == "enter" or key == " ":
				group = conflict._ui_group
				if widget == group[0]: self.onConflict(widget, "m")
				elif widget == group[1]: self.onConflict(widget, "m")
				elif widget == group[2]: self.onConflict(widget, "m")
				else: raise Exception("Unexpected widget: " + str(widget))
				self._updateConflictView(conflict)
			else:
				return False

	def onKeyPress( self, widget, key ):
		if  key == "q":
			self.ui.end() 
			return
		elif key == "c":
			if not self.ui.data.conflicts.unresolved():
				# TODO: Detect if commit was successful or not
				#self.ui.end()
				#res = os.popen("hg commit").read()
				pass
		else:
			return False

	def onLeave( self, widget ):
		self.ui.tooltip("Leave")
		self.ui.end("Don't forget to commit your changes !")


	def onCommit( self, widget ):
		os.system("hg commit")
		self.ui.end()

	# Operations bindings
	# ------------------------------------------------------------------------

	def ask( self, message ):
		return "y"

	def command( self, command ):
		os.popen(command).read()

	def format( self, format, **kwargs ):
		return format(message, **kwargs)

	def log( self, *args ):
		self.ui.info(" ".join(map(str, args)))
		self.ui.draw()

# -----------------------------------------------------------------------------
#
# CONFLICTS CLASS
#
# -----------------------------------------------------------------------------

class Conflict:
	"""Represents a conflict between two files."""

	RESOLVED   = "RESOLVED"
	UNRESOLVED = "UNRESOLVED"
	SEPARATOR  = "--vs--"
	PARENT	 = "parent"
	OTHER	  = "other"
	MERGED	 = "merged"

	def __init__( self, number, path, state=None, description="" ):
		if not state: state = Conflict.UNRESOLVED
		assert type(number) == int
		self.number = number
		self.state  = state
		self._path  = path
		self.description = description

	def getState( self ):
		"""Returns the state for this conflict (Conflict.RESOLVED or
		Conflict.UNRESOLVED)"""
		return self.state

	def resolve(self):
		self.state = self.RESOLVED

	def unresolve(self):
		self.state = self.UNRESOLVED

	def path( self ):
		return self._path

	def current( self ):
		return self._path + ".current"

	def parent( self ):
		return self._path + ".parent"

	def other( self ):
		return self._path + ".other"

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
		return sha.new(self._read(path)).hexdigest()

	def _sigs( self ):
		return self._sig(self.path()), self._sig(self.current()), \
		self._sig(self.parent()), self._sig(self.other())

	def resolutionType( self ):
		assert self.state == self.RESOLVED
		c = self._read(self.path())
		p = self._read(self.parent())
		o = self._read(self.other())
		if c == p:
			return self.PARENT
		elif c == o:
			return self.OTHER
		else:
			return self.MERGED

	@staticmethod
	def parse( line, number=-1 ):
		"""Returns a new conflict from the given conflict string
		representation."""
		line     = line.strip()
		colon    = line.find(":")
		colon2   = line.rfind(":")
		if not line or colon == -1: return
		if colon2 == -1: line +=" "
		number   = line[:colon].strip()
		sep	  = line.find(Conflict.SEPARATOR)
		original = line[colon+1:sep].strip()
		if number.startswith("R"):
			status = Conflict.RESOLVED
			number = number[1:]
		else: status = Conflict.UNRESOLVED
		description = ""
		return Conflict(int(number), original, status, description)

	def asString( self ):
		a = cutpath(os.path.abspath(os.getcwd()), self.path())
		b = cutpath(os.path.abspath(os.getcwd()), self.other())
		p = self.state == self.RESOLVED and "R" or ""
		return "%s%4s: %s %s %s:%s" % (p, self.number, a, self.SEPARATOR, b, self.description)

	def __str__( self ):
		return self.asString()

class Conflicts:
	"""This is a utility class that represents the list of conflicts, and
	whether they are resolved or not. It is used by all commands, and makes it
	easy to manage the conflicts file."""

	def __init__( self, path="." ):
		# We look for the parent directory where the conflicts file is located
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
		self._path = os.path.join(path, CONFLICTS_FILE)
		self._conflicts = None
		self.load()

	def load( self ):
		"""Reads the conflicts from the file, if it exists"""
		self._conflicts = []
		if not os.path.isfile(self._path): return
		f = file(self._path, "rt")
		# We read the lines and fill in the _conflicts list
		for line in f.readlines():
			result = Conflict.parse(line[:-1], number=len(self._conflicts))
			if result: self._conflicts.append(result)
		f.close()

	def save( self ):
		"""Writes back the conflicts to the file, overwriting it."""
		f = file(self._path, "w")
		f.write(str(self))
		f.close()

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

	def add( self, path, other ):
		"""Adds a new conflict between the given files, and returns the conflict
		as a (STATE, ID, FILES) triple."""
		path    = os.path.abspath(path)
		other   = os.path.abspath(other)
		next    = 0
		# We do not add a conflict twice
		for c in self._conflicts:
			if  c.path()  != path \
			and c.other() != other:
				next += 1
			else:
				return c
		# Eventually adds the conflict
		next	 = len(self.unresolved())
		conflict = Conflict(next, path)
		assert other == conflict.other(), "Internal error"
		self._conflicts.append(conflict)
		return conflict

	def asString(self, color=False):
		res = ""
		unresolved = self.unresolved()
		resolved   = self.resolved()
		# We handle unresolved conflicts
		if unresolved:
			for conflict in unresolved:
				if color:
					res += format(str(conflict), color=RED) + "\n"
				else:
					res += str(conflict) + "\n"
		# And handle resolved conflicts
		if resolved:
			for conflict in resolved:
				if color:
					res += format(str(conflict), color=GREEN) + "\n"
				else:
					res += str(conflict) + "\n"
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

	def __init__( self, conflicts ):
		self.conflicts = conflicts
		self.color     = True

	def output( self, message ):
		print message

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

	def addConflicts( self, path, other ):
		"""Adds the given conflict to the list of conflicts (stored in a
		'.hgconflicts' file), in the given root directory."""
		c = self.conflicts.add(path, other)
		self.conflicts.save()
		return c

	def listConflicts( self ):
		"""Lists the conflicts in the given directory."""
		self.output(self.conflicts.asString(self.color))

	def reviewConflict( self, conflict, left="local", right="parent" ):
		"""Reviews the given conflict, by comparing its current revision to the
		parent revision."""
		paths = {
			"local":conflict.path(),
			"current":conflict.current(),
			"parent":conflict.parent(),
			"other":conflict.other()
		}
		assert left in paths.keys()
		assert right in paths.keys()
		mergetool.review(paths[left], paths[right])

	def getUnresolvedConflict( self, number ):
		"""Returns an unresolved Conflict instance corresponding to the given
		number, or returns False and takes care of displaying the proper error
		messages."""
		conflicts = self.conflicts
		number	= int(number)
		conflict  = conflicts.unresolved(number)
		if not conflict:
			self.error("No conflict found: %s" % (number))
			return False
		elif conflict.state == Conflict.RESOLVED:
			self.warning("Conflict already resolved. Doing nothing.")
			return False
		return conflict

	def resolveConflictByMerging( self, number, mergeWith ):
		"""Resolves the given conflict by merging the local file with the given
		merge ('current', 'parent' or 'other'). This fires the mergetool to do
		the merge."""
		conflict = self.getUnresolvedConflict(number)
		if not conflict: return
		if   mergeWith == "current": target = conflict.current()
		elif mergeWith == "parent":  target = conflict.parent()
		elif mergeWith == "other":  target = conflict.other()
		else: raise Exception("Unknown merge target: " + mergeWith)
		self.log("Resolving conflict", conflict.path() ,"by",
				self.format("merging with",color=BLUE,  weight=BOLD),
				target
		)
		mergetool.merge(conflict.path(), target)
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
		if   replaceWith == "current": target = conflict.current()
		elif replaceWith == "parent":  target = conflict.parent()
		elif replaceWith == "other":  target = conflict.other()
		else: raise Exception("Unknown merge target: " + replaceWith)
		self.log("Resolving conflict", conflict.path() ,"by",
				self.format("replacing with",color=BLUE,  weight=BOLD),
				target)
		copy(target, conflict.path())
		res = self.ask("Did you resolve the conflict (y/n) ? ")
		if res == "y":
			self.info("Conflict resolved")
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
				# FIXME: Add choice of actiono
				self.resolveConflict(conflict.number) 
		else:
			for number in numbers:
				# FIXME: Add choice of action
				self.resolveConflict(number) 

	def unresolve( self, *numbers):
		"""Unresolve the given conflicts."""
		conflicts = self.conflicts
		numbers   = map(int, numbers)
		self.warning("NOTE: Unresolving a conflict will revert your conflict"
		+ " file back to the original state.\n"
		+ "However, your current changes will be backed up.")
		backups = []
		for number in numbers:
			conflict = conflicts.resolved(number)
			if not conflict:
				self.error("No resolved conflict with id: %s" % (number))
				continue
			if conflict.state == Conflict.UNRESOLVED:
				self.error("Conflict is already unresolved: %s" % (number))
				continue
			res = self.ask("Do you want to unresolve conflict on %s (y/n) ? " % (conflict.path()))
			if res == "y":
				self.log("Unresolving conflict, using %s as original data" % (conflict.current()))
				if conflict._sig(conflict.path()) not in (conflict._sig(conflict.parent()),
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
		if os.path.isfile(conflicts_file): os.unlink(conflicts_file)
		# And we clean the directory
		for root, dirs, files in os.walk(rootdir):
			for name in files:
				if CLEAN_MATCH.match(name):
					path = os.path.join(root, name)
					self.info("Cleaning up: " + cutpath(rootdir, path) )
					os.unlink(path)
			if ".hg" in dirs: dirs.remove(".hg")

# -----------------------------------------------------------------------------
#
# MAIN
#
# -----------------------------------------------------------------------------

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
		ops  = Operations(Conflicts(root))
		conflicts = filter(lambda c:RE_NUMBER.match(c), args[1:])
		if len(conflicts) == 1:
			conflict = conflicts[0]
			if   len(args) == 2:
				ops.resolveConflict(conflict, "merge")
			elif len(args) == 3:
				action = args[2].lower()
				ops.resolveConflict(conflict, action)
			else:
				error("resolve expects a list of conflicts, or a conflict and an action")
		else:
			# We list the conflicts in the directory
			ops.resolveConflicts(*conflicts)
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
		tip	 = os.popen("hg tip").read()
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
	# Command: ORIGINAL PARENT NEWER
	elif len(args) == 3:
		info("Registering conflict")
		# We prepare the destination paths
		original, parent, other = map(os.path.abspath, args)
		original_copy = original + ".current"
		parent_copy   = original + ".parent"
		other_copy	= original + ".other"
		# We print the conflict
		ops  = Operations(Conflicts(root))
		conflict = ops.addConflicts(original, other_copy)
		print "Conflict %4d:" % (conflict.number)
		print cutpath(root, original), "[" + str(int(diff_count(original, other))) + "%]"
		print "  parent     ", cutpath(root, parent_copy)
		print "  current    ", cutpath(root, original_copy)
		print "  other      ", cutpath(root, other_copy)
		# We backup .orig, .parent and .new that may already be tehre
		try:
			map(ensure_notexists, (parent_copy, original_copy, other_copy))
		except Exception:
			error("Previous conflict files present. Please run", PROGRAM_NAME, "clean")
			return -1
		# And we create the new ones
		shutil.copyfile(original, original_copy)
		shutil.copyfile(parent,   parent_copy)
		shutil.copyfile(other,    other_copy)
		map(lambda p:os.chmod(p, stat.S_IREAD|stat.S_IRUSR|stat.S_IRGRP), (original_copy, parent_copy, other_copy))
		#info("You can resolve conflicts with:", PROGRAM_NAME, "resolve 0 (keep|update|merge)")
		return 0
	else:
		print USAGE
		return -1

if __name__ == "__main__":
	sys.exit(run(sys.argv[1:]))

# EOF
