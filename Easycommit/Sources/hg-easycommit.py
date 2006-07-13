#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet fenc=latin-1
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easycommit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                           <sebastien@xprima.com>
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Creation  : 10-Jul-2006
# Last mod  : 13-Jul-2006
# -----------------------------------------------------------------------------

import sys, os, re, time, stat, tempfile

try:
	from mercurial.demandload import demandload
	from mercurial.i18n import gettext as _
except:
	print "Failed to load Mercurial modules."
	sys.exit(-1)

try:
	import urwid
	import urwid.curses_display
except:
	print "URWIS is required. You can get it from <%s>" % (
	"http://excess.org/urwid/")
	sys.exit(-1)

demandload(globals(), 'mercurial.ui mercurial.util mercurial.commands mercurial.localrepo')

__version__ = "0.1.0"
__doc__     = """\
Easycommit is a tool that allows better, richer, more structured commits for
Mercurial. It eases the life of the developers and enhances the quality and
consistency of commits.
"""
# ------------------------------------------------------------------------------
#
# EVENTS
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
# COMMIT OBJECT
#
# ------------------------------------------------------------------------------

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
# CURSES INTERFACE
#
# ------------------------------------------------------------------------------

BLANK     = urwid.Text("")

def CLASS(c,f):
	if c.upper() in map(lambda x:x[0], CommitEditor.PALETTE):
		return urwid.AttrWrap(f,c,c.upper())
	else:
		return urwid.AttrWrap(f,c)

def isKey( key ):
	return key in ("left", "right", "up", "down")

COMMIT_STATES            = ["WIP", "UNSTABLE", "STABLE", "RELEASE"]
COMMIT_TYPES             = ["Feature", "Bugfix", "Refactor"]

TOOLTIP_EDIT_STATE       = "LEFT/- or RIGHT/+ to select a project state: %s" % (" ".join(COMMIT_STATES))
TOOLTIP_EDIT_TYPE        = "LEFT/- or RIGHT/+ to select a commit type: %s" % (" ".join(COMMIT_TYPES))
TOOLTIP_EDIT_SUMMARY     = ""
TOOLTIP_EDIT_DESCRIPTION = ""

DEFAULT_EDIT_STATE       = "WIP"
DEFAULT_EDIT_TYPE        = "Feature"
DEFAULT_EDIT_SUMMARY     = "A one line summary of your commit"
DEFAULT_EDIT_DESCRIPTION = """\
A longer description, where you can give a list of what you changed:

- Added this
- Updated that
- Moved this
- Changed that
"""

class CommitEditor:

	PALETTE = [
		('background',         'dark gray',    'default',    'standout'),
		('header',             'white',        'dark cyan',  'bold'),
		('footer',             'light gray',    'default',  'standout'),
		('info',               'white',        'light gray',  'bold'),
		('shade',              'dark cyan',    'light gray',  'bold'),
		('label',              'light gray',   'default',    'standout'),
		('divider',            'light gray',   'default',    'standout'),
		('edit',               'black',        'default',    'bold'),
		('EDIT',               'dark magenta', 'light gray', 'bold'),
		('text',               'black',        'default',    'bold'),
		('TEXT',               'dark blue',    'light gray', 'bold'),
		('checkbox',           'black',        'default',    'standout'),
		('CHECKBOX',           'dark magenta', 'light gray', 'bold'),
		('button',             'white',        'dark cyan',  'bold'),
		('BUTTON',             'white',        'dark magenta',  'bold'),
	]

	def __init__(self):
		# The commit object
		self.commit            = None
		# We define the basic components
		self.edit_state        = urwid.Edit( ('label',"Project State : "), DEFAULT_EDIT_STATE)
		self.edit_type         = urwid.Edit( ('label',"Commit Type   : "), DEFAULT_EDIT_TYPE)
		self.edit_summary      = urwid.Edit( ('label',"Summary       : "), DEFAULT_EDIT_SUMMARY)
		self.edit_description  = urwid.Edit( "", DEFAULT_EDIT_DESCRIPTION, multiline=True)
		self.edit_state.tooltip = TOOLTIP_EDIT_STATE
		self.edit_type.tooltip  = TOOLTIP_EDIT_TYPE
		self.edit_summary.tooltip  = TOOLTIP_EDIT_SUMMARY
		self.edit_description.tooltip  = TOOLTIP_EDIT_DESCRIPTION
		# We register editing hooks
		self.edit_state.keypress       = self.onEditState
		self.edit_state.keypress       = self.onEditState
		self.edit_type.keypress        = self.onEditType
		self.edit_summary.keypress     = self.onEditSummary
		self.edit_description.keypress = self.onEditDescription
		# We describe the User Interface
		self.pile_commitFiles = urwid.Pile([urwid.Text("No commit data")])
		self.content     = [
			CLASS('shade', urwid.Divider(":")),
			BLANK,
			CLASS('edit', self.edit_state),
			CLASS('edit', self.edit_type),
			CLASS('edit', self.edit_summary),
			CLASS('divider', urwid.Divider("-")),
			CLASS('text', self.edit_description),
			CLASS('divider', urwid.Divider("=")),
			CLASS('label', urwid.Text( "Changes to commit")),
			CLASS('divider', urwid.Divider("-")),
			self.pile_commitFiles,
			CLASS('divider', urwid.Divider("_")),
			urwid.GridFlow(map(lambda x:CLASS("button", x),  [
				urwid.Button("Cancel", self.cancel),
				urwid.Button("Save",   self.save),
				urwid.Button("Commit", self.commit),
			]), 10,1,1, 'right') ,
		]
		instruct     = urwid.Text("MERCURIAL - Easycommit %s" % (__version__))
		header       = urwid.AttrWrap( instruct, 'header' )
		self.listbox = urwid.ListBox(self.content)
		self.frame   = urwid.Frame(self.listbox, header)
		urwid.AttrWrap(self.frame, 'background')

	def updateCommitFiles(self):
		assert self.commit
		widgets = []
		# Function invoked when focusing a checkbox
		def on_focus(c):
			text = c.commitEvent.info()
			if text: self.footer(text=text, info="[v] Review differences")
		# Iterates on evnets and registers checkboxes
		for event in self.commit.events:
			checkbox = urwid.CheckBox("%-10s %s" %(event.name, event.path), state=True)
			checkbox.commitEvent = event
			checkbox.onFocus     = on_focus
			widgets.append(CLASS("checkbox", checkbox))
		self.pile_commitFiles.widget_list = widgets
		self.pile_commitFiles.set_focus(0)

	def main(self, commit ):
		self.commit = commit
		self.updateCommitFiles()
		self.ui = urwid.curses_display.Screen()
		self.ui.register_palette(self.PALETTE)
		self.ui.run_wrapper( self.run )

	def run(self):
		size = self.currentSize = self.ui.get_cols_rows()
		while True:
			self.draw_screen( self.currentSize )
			keys    = self.ui.get_input()
			focused = self.listbox.get_focus()[0]
			if isinstance(focused, urwid.AttrWrap): focused = focused.w
			if isinstance(focused, urwid.Pile):     focused = focused.get_focus()
			# These are URWID extensions to manage tooltip and onFocus
			if hasattr(focused, "tooltip") and focused.tooltip:
				self.footer(info=focused.tooltip)
			if hasattr(focused, "onFocus"):
				focused.onFocus(focused)
			# We handle keys
			if "f1" in keys:
				break
			for k in keys:
				if k == "window resize":
					size = self.ui.get_cols_rows()
					continue
				if focused and k == 'v':
					self.reviewFile(focused.commitEvent)
				else:
					self.frame.keypress( size, k )

	def reviewFile( self, commitEvent ):
		parent_rev = commitEvent.parentRevision()
		fd, path   = tempfile.mkstemp(prefix="hg-easycommit")
		os.write(fd, parent_rev)
		self.footer("Reviewing differences for " + commitEvent.path)
		os.popen("gview -df '%s' '%s'" % (commitEvent.abspath(), path)).read()
		os.close(fd)
		os.unlink(path)

	def cancel( self, e ):
		self.footer("Cancel")

	def save( self, e ):
		self.footer("Save")

	def commit( self, e ):
		self.footer("Commit")

	def keypress(self, size, k):
		pass

	def footer( self, text=None, info=None ):
		content = []
		if text: content.append(CLASS('footer',urwid.Text(text)))
		if info: content.append(CLASS('info',  urwid.Text(info)))
		self.frame.footer = urwid.Pile(content)

	def draw_screen(self, size):
		canvas = self.frame.render( size, focus=True )
		self.ui.draw_screen( size, canvas )
	
	def onEditState( self, size, key ):
		i = COMMIT_STATES.index(self.edit_state.get_edit_text())
		if key == "left" or key == "-":
			i = ( i-1 ) % (len(COMMIT_STATES))
			self.edit_state.set_edit_text(COMMIT_STATES[i])
		elif key == "right" or key == "+":
			i = ( i+1 ) % (len(COMMIT_STATES))
			self.edit_state.set_edit_text(COMMIT_STATES[i])
		else:
			return key

	def onEditType( self, size, key ):
		i = COMMIT_TYPES.index(self.edit_type.get_edit_text())
		if key == "left" or key == "-":
			i = ( i-1 ) % (len(COMMIT_TYPES))
			self.edit_type.set_edit_text(COMMIT_TYPES[i])
		elif key == "right" or key == "+":
			i = ( i+1 ) % (len(COMMIT_TYPES))
			self.edit_type.set_edit_text(COMMIT_TYPES[i])
		else:
			return key

	def onEditSummary( self, size, key ):
		if not isKey(key) \
		and self.edit_summary.get_edit_text() == DEFAULT_EDIT_SUMMARY:
			self.edit_summary.set_edit_text("")
		return self.edit_summary.__class__.keypress( self.edit_summary, size, key) 

	def onEditDescription( self, size, key ):
		if not isKey(key) \
		and self.edit_description.get_edit_text() == DEFAULT_EDIT_DESCRIPTION:
			self.edit_description.set_edit_text("")
		res  = self.edit_description.__class__.keypress( self.edit_description, size, key) 
		text = self.edit_description.get_edit_text()
		while text[-1] == "\n" and len(text) >2 and text[-2] == "\n": text = text[:-1]
		while text.count("\n") < 6: text += "\n"
		text = self.edit_description.set_edit_text(text)
		return res

# ------------------------------------------------------------------------------
#
# MERCURIAL COMMAND REGISTRATION
#
# ------------------------------------------------------------------------------

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
		CommitEditor().main(commit_object)
		# Now we execute the old commit method
		#repo._old_commit( files, text, user, date, match, force, lock, wlock, force_editor )
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
	"commit": ( command_main, [], 'hg commit', "FOU" )
}

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------

if __name__ == "__main__":
	CommitEditor().main(Commit())

# EOF
