#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet fenc=latin-1
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easycommit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                           <sebastien@xprima.com>
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# Creation  : 10-Jul-2006
# Last mod  : 13-Jul-2006
# -----------------------------------------------------------------------------

import sys, os, re
try:
	import urwid
	import urwid.curses_display
except:
	print "URWIS is required. You can get it from <%s>" % (
	"http://excess.org/urwid/")
	sys.exit(-1)


__version__ = "0.1.0"
__doc__     = """\
Easycommit is a tool that allows better, richer, more structured commits for
Mercurial. It eases the life of the developers and enhances the quality and
consistency of commits.
"""

RE_NOTEOL = re.compile("[^\n]")
BLANK     = urwid.Text("")

def CLASS(c,f):
	if c.upper() in map(lambda x:x[0], CommandLineUI.PALETTE):
		return urwid.AttrWrap(f,c,c.upper())
	else:
		return urwid.AttrWrap(f,c)

def isKey( key ):
	return key in ("left", "right", "up", "down")

# ------------------------------------------------------------------------------
#
# CURSES INTERFACE
#
# ------------------------------------------------------------------------------

COMMIT_STATES            = ["WIP", "UNSTABLE", "STABLE", "RELEASE"]
COMMIT_TYPES             = ["Feature", "Bugfix", "Refactor"]

TOOLTIP_EDIT_STATE       = "LEFT or RIGHT to select a project state: %s" % (" ".join(COMMIT_STATES))
TOOLTIP_EDIT_TYPE        = "LEFT or RIGHT to select a commit type: %s" % (" ".join(COMMIT_TYPES))
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


class CommandLineUI:

	PALETTE = [
		('background',         'dark gray',    'default',    'standout'),
		('header',             'white',        'dark cyan',  'bold'),
		('footer',             'white',    'dark magenta',  'standout'),
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
		for event in self.commit.events:
			stat = os.stat(event.path)
			widgets.append(CLASS("checkbox", urwid.CheckBox("%-10s %s"
			%(event.name, event.path))))
		self.pile_commitFiles.widget_list = widgets
		self.pile_commitFiles.set_focus(0)

	def main(self, args=()):
		if args: self.commit = Commit.fromFile(args[0])
		self.updateCommitFiles()
		self.ui = urwid.curses_display.Screen()
		self.ui.register_palette(self.PALETTE)
		self.ui.run_wrapper( self.run )

	def run(self):
		size = self.currentSize = self.ui.get_cols_rows()
		while True:
			self.draw_screen( self.currentSize )
			keys = self.ui.get_input()
			focused = self.listbox.get_focus()[0]
			if isinstance(focused, urwid.AttrWrap): focused = focused.w
			if hasattr(focused, "tooltip") and focused.tooltip:
				self.footer(focused.tooltip)
			if hasattr(focused, "onFocus"):
				focused.onFocus(focused)
			else:
				self.footer("")

			if "f1" in keys:
				break
			for k in keys:
				if k == "window resize":
					size = self.ui.get_cols_rows()
					continue
				self.frame.keypress( size, k )

	def cancel( self, e ):
		self.footer("Cancel")

	def save( self, e ):
		self.footer("Save")

	def commit( self, e ):
		self.footer("Commit")

	def keypress(self, size, k):
		pass
	
	def footer( self, text, *args ):
		if args: text = str(text) + " " + " ".join(map(str, args))
		if not text:
			self.frame.footer = None
		else:
			self.frame.footer = CLASS('footer',urwid.Text(text))

	def draw_screen(self, size):
		canvas = self.frame.render( size, focus=True )
		self.ui.draw_screen( size, canvas )
	
	def onEditState( self, size, key ):
		i = COMMIT_STATES.index(self.edit_state.get_edit_text())
		if key == "left" or key == "-":
			i = ( i-1 ) % (len(COMMIT_STATES))
			self.edit_type.set_edit_text(COMMIT_TYPES[i])
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
			self.edit_summary.set_edit_text(RE_NOTEOL.sub(" ", DEFAULT_EDIT_SUMMARY))
		return self.edit_summary.__class__.keypress( self.edit_summary, size, key) 

	def onEditDescription( self, size, key ):
		if not isKey(key) \
		and self.edit_description.get_edit_text() == DEFAULT_EDIT_DESCRIPTION:
			self.edit_description.set_edit_text(RE_NOTEOL.sub("", DEFAULT_EDIT_DESCRIPTION))
		return self.edit_description.__class__.keypress( self.edit_description, size, key) 

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

	def __init__( self, name, path ):
		"""Creates a new event with the given name and path"""
		self.name = name
		self.path = path

class ChangeEvent( Event ):
	"""A Change event"""

	def __init__( self, path ):
		Event.__init__(self, Event.CHANGE, path)

	def __repr__( self ):
		return "<Event:%s='%s'>" % (self.name, self.path)

class AddEvent( Event ):
	"""A Add event"""

	def __init__( self, path ):
		Event.__init__(self, Event.ADD, path)

class RemoveEvent( Event ):
	"""A Remove event"""

	def __init__( self, path ):
		Event.__init__(self, Event.REMOVE, path)

EVENTS_BY_NAME = {
	"changed":ChangeEvent,
	"removed":RemoveEvent,
	"added"  :AddEvent,
}

# ------------------------------------------------------------------------------
#
# COMMIT OBJECT
#
# ------------------------------------------------------------------------------

class Commit:
	"""A Commit object contains useful information about a Mercurial commit."""

	RE_LINE = re.compile("^HG: (\w+) (.+)$")

	def __init__( self ):
		self.events = []
	
	@staticmethod
	def fromFile( path ):
		"""Creates a commit instance from the commit log at the given path."""
		commit      = Commit()
		commit_file = file(path, 'r')
		for line in commit_file:
			match = Commit.RE_LINE.match(line)
			if not match: continue
			operation, path = match.groups()
			if not operation in EVENTS_BY_NAME.keys():
				raise Exception("Unknown commit operation: " +operation)
			commit.events.append(EVENTS_BY_NAME[operation](path))
		commit_file.close()
		return commit

	def __str__( self ):
		return str(self.events)

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------

if __name__ == "__main__":
	CommandLineUI().main(sys.argv[1:])

# EOF
