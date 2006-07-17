#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet fenc=latin-1
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easycommit
# -----------------------------------------------------------------------------
# Author    : Sébastien Pierre                           <sebastien@xprima.com>
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Creation  : 10-Jul-2006
# Last mod  : 15-Jul-2006
# -----------------------------------------------------------------------------

import sys, os, re, time, stat, tempfile
import urwide, urwid

try:
	from mercurial.demandload import demandload
	from mercurial.i18n import gettext as _
except:
	print "Failed to load Mercurial modules."
	sys.exit(-1)

demandload(globals(), 'mercurial.ui mercurial.util mercurial.commands mercurial.localrepo')

__version__ = "0.2.0"
__doc__     = """\
Easycommit is a tool that allows better, richer, more structured commits for
Mercurial. It eases the life of the developers and enhances the quality and
consistency of commits.
"""

# ------------------------------------------------------------------------------
#
# CURSES INTERFACE
#
# ------------------------------------------------------------------------------

CHOICES = {
	"edit_state":["WIP", "UNSTABLE", "STABLE", "RELEASE"],
	"edit_type": ["Feature", "Bugfix", "Refactor"]
}

STYLE = """
Frame         : Dg,  _, SO
header        : WH, DC, BO
footer        : LG,  _, SO
info          : WH, Lg, BO
tooltip       : Lg,  _, SO
shade         : DC, Lg, BO

label         : Lg,  _, SO

Edit          : BL,  _, BO
Edit*         : DM, Lg, BO
Button        : WH, DC, BO
Button*       : WH, DM, BO
Divider       : Lg,  _, SO
CheckBox      : BL,  _, SO
CheckBox*     : DM, Lg, BO

#edit_summary : DM,  _, SO
"""

UI = """\
Hdr MERCURIAL - Easycommit %s
::: @shade

Edt  State         [WIP]            #edit_state  &key=cycle
Edt  Commit Type   [Feature]        #edit_type   &key=cycle
Edt  Name          [$USERNAME]      #edit_user
Edt  Summary       [One line commit summary]     #edit_summary &key=sumUp
---
Edt  [Your project description]     #edit_desc &key=describe &edit=formatDescription multiline=True 
===
Txt  Changes to commit  
---
Ple                                 #changes
End
GFl                                 align=RIGHT
Btn [Cancel]                        #btn_cancel &press=cancel
Btn [Commit]                        #btn_commit &press=commit
End
	""" % (__version__)

class Interface:
	"""Main user interface for easycommit."""

	def __init__(self):
		self.ui = urwide.UI()
		self.defaultHandler = Handler()
		self.ui.handler(self.defaultHandler)
		self.ui.strings.STATES      = "LEFT/- or RIGHT/+ to select a project state"
		self.ui.strings.TYPE        = "LEFT/- or RIGHT/+ to select a project type"
		self.ui.strings.CHANGE      = "[v] review differences"

	def main( self, commit = None ):
		self.ui.parse(STYLE, UI)
		self.ui.DEFAULT_SUMMARY     = self.ui.widgets.edit_summary.get_edit_text()
		self.ui.DEFAULT_DESCRIPTION = self.ui.widgets.edit_desc.get_edit_text()
		self.ui.data.commit = commit
		if commit:
			self.defaultHandler.updateCommitFiles()
		self.ui.main()

	def selectedChanges(self):
		return self.defaultHandler.selectedChanges()

	def commitMessage( self ):
		desc = self.ui.widgets.edit_desc.get_edit_text() 
		desc = desc.replace("\n\n", "\n")
		msg = "%s: %s\n%sChanges type: %s\n" % (
			self.ui.widgets.edit_state.get_edit_text(),
			self.ui.widgets.edit_summary.get_edit_text(),
			desc,
			self.ui.widgets.edit_type.get_edit_text(),
		)
		return msg

	def commitUser( self ):
		return self.ui.widgets.edit_user.get_edit_text()

class Handler(urwide.Handler):
	"""Main event handler."""

	def onSave( self, button ):
		self.ui.tooltip("Save")

	def onCancel( self, button ):
		self.ui.tooltip("Cancel")
		sys.exit(-1)

	def onCommit( self, button ):
		self.ui.tooltip("Commit")
		self.ui.end()

	def onChangeDescription( self, widget, oldtext, newtext ):
		pass

	def onCycle( self, widget, key ):
		name    = self.ui.id(widget)
		choices = CHOICES[name]
		current = choices.index(widget.get_edit_text())
		if key == "left" or key == "-":
			current = ( current-1 ) % (len(choices))
			widget.set_edit_text(choices[current])
		elif key == "right" or key == "+":
			current = ( current+1 ) % (len(choices))
			widget.set_edit_text(choices[current])
		elif key in ("up", "down"):
			return False
		else:
			return True

	def onSumUp( self, widget, key ):
		if hasattr(widget, "_alreadyEdited"): return False
		if key in ("left", "right", "up", "down"): return False
		widget.set_edit_text("")
		widget._alreadyEdited = True
		return False

	def onDescribe( self, widget, key ):
		if key in ("left", "right", "up", "down"):
			return False
		if not hasattr(widget, "_alreadyEdited"):
			widget.set_edit_text("")
			widget._alreadyEdited = True
		return False

	def onFormatDescription( self, widget, previous, text ):
		if previous == text: return False
		# We adjust the text width
		while len(text) > 1 and text[-1] == "\n" and text[-2] == "\n": text = text[:-1]
		while text.count("\n") < 6: text += "\n"
		widget.set_edit_text(text)

	def onChangeInfo( self, widget ):
		self.ui.tooltip(widget.commitEvent.info())

	# SPECIFIC ACTIONS
	# _________________________________________________________________________

	def updateCommitFiles(self):
		commit = self.ui.data.commit
		# Cleans up the existing widgets
		changes = self.ui.widgets.changes
		changes.remove_widgets()
		widgets = []
		# Iterates on evnets and registers checkboxes
		for event in commit.events:
			checkbox = self.ui.new(urwid.CheckBox, "%-10s %s" %(event.name, event.path), True)
			changes.add_widget(self.ui.wrap(checkbox, "?CHANGE &focus=changeInfo"))
			checkbox.commitEvent = event
		self.ui.widgets.changes.set_focus(0)

	def reviewFile( self, commitEvent ):
		parent_rev = commitEvent.parentRevision()
		fd, path   = tempfile.mkstemp(prefix="hg-easycommit")
		os.write(fd, parent_rev)
		self.footer("Reviewing differences for " + commitEvent.path)
		os.popen("gview -df '%s' '%s'" % (commitEvent.abspath(), path)).read()
		os.close(fd)
		os.unlink(path)

	def selectedChanges( self ):
		"""Returns the list of selected change events."""
		events = []
		for checkbox in map(self.ui.unwrap, self.ui.widgets.changes.widget_list):
			if not checkbox.state: continue
			events.append(checkbox.commitEvent)
		return events

# ------------------------------------------------------------------------------
#
# COMMIT OBJECT
#
# ------------------------------------------------------------------------------
# NOTE: We decided to wrap the current Mercurial commit datastructure into an OO
# layer that eases the manipulation of the commit data.

class Commit:
	"""A Commit object contains useful information about a Mercurial commit."""

	def __init__( self, repo ):
		self.events = []
		self.repo   = repo

	def commandInRepo( self, command ):
		"""Executes the given command within the repository, and returns its
		result."""
		cwd = os.getcwd()
		os.chdir(os.path.dirname(self.repo.path))
		res = os.popen(command).read()
		os.chdir(cwd)
		return res

	def hg( self, command ):
		return self.commandInRepo("hg " + command)

	def parent( self ):
		"""Returns the local parent revision number."""
		parent = self.hg("parent").split("\n")[0].split(":")[1].strip()
		return parent

	def __str__( self ):
		return str(self.events)

# ------------------------------------------------------------------------------
#
# COMMIT EVENTS
#
# ------------------------------------------------------------------------------

class Event:
	"""Abstract interface to events that occured while last commit, and related
	in a commit log."""

	CHANGE = "Changed"
	ADD    = "Added"
	REMOVE = "Removed"

	def __init__( self, parent, name, path ):
		"""Creates a new event with the given name and path"""
		self.name   = name
		self.path   = path
		self.parent = parent
		self._cache_info = None

	def parentRevision( self ):
		return None

	def abspath( self ):
		"""Returns the absolute path for this event."""
		return os.path.join(os.path.dirname(self.parent.repo.path), self.path)

	def info( self ):
		"""Returns additional info on the event."""
		return None

	def __repr__( self ):
		return "<Event:%s='%s'>" % (self.name, self.path)

class ChangeEvent( Event ):
	"""A Change event"""

	def __init__( self, parent, path ):
		Event.__init__(self, parent, Event.CHANGE, path)

	def parentRevision( self ):
		return self.parent.hg("cat -r%s '%s'" % (self.parent.parent(), self.abspath()))
		
	def info( self ):
		"""Returns the diffstat information"""
		if self._cache_info: return self._cache_info
		info = self.parent.commandInRepo("hg diff '%s' | diffstat" % (self.path))
		if info[-1] == "\n": info = info[:-1]
		self._cache_info = info
		return self._cache_info

class AddEvent( Event ):
	"""A Add event"""

	def __init__( self, parent, path ):
		Event.__init__(self, parent, Event.ADD, path)

	def info( self ):
		"""Returns the diffstat information"""
		if self._cache_info: return self._cache_info
		st = os.stat(self.abspath())
		st_size  = float(st[stat.ST_SIZE]) / 1024
		st_mtime = time.ctime(st[stat.ST_MTIME])
		info = " %s\n %skb, last modified %s" % (
			os.path.basename(self.path),
			st_size,
			st_mtime
		)
		self._cache_info = info
		return self._cache_info

class RemoveEvent( Event ):
	"""A Remove event"""

	def __init__( self, parent, path ):
		Event.__init__(self, parent, Event.REMOVE, path)

# ------------------------------------------------------------------------------
#
# MERCURIAL COMMAND REGISTRATION
#
# ------------------------------------------------------------------------------

USERNAME = None

def commit_wrapper(repo, files=None, text="", user=None, date=None,
    match=mercurial.util.always, force=False, lock=None, wlock=None,
    force_editor=False):
	"""Replacement for the localrepository commit that intercepts the list of
	changes. This function takes care of firing the """
	assert isinstance(repo, mercurial.localrepo.localrepository),\
	"Easycommit only works with local repositories (for now)"
	# The following is adapted from localrepo.py (commit function)
	# ---------------------------------------------------------------------------
	added     = []
	removed   = []
	deleted   = []
	changed   = []
	if files:
		raise Exception("Explicit files are not supported right now.")
	else:
		changed, added, removed, deleted, unknown = repo.changes(match=match)
	# ---------------------------------------------------------------------------
	# We create a commit object that sums up the information
	commit_object = Commit(repo)
	for c in changed: commit_object.events.append(ChangeEvent(commit_object, c))
	for c in added:   commit_object.events.append(AddEvent(commit_object, c))
	for c in removed: commit_object.events.append(RemoveEvent(commit_object, c))
	if commit_object.events:
		# And we invoke the commit editor
		app = Interface()
		app.ui.strings.USERNAME = USERNAME
		app.main(commit_object)
		files = map(lambda c:c.path, app.selectedChanges())
		# Now we execute the old commit method
		if files:
			repo._old_commit( files, app.commitMessage(), app.commitUser(),
			date, match, force, lock, wlock, force_editor )
	else:
		print "No changes: nothing to commit"

def command_defaults(cmd):
	"""Returns the default option values for the given Mercurial command. This
	was taken from the Tailor conversion script."""
	if hasattr(mercurial.commands, 'findcmd'):
		findcmd = mercurial.commands.findcmd
	else:
		findcmd = mercurial.commands.find
	return dict([(f[1].replace('-', '_'), f[2]) for f in findcmd(cmd)[1][1]])

def command_main( ui, repo, *args, **opts ):
	# Here we swap the default commit implementation with ours
	repo_old_commit            = repo.__class__.commit
	repo.__class__.commit      = commit_wrapper
	repo.__class__._old_commit = repo_old_commit
	global USERNAME ; USERNAME = ui.username()
	# Sets the default commit options
	for key, value in COMMIT_DEFAULTS.items():
		if not opts.has_key(key): opts[key] = value
	# Restores the commit implementation
	mercurial.commands.commit(ui, repo, *args, **opts)
	repo.__class__.commit  = repo_old_commit
	del repo.__class__._old_commit

# This stores the Mercurial commit defaults, that will be used by the
# command_main
COMMIT_DEFAULTS = command_defaults("commit")
cmdtable = {
	"commit": ( command_main, [], 'hg commit', "TODO" )
}

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------


# EOF
