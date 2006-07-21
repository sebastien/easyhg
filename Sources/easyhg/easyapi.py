#!/usr/bin/python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 fenc=latin-1 noet
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easy tools
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Author    : Sébastien Pierre                           <sebastien@xprima.com>
# -----------------------------------------------------------------------------
# Creation  : 21-Jul-2006
# Last mod  : 21-Jul-2006
# -----------------------------------------------------------------------------

import os, string, time
import mercurial.ui

__doc__ = """\
This modules wraps parts of Mercurial API with an OO layer that makes
manipulation easier, and will lower the possibilities of breakage whenever the
Mercurial API changes.

The reason for this API is that the current Mercurial API can be tedious to use,
and that it would be too radical to start patching it.
"""
# ------------------------------------------------------------------------------
#
# UTILITY FUNCTIONS
#
# ------------------------------------------------------------------------------

def expand_path( path ):
	"""Expands env variables and ~ symbol into the given path, and makes it
	absolute."""
	path = os.path.expanduser(path)
	path = string.Template(path).substitute(os.environ)
	return os.path.abspath(path)

def update_configuration( path, values ):
	"""Updates the [project] section of the Mercurial configuration to be filled
	with the given set of values. If the section does not exist, it will be
	appended, if it already exists, it will be rewrited."""
	# The given configuration file may not exist
	if not os.path.isfile(path): text = ""
	else: f = open(path, 'r') ; text = f.read() ; f.close()
	result          = []
	current_section = None
	sections        = {}
	# For every line of the Mercurial RC file
	for line in text.split("\n"):
		# If we are in a section, we log it
		if line.strip().startswith("["):
			current_section = line.strip()[1:-1].strip().lower()
			result.append(line)
			last_section = {}
			sections[current_section] = True
			# We take care of the paths.default-push
			if current_section == "paths" and values.get("parent"):
				result.append("default-push = %s" % (values["parent"]))
		# We skip the [project] section
		elif current_section == "project":
			for key, value in values.items():
				result.append("%s = %s" % (key, value))
			current_section = "SKIP"
		# We skip the [paths] default-push
		elif current_section == "paths" and values.get("parent"):
			if line.strip().lower().startswith("default-push"): pass
			else: result.append(line)
		elif current_section == "SKIP":
			pass
		else:
			result.append(line)
	# If there was no project section, we create it
	if not sections.get("project"):
		result.append("[project]")
		for key, value in values.items():
			result.append("%s = %s" % (key, value))
	# We add a paths sections with default-push if necessary
	if not sections.get("paths") and values.get("parent"):
		result.append("[paths]")
		result.append("default-push = %s" % (values["parent"]))

	text = "\n".join(result)
	f = open(path, 'w') ; f.write(text) ; f.close()
	# Returns the result as text
	return text

# ------------------------------------------------------------------------------
#
# REPOSITORIES
#
# ------------------------------------------------------------------------------

class RepositoryException(Exception): pass
class Repository:
	"""The Repository class abstracts Mercurial repositories under a simple API
	and allows to make the distinction between the Central and Working
	repository.

	This class was designed to easily give important information about a
	repository (tags, changes), in a format that can be easily used by UIs."""

	@staticmethod
	def locate( path="." ):
		"""Locates a directory which may be in the given path, or in any
		ancestor of this path."""
		path = os.path.abspath(path)
		print path
		old_path = None
		while old_path != path:
			hg_path  = os.path.join(path, ".hg")
			if os.path.isdir(hg_path): return path
			old_path = path
			path     = os.path.dirname(path)
		return None

	def __init__(self, path=None, repo=None, ui=None):
		"""Creates a new Repository wrapper for a repository at the given path,
		or for the given repository instance. If a Mercurial UI is given, it
		will be used, otherwise it will be created."""
		# We remove the .hg from the path, if present
		# We initialize the UI first
		if ui:
			self_ui	= ui
		# We have to use this trick to make sure the UI configuration is loaded
		# from the repository path, and not from the current location
		else:
			oldrc_path = mercurial.ui.util._rcpath 
			p = path or repo.path
			if p.endswith("hgrc"): pass
			elif p.endswith(".hg"): p = os.path.join(p, "hgrc")
			else: p = os.path.join(p, ".hg", "hgrc")
			mercurial.ui.util._rcpath = p
			self._ui   = mercurial.ui.ui(quiet=True)
			mercurial.ui.util._rcpath = oldrc_path
		# And then the repository
		if repo:
			self._repo = repo
		else:
			self._path = self._ui.expandpath(path)
			if self._path.endswith(".hg"):
				self._path = os.path.dirname(self._path)
			self._repo = mercurial.hg.repository(self._ui, self._path)
		# Configuration
		self._updated	  = {}

	# ACCESSORS
	# _________________________________________________________________________

	def path(self):
		return expand_path(self._path)

	def count( self ):
		"""Returns the number of changes in this repository."""
		return self._repo.changelog.count()

	def changes( self, n=None ):
		"""Yields the n (all by default) latest changes in this
		repository. Each change is returned as (author, date, description, files)"""
		changes_count = self._repo.changelog.count()
		if n == None: n = changes_count
		for i in range(min(n,changes_count)):
			# We get the changeset node
			changeset_ref = self._repo.changelog.node(changes_count - i - 1)
			yield self._changesetInfo(changeset_ref)

	def tags( self ):
		"""Returns tag name, rev and date for each tag within this repository."""
		tags = []
		for name, ref in self._repo.tagslist():
			cauthor, ctime, cdate, desc, cfiles = self._changesetInfo(ref)
			tags.append((name, self._repo.changelog.rev(ref), cdate))
		tags.reverse()
		return tags

	# OPERATIONS
	# _________________________________________________________________________

	def saveConfiguration( self ):
		"""Updates this repository configuration file to reflect the changes
		made to this repository properties."""
		if not self._updated: return
		values = {}
		for key, value in self._ui.configitems("project"): values[key] = value
		for key, value in self._updated.items(): values[key] = value
		hgrc = os.path.join(self._path, ".hg", "hgrc")
		update_configuration(hgrc, values)

	# UTILITIES
	# _________________________________________________________________________

	def _changesetInfo( self, ref ):
		"""Returns informations on the given change set."""
		changeset  = self._repo.changelog.read(ref)
		cid, cauthor, ctime, cfiles, cdesc = changeset
		cauthor = cauthor.strip()
		cdate	 = time.strftime('%d-%b-%Y', time.gmtime(ctime[0]))
		cdesc	 = cdesc.replace("'", "''").strip()
		return cauthor, ctime, cdate, cdesc, cfiles

	def _property( self, name, value = None, add=False ):
		"""Gets a property set in this project configuration"""
		section, property = name.split(".")
		if value == None:
			return self._ui.config(section, name)
		else:
			if add:
				p = self._property(name)
				if p: self._property(name, p + ", " + value)
				else: self._property(name, value)
			else:
				self._ui.setconfig(section, property, value)
				assert self._property(name) == value
				self._updated[name]

	def _properties( self, value=None ):
		"""Sets a property in this project configuration"""
		return map(string.strip, str(self._property(value)).split())

# EOF
