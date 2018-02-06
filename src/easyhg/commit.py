#!/usr/bin/env python
# Encoding: utf8
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easycommit
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Author    : Sébastien Pierre                           <sebastien@type-z.org>
# -----------------------------------------------------------------------------
# Creation  : 10-Jul-2006
# Last mod  : 22-Jan-2017
# -----------------------------------------------------------------------------

import sys, os, re, time, stat, tempfile, json
import easyhg.mergetool as mergetool
from   copy import copy
from   fnmatch import fnmatch
import urwide, urwid
from   mercurial.i18n import gettext as _
import mercurial.match
import mercurial.commands
import mercurial.cmdutil
import mercurial.localrepo
from easyhg.output import *

# TODO: Support --amend
# FIXME: When .hgsubstate has changed
# FIX for 0.9.4 version of Mercurial
try:
	from mercurial import demandimport
	demandimport.ignore.append('str_util')
except:
	pass

__version__ = "0.9.8"
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
DEFAULT_TAGS  = [
	"Release",
	"New",
	"Update",
	"Change",
	"Feature",
	"Refactor",
	"Fix",
	"WIP"
	"Merge",
	"Submodules",
]

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

Edt Name          [$USERNAME]               #edit_user
Edt Tags          [Update]                  #edit_tags    ?TAGS    &key=tag
Edt Scope         [‥]                       #edit_scope   ?SCOPE   &key=scope
Edt Summary       [‥]                       #edit_summary ?SUMMARY &key=sumUp
Dvd ___

Box
  Edt [‥]                                   #edit_desc    ?DESC &key=describe multiline=True
End

Dvd ___

Ple                                         #changes
End
Dvd ___

GFl
	Btn [Cancel]                            #btn_cancel  &press=cancel
	Btn [Commit]                            #btn_commit  &press=commit
End

	""" % (__version__)

class ConsoleUI:
	"""Main user interface for commit."""

	def __init__(self):
		self.ui = urwide.Console()
		self.defaultHandler = ConsoleUIHandler()
		self.ui.handler(self.defaultHandler)
		self.ui.strings.DESC    = "Describe your changes in detail here"
		self.ui.strings.SUMMARY = "Give a one-line summary of your changes"
		self.ui.strings.TAGS    = "Enter tags [+] and [-] to cycle through available tags"
		self.ui.strings.SCOPE   = "Enter the scope of the the change"
		self.ui.strings.CHANGE  = "[V]iew [C]ommit [S]ave [Q]uit"

	def main( self, commit = None ):
		self.ui.create(CONSOLE_STYLE, CONSOLE_UI)
		message = (commit.load() if commit else {}) or {}
		self.ui.DEFAULT_SUMMARY     = message.get("summary")     or self.ui.widgets.edit_summary.get_edit_text()
		self.ui.DEFAULT_DESCRIPTION = message.get("description") or self.ui.widgets.edit_desc.get_edit_text()
		self.ui.DEFAULT_SCOPE       = message.get("scope")       or self.ui.widgets.edit_scope.get_edit_text()
		if commit and len(commit.revs) > 1:
			self.ui.DEFAULT_TAGS = "[Merge]"
		self.ui.data.commit = commit
		if commit:
			if commit.changed(".hgsub*") or commit.added(".hgsub*") or commit.empty():
				self.ui.widgets.edit_tags.set_edit_text("Submodules")
			self.defaultHandler.updateCommitFiles()
		return self.ui.main()

	def selectedChanges(self):
		return self.defaultHandler.selectedChanges()

	def commitMessage( self, json=False ):
		summ  = self.ui.widgets.edit_summary.get_edit_text()
		scope = self.ui.widgets.edit_scope.get_edit_text()
		tags  = self.ui.widgets.edit_tags.get_edit_text()
		desc  = self.ui.widgets.edit_desc.get_edit_text()
		if scope.startswith("‥"): scope = ""
		if desc.startswith("‥"):  desc  = ""
		if tags:
			tags = [_.strip() for _ in tags.split() if _.strip]
		if json:
			return dict(
				summary     = summ,
				scope       = scope,
				tags        = tags,
				description = desc
			)
		else:
			if tags:
				tags = "".join("[{0}]".format(_) for _ in tags)
			msg = "{0} {1}{2}{3}".format(
				tags,
				scope + ": " if scope else "",
				summ,
				"\n\n" + desc if desc else ""
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
		widget.set_edit_text("" + (key if len(key) == 1 else ""))
		widget._alreadyEdited = True

	def onScope( self, widget, key ):
		return self.onSumUp(widget, key)

	def onDescribe( self, widget, key ):
		return self.onSumUp(widget, key)

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

	def onChangeInfo( self, widget ):
		self.ui.tooltip(widget.commitEvent.info())
		self.ui.info(self.ui.strings.CHANGE)

	def onChange( self, widget, key ):
		if key == "v":
			self.reviewFile(widget.commitEvent)
		else:
			return False

	def onKeyPress( self, widget, key ):
		if key in ("q", "esc"):
			self.onCancel(widget)
		elif key == "s":
			self.onSave(widget)
		elif key == "c":
			self.onCommit(widget)
		else:
			return False

	# SPECIFIC ACTIONS
	# _________________________________________________________________________

	def updateCommitFiles(self):
		commit = self.ui.data.commit
		# Cleans up the existing widgets
		changes = self.ui.widgets.changes
		urwide.remove_widgets(changes)
		widgets = []
		# Iterates on evnets and registers checkboxes
		for event in commit.events:
			checkbox = self.ui.new(urwid.CheckBox, "%-10s %s" %(event.name, event.path), True)
			self.ui.unwrap(checkbox).commitEvent = event
			urwide.add_widget(changes, self.ui.wrap(checkbox, "?CHANGE &focus=changeInfo"))
			self.ui.onFocus(checkbox, "changeInfo")
			self.ui.onKey(checkbox, "change")
		if commit.events:
			# When only the .hgsubstate has changed, we might have 0 events
			self.ui.widgets.changes.set_focus(0)

	def reviewFile( self, commitEvent ):
		parent_rev = commitEvent.parentRevision()
		fd, path   = tempfile.mkstemp(prefix="hg-commit")
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

	def __init__( self, repo, revs=None ):
		self.events  = []
		self.repo    = repo
		self.revs    = revs

	def load( self, path=".hgcommit" ):
		if os.path.exists(path):
			rev = self.current()
			with open(path) as f:
				try:
					message = json.load(f)
					if "rev" in message and message.get("rev") != rev:
						message = None
				except ValueError as e:
					message = None
			if not message:
				os.unlink(path)
			return message
		else:
			return None

	def save( self, scope=None, tags=None, summary=None, description=None, path=".hgcommit"):
		message = {
			"scope":scope,
			"tags":tags,
			"description":description,
			"summary":summary,
			"rev":self.current(),
			}
		with open(path, "w") as f:
			json.dump(message, f)
		return message

	def changed( self, match=None ):
		return [_ for _ in self.events if isinstance(_, ChangeEvent) and _.match(match)]

	def removed( self, match=None ):
		return [_ for _ in self.events if isinstance(_, RemoveEvent) and _.match(match)]

	def added( self, match=None ):
		return [_ for _ in self.events if isinstance(_, AddEvent) and _.match(match)]

	def empty( self ):
		return len(self.events) == 0

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

	def current(self):
		return self.revs

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

	def match( self, expr ):
		if expr is None:
			return True
		else:
			return expr == self.path or fnmatch(self.path, expr)

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
		if os.path.isfile(self.abspath()):
			st = os.stat(self.abspath())
			st_size  = float(st[stat.ST_SIZE]) / 1024
			st_mtime = time.ctime(st[stat.ST_MTIME])
			info = " %s\n %skb, last modified %s" % (
				os.path.basename(self.path),
				st_size,
				st_mtime
			)
		else:
			info = " Symbolic link to: " + os.popen("readlink '%s'" % (self.abspath())).read()
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
OPTIONS  = None

def commit_wrapper(repo, message, user, date, match, **kwargs):
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
	ignored   = []
	cleaned   = []

	hgsub = os.path.join(repo.root, ".hgsub")
	if os.path.exists(hgsub):
		with open(hgsub) as f:
			for sub in f.readlines():
				if sub.strip().startswith("#"): continue
				sub = sub.split("=",1)[0].strip()
				if not sub: continue
				subid = os.popen("hg id -n --repository '{0}'".format(sub)).read().split("\n")[0]
				if subid.endswith("+"):
					error("Subrepository has uncommited changed: {0}".format(sub))
					info("run: hg easycommit --repository {0}".format(sub))
					return None
				else:
					info("Subrepository has not changed: {0}".format(sub))

	rev = os.popen("hg id -n --repository '{0}'".format(repo.root)).read().split("\n")[0].split(" ")[0]
	revs = ["tip" if _ == "-1" else _ for _ in rev.split("+") if _.strip]

	if rev[-1] != "+":
		return None

	changes = repo.changectx(revs[0])
	ch, ad, rm, dt, un, ig, cl = changes.status()
	changed += ch
	added   += ad
	deleted += ad
	removed += rm
	ignored += ig
	cleaned += cl

	# We create a commit object that sums up the information
	commit_object = Commit(repo, revs=revs)
	for c in changed: commit_object.events.append(ChangeEvent(commit_object, c))
	for c in added:   commit_object.events.append(AddEvent(commit_object, c))
	for c in removed: commit_object.events.append(RemoveEvent(commit_object, c))

	# And we invoke the commit editor
	app = ConsoleUI()
	app.ui.strings.USERNAME = USERNAME
	res = app.main(commit_object)
	if not res:
		info("Nothing was commited")
		return
	files = map(lambda c:c.path, app.selectedChanges())
	# FIXME: We might want to create a new match here
	# Now we execute the old commit method
	if files:
		if len(files) != len(commit_object.events):
			match = mercurial.match.match(repo.root, repo.root, patterns=files,exact=True)
		message  = app.commitMessage()
		user     = app.commitUser()
		kwargs   = copy(kwargs)
		kwargs["editor"] = None
		commit_object.save(**app.commitMessage(json=True))
	# FIXME: For some reason that does not work for amend
	return repo._old_commit( message, user, date, match, **kwargs )

def command_defaults(ui, cmd):
	"""Returns the default option values for the given Mercurial command. This
	was taken from the Tailor conversion script."""
	defaults = mercurial.cmdutil.findcmd(cmd, mercurial.commands.table)
	return dict([(f[1].replace('-', '_'), f[2]) for f in defaults[1][1]])

def _commit( ui, repo, *args, **opts ):
	"""This is the main function that is called by the 'hg' commands (actually
	through the 'mercurial.commands.dispatch' function)."""
	# Here we swap the default commit implementation with ours
	commit_message = opts.get("message")
	global USERNAME ; USERNAME = ui.username()
	global OPTIONS
	if not commit_message:
		repo_old_commit            = repo.__class__.commit
		repo.__class__.commit      = commit_wrapper
		repo.__class__._old_commit = repo_old_commit
		new_opts = copy(opts)
		# Sets the default commit options
		for key, value in command_defaults(ui, "commit").items():
			if not opts.has_key(key): opts[key] = value
		# Restores the commit implementation
		new_opts['cmdoptions'] = new_opts
		OPTIONS = new_opts
		# Invokes the 'normal' mercurial commit
		mercurial.commands.commit(ui, repo, *args, **new_opts)
		repo.__class__.commit  = repo_old_commit
		del repo.__class__._old_commit
	else:
		new_opts = opts
		mercurial.commands.commit(ui, repo, *args, **new_opts)

# SEE: https://www.mercurial-scm.org/wiki/WritingExtensions
cmdtable       = {}
command        = mercurial.cmdutil.command(cmdtable)
COMMIT_COMMAND =  mercurial.commands.table["^commit|ci"]

@command('easycommit', COMMIT_COMMAND[1])
def commit( *args, **kwargs ):
	return _commit(*args, **kwargs)

# EOF - vim: tw=80 ts=4 sw=4 noet
