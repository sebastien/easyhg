#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet fenc=latin-1
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easycommit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                           <sebastien@xprima.com>
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# Creation  : 10-Jul-2006
# Last mod  : 11-Jul-2006
# -----------------------------------------------------------------------------

import sys
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

BLANK = urwid.Text("")

def CLASS(c,f):
	if c.upper() in map(lambda x:x[0], CommandLineUI.PALETTE):
		return urwid.AttrWrap(f,c,c.upper())
	else:
		return urwid.AttrWrap(f,c)

# ------------------------------------------------------------------------------
#
# CURSES INTERFACE
#
# ------------------------------------------------------------------------------

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
		self.content = [
			CLASS('shade', urwid.Divider(":")),
			BLANK,
			CLASS('edit', urwid.Edit( ('label',"Project State : "), "WIP")),
			CLASS('edit', urwid.Edit( ('label',"Commit Type   : "), "FEATURE")),
			CLASS('edit', urwid.Edit( ('label',"Summary       : "), "One line summary")),
			CLASS('divider', urwid.Divider("-")),
			CLASS('text', urwid.Edit( "", "Long description\n\n\n\n\n", multiline=True)),
			CLASS('divider', urwid.Divider("=")),
			CLASS('label', urwid.Text( "Changes to commit")),
			CLASS('divider', urwid.Divider("-")),
			urwid.Pile(map(lambda x:CLASS("checkbox", x), [
				urwid.CheckBox("File asdsadasd "),
				urwid.CheckBox("File asdsadasd "),
				urwid.CheckBox("File asdsadasd "),
				urwid.CheckBox("File asdsadasd "),
				urwid.CheckBox("File asdsadasd "),
			])),
			CLASS('divider', urwid.Divider("_")),
			urwid.GridFlow(map(lambda x:CLASS("button", x),  [
				urwid.Button("Cancel", self.cancel),
				urwid.Button("Save",   self.save),
				urwid.Button("Commit", self.commit),
			]), 10,1,1, 'right') ,
		]
		instruct     = urwid.Text("MERCURIAL - Easycommit %s" % (__version__))
		header       = urwid.AttrWrap( instruct, 'header' )
		listbox      = urwid.ListBox(self.content)
		self.frame   = urwid.Frame(listbox, header)
		urwid.AttrWrap(self.frame, 'background')

	def main(self):
		self.ui = urwid.curses_display.Screen()
		self.ui.register_palette(self.PALETTE)
		self.ui.run_wrapper( self.run )

	def run(self):
		size = self.ui.get_cols_rows()
		while True:
			self.draw_screen( size )
			keys = self.ui.get_input()
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
	
	def footer( self, text ):
		self.frame.footer = CLASS('footer',urwid.Text(text))

	def draw_screen(self, size):
		canvas = self.frame.render( size, focus=True )
		self.ui.draw_screen( size, canvas )

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------

if __name__ == "__main__":
	CommandLineUI().main()

# EOF
