#!/usr/bin/env python
# Encoding: iso-8859-1
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easycommit
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Author    : Sébastien Pierre                           <sebastien@type-z.org>
# -----------------------------------------------------------------------------
# Creation  : 10-Jul-2006
# Last mod  : 30-Jul-2007
# -----------------------------------------------------------------------------

import sys, os, re, time, stat, tempfile
import urwide, urwid
import easyhg.mergetool as mergetool

from mercurial.i18n import gettext as _
import mercurial
import mercurial.commands
import mercurial.localrepo
# FIX for 0.9.4 version of Mercurial
try:
	from mercurial import demandimport
	demandimport.ignore.append('str_util')
except:
	pass

__version__ = "0.9.4"
__doc__     = """\
Easycommit is a tool that allows better, richer, more structured commits for
Mercurial. It eases the life of the developers and enhances the quality and
consistency of commits.
"""

# ------------------------------------------------------------------------------
#
# CONSOLE INTERFACE
#
# ------------------------------------------------------------------------------
DEFAULT_TAGS  = "Fix Feature Update Refactor Experiment Prototype Release Merge Branch Major Minor Experimental".split()
CONSOLE_STYLE = """\
Frame         : WH, DB, SO
header        : WH, DC, BO
footer        : WH, DB, SO
info          : BL, DC, SO
tooltip       : Lg, DB, BO

label         : Lg, DB, SO
title         : WH, DB, BO

Edit          : WH, DB, BO
Edit*         : WH, DM, BO
Button        : LC, DB, BO
Button*       : WH, DM, BO
CheckBox      : Lg, DB, SO
CheckBox*     : Lg, DM, SO
Divider       : DC, DB, SO
Text          : Lg, DB, SO
Text*         : WH, DM, BO

#edit_summary : YL, DB, SO
"""

CONSOLE_UI = """\
Hdr MERCURIAL - Easycommit %s

Edt Name          [$USERNAME]                   #edit_user
Edt Summary       [One line commit summary]     #edit_summary ?SUMMARY &key=sumUp
Edt Tags          [Update]                      #edit_tags    ?TAGS    &key=tag
Dvd ___

Box
  Edt [Commit description]                       #edit_desc    ?DESC &key=describe multiline=True
End
Dvd ___

Ple                                              #changes 
End
Dvd ___

GFl
	Btn [Cancel]                                  #btn_cancel  &press=cancel
	Btn [Commit]                                  #btn_commit  &press=commit
End

	""" % (__version__)

class ConsoleUI:
	"""Main user interface for easycommit."""

	def __init__(self):
		self.ui = urwide.Console()
		self.defaultHandler = ConsoleUIHandler()
		self.ui.handler(self.defaultHandler)
		self.ui.strings.DESC    = "Describe your changes in detail here"
		self.ui.strings.SUMMARY = "Give a one-line summary of your changes"
		self.ui.strings.TAGS    = "Enter tags [+] and [-] to cycle through available tags"
		self.ui.strings.CHANGE  = "[V]iew [C]ommit [S]ave [Q]uit"

	def main( self, commit = None ):
		self.ui.create(CONSOLE_STYLE, CONSOLE_UI)
		self.ui.DEFAULT_SUMMARY     = self.ui.widgets.edit_summary.get_edit_text()
		self.ui.DEFAULT_DESCRIPTION = self.ui.widgets.edit_desc.get_edit_text()
		self.ui.data.commit = commit
		if commit:
			self.defaultHandler.updateCommitFiles()
		return self.ui.main()

	def selectedChanges(self):
		return self.defaultHandler.selectedChanges()

	def commitMessage( self ):
		summ = self.ui.widgets.edit_summary.get_edit_text()
		tags = self.ui.widgets.edit_tags.get_edit_text()
		desc = self.ui.widgets.edit_desc.get_edit_text() 
		if tags: tags = "\n%-12s %s" % ("tags:" , tags.lower())
		msg = "%s\n\n%s%s" % (
			summ,
			desc,
			tags,
		)
		while msg.find("\n\n") != -1: msg = msg.replace("\n\n", "\n")
		return msg

	def commitUser( self ):
		return self.ui.widgets.edit_user.get_edit_text()

class ConsoleUIHandler(urwide.Handler):
	"""Main event handler."""

	def onSave( self, button ):
		self.ui.tooltip("Save")

	def onCancel( self, button ):
		self.ui.tooltip("Cancel")
		self.ui.end("Commit canceled",status=False)

	def onCommit( self, button ):
		self.ui.tooltip("Commit")
		self.ui.end()

	def onSumUp( self, widget, key ):
		if hasattr(widget, "_alreadyEdited"): return False
		if key in ("left", "right", "up", "down", "tab", "shift tab"): return False
		widget.set_edit_text("")
		widget._alreadyEdited = True
		return False

	def isTag( self, tagname ):
		"""Tells wether the given @tagname (as text) is a tag from the
		@DEFAULT_TAGS and returns the indice of the tag in the array. The tag
		matches if on of the @DEFAULT_TAGS start with the given tagname."""
		i = 0
		for tag in DEFAULT_TAGS:
			if tagname.lower() == tag.lower():
				return i
			i += 1
		i = 0
		for tag in DEFAULT_TAGS:
			if tag.lower().startswith(tagname.lower()):
				if i == 0: return len(DEFAULT_TAGS) - 1
				else: return i- 1
			i += 1
		return -1

	def onTag( self, widget, key ):
		# This takes into account tag completion
		if key in ( "+", "-" ):
			if key == "+":
				offset  = 1
				default = -1
			else:
				offset  = -1
				default = 0
			o = widget.edit_pos
			t = widget.get_edit_text()
			current_tag = len(map(lambda x:x.strip(), t[:o].strip().split())) -1
			tags = map(lambda x:x.strip(), t.strip().split())
			if tags:
				i = self.isTag(tags[current_tag])
				i = (i+ offset) % len(DEFAULT_TAGS)
				tooltip = "Available tags: %s [%s] %s" % (
					" ".join(DEFAULT_TAGS[:i]),
					DEFAULT_TAGS[i].upper(),
					" ".join(DEFAULT_TAGS[i+1:])
				)
				self.ui.tooltip(tooltip)
				tags[current_tag] = (DEFAULT_TAGS[i])
			else:
				tags.append(DEFAULT_TAGS[default])
			widget.set_edit_text(" ".join(tags))
			widget._alreadyEdited = True
			return True
		if not hasattr(widget, "_alreadyEdited"):
			if key in ("left", "right", "up", "down", "tab", "shift tab"): return False
			widget.set_edit_text("")
			widget._alreadyEdited = True
			return False
		else:
			return False

	def onDescribe( self, widget, key ):
		if key in ("left", "right", "up", "down", "tab", "shift tab"):
			return False
		if not hasattr(widget, "_alreadyEdited"):
			widget.set_edit_text("")
			widget._alreadyEdited = True
		return False

	def onChangeInfo( self, widget ):
		self.ui.tooltip(widget.commitEvent.info())
		self.ui.info(self.ui.strings.CHANGE)

	def onChange( self, widget, key ):
		if key == "v":
			self.reviewFile(widget.commitEvent)
		else:
			return False

	def onKeyPress( self, widget, key ):
		if key == "q":
			self.onCancel(widget)
		elif key == "s":
			self.onSave(widget)
		elif key == "c":
			self.onCommit(widget)
		return False

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
			self.ui.unwrap(checkbox).commitEvent = event
			changes.add_widget(self.ui.wrap(checkbox, "?CHANGE &focus=changeInfo"))
			self.ui.onFocus(checkbox, "changeInfo")
			self.ui.onKey(checkbox, "change")
		self.ui.widgets.changes.set_focus(0)

	def reviewFile( self, commitEvent ):
		parent_rev = commitEvent.parentRevision()
		fd, path   = tempfile.mkstemp(prefix="hg-easycommit")
		if not parent_rev: parent_rev = ""
		os.write(fd, parent_rev)
		self.ui.tooltip("Reviewing differences for " + commitEvent.path)
		self.ui.draw()
		mergetool.review(commitEvent.abspath(), path)
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
		if info and info[-1] == "\n": info = info[:-1]
		self._cache_info = info or "Diffstat not available"
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
    	force_editor=False,cmdoptions=None):
	"""Replacement for the localrepository commit that intercepts the list of
	changes. This function takes care of firing the """

	assert isinstance(repo, mercurial.localrepo.localrepository),\
	"Easycommit only works with local repositories (for now)"

	# The following is adapted from localrepo.py (commit function)
	# References are mercurial.commands.commit and localrepo.commit

	added     = []
	removed   = []
	deleted   = []
	changed   = []
	if files:
		raise Exception("Explicit files are not supported right now.")
	else:
		changed, added, removed, deleted, unknown, ignored, clean = repo.status(match=match)

	# We create a commit object that sums up the information	

	commit_object = Commit(repo)
	for c in changed: commit_object.events.append(ChangeEvent(commit_object, c))
	for c in added:   commit_object.events.append(AddEvent(commit_object, c))
	for c in removed: commit_object.events.append(RemoveEvent(commit_object, c))
	if commit_object.events:
		# And we invoke the commit editor
		app = ConsoleUI()
		app.ui.strings.USERNAME = USERNAME
		res = app.main(commit_object)
		if not res:
			print "Nothing was commited"
			return
		files = map(lambda c:c.path, app.selectedChanges())
		# Now we execute the old commit method
		if files:
			# This is the old commit prototype
			# def commit(self, files=None, text="", user=None, date=None,
			#			 match=util.always, force=False, lock=None,
			#			 wlock=None,
			#			 force_editor=False, p1=None, p2=None,
			#			 extra={}):
			repo._old_commit( files, app.commitMessage(), app.commitUser(),
			date, match, force, lock, wlock, force_editor )
			# This was necessary for 0.9.3
			print
			print "Easycommit: Commit successful !"
			print
			print os.popen("hg tip").read()
	else:
		print "No changes: nothing to commit"

def command_defaults(ui, cmd):
	"""Returns the default option values for the given Mercurial command. This
	was taken from the Tailor conversion script."""
	import mercurial.commands
	# Mercurial 0.9.1
	if hasattr(mercurial.commands, 'find'):
		findcmd = mercurial.commands.find
	# Mercurial 0.9.3
	elif hasattr(mercurial.commands, 'findcmd'):
		findcmd = mercurial.commands.findcmd
	# Mercurial 0.9.4
	else:
		import mercurial.cmdutil
		findcmd = mercurial.cmdutil.findcmd
	return dict([(f[1].replace('-', '_'), f[2]) for f in findcmd(ui, cmd)[1][1]])

def easy_commit( ui, repo, *args, **opts ):
	"""This is the main function that is called by the 'hg' commands (actually
	through the 'mercurial.commands.dispatch' function)."""
	# Here we swap the default commit implementation with ours
	repo_old_commit            = repo.__class__.commit
	repo.__class__.commit      = commit_wrapper
	repo.__class__._old_commit = repo_old_commit
	global USERNAME ; USERNAME = ui.username()
	new_opts = {}
	for key, value in opts.items(): new_opts[key] = value
	# Sets the default commit options
	for key, value in command_defaults(ui, "commit").items():
		if not opts.has_key(key): opts[key] = value
	# Restores the commit implementation
	new_opts['cmdoptions'] = new_opts
	# Invokes the 'normal' mercurial commit
	mercurial.commands.commit(ui, repo, *args, **new_opts)
	repo.__class__.commit  = repo_old_commit
	del repo.__class__._old_commit

# This may change in the different Mercurial version, maybe we should find a
# better way of doing this.d
COMMIT_COMMAND =  mercurial.commands.table["^commit|ci"]
cmdtable = { "commit": (easy_commit,  COMMIT_COMMAND[1],    COMMIT_COMMAND[2])}

# EOF - vim: tw=80 ts=4 sw=4 noet
