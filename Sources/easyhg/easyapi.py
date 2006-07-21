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

import os, string, time, re, tempfile
import mercurial.ui, mercurial.hg, mercurial.localrepo, mercurial.sshrepo

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

class Configuration:
	"""This is a wrapper around a Mercurial repository configuration file that
	allows to easily update specific values, while keeping the configuration
	file as it is."""

	class NotFound(Exception): pass
	class CannotSave(Exception): pass
	class RepositoryNotSupported(Exception): pass

	SECTION  = "section"
	PROPERTY = "property"
	OTHER    = "other"

	RE_SECTION  = re.compile("^\s*\[\s*([^]]+)\s*\]\s*$")
	RE_PROPERTY = re.compile("^\s*([\w_\.]+)\s*=(.*)$")

	def __init__( self, repo=None ):
		self._currentSection = None
		self._lines          = []
		self._sections       = [("",[])]
		self._repo           = repo
		self._updated        = {}
		self.parse(repo)

	def section( self, name ):
		for section, contents in self._sections:
			if section == name:
				return contents
		return None

	def update( self, sectionName, name, value, replace=True, create=True ):
		assert sectionName, name
		section = self.section(sectionName)
		if section:
			for property_value in section:
				if property_value[0] == name:
					if not replace: return
					self._updated["%s.%s" % (sectionName, name)] = value
					property_value[1] = value
					return
			self._updated["%s.%s" % (sectionName, name)] = value
			section.append([name, value])
		elif create:
			self._sections.append((sectionName, [[name, value]]))
		else:
			return None

	def isUpdated( self ):
		"""Tells wether this configuration was updated since the last saving."""
		return self._updated

	def get( self, section, name ):
		section = self.section(section)
		if not section: return None
		for _property, value in section:
			if _property == name:
				return value
		return None

	def mget( self, section, name ):
		value = self.get(section, name)
		return map(string.strip, value.split(","))

	def parse( self, repo ):
		if not repo: return
		self._content        = []
		current_section      = self._sections[0]
		text                 = self.read()
		# The main parsing strategy
		for line in text.split("\n"):
			is_section  = self.RE_SECTION.match(line)
			is_property = self.RE_PROPERTY.match(line)
			if   is_section:
				section_name = is_section.group(1)
				current_section = self.section(section_name)
				assert section_name
				if current_section == None:
					current_section = []
					self._sections.append((section_name, current_section))
			elif is_property:
				current_section.append([is_property.group(1), is_property.group(2)])
			elif current_section == "SKIP":
				current_section.append(["", line])

	def asString( self ):
		res = []
		for section, values in self._sections:
			if not section and not values: continue
			if section:
				res.append("[%s]" % (section))
			else:
				res.append("")
			for name, value in values:
				if name:
					res.append("%s=%s" % (name, value))
				else:
					res.append(value)
		return "\n".join(res)

	def read( self ):
		if self._repo.isSSH():
			hgrepo  = self._repo.hgrepo()
			sshcmd  = self._repo._ui.config("ui", "ssh", "ssh")
			sshcmd += " " + self._repo.isSSH()
			# Touches and reads the hgrc configuration
			os.popen("%s touch '%s'" % (sshcmd, self._repo.configpath()))
			r = os.popen("%s cat '%s'" % (sshcmd, self._repo.configpath())).read()
			return r
		elif self._repo.isLocal():
			if not os.path.exists(self._repo.configpath()): return ""
			f = file(self._repo.configpath(), 'r')
			r = f.read()
			f.close()
			return r
		else:
			raise self.RepositoryNotSupported(repr(self._repo.hgrepo()))

	def save( self, path=None ):
		if self._repo.isSSH():
			sshcmd  = self._repo._ui.config("ui", "ssh", "ssh")
			sshcmd += " " + self._repo.isSSH()
			# Backs up the existing configuration
			os.system("%s cp '%s' '%s.old'" % (sshcmd, self._repo.configpath(), self._repo.configpath()))
			fd, path = tempfile.mkstemp(prefix="hg-easy")
			os.write(fd, self.asString())
			# Creates a new one
			os.system("cat '%s' | %s cat - \">\" '%s'" % (path, sshcmd, self._repo.configpath()))
			os.close(fd) ; os.unlink(path)
		elif self._repo.isLocal():
			# Backs up the existing configuration
			f = file(self._repo.configpath() + ".old", 'w')
			f.write(self.read())
			f.close()
			# Writes the new configuration file
			f = file(self._repo.configpath(), 'w')
			f.write(self.asString())
			f.close()
		else:
			raise self.RepositoryNotSupported(repr(self._repo.hgrepo()))

def update_configuration( path, values ):
	"""Updates the Mercurial repository configuration (.hg/hgrc) to be filled
	with the given set of values. If the sections for the given values do not
	exist, they will be added, if they were already present, they will be
	replaced."""
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

class Repository:
	"""The Repository class abstracts Mercurial repositories under a simple API
	and allows to make the distinction between the Central and Working
	repository.

	This class was designed to easily give important information about a
	repository (tags, changes), in a format that can be easily used by UIs."""

	class ConfigurationException(Exception): pass

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
		# We extract the HG repository if necessary
		if repo and isinstance(repo, Repository):
			repo = repo.hgrepo()
		# We remove the .hg from the path, if present
		# We initialize the UI first
		if ui:
			self._ui = ui
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
			if path.endswith(".hg"): path = os.path.dirname(path)
			self._repo = mercurial.hg.repository(self._ui, path)
		# And the configuration
		try:
			self.config   = Configuration(self)
		except Configuration.NotFound:
			self.config   = Configuration()
			

	def isLocal( self ):
		return isinstance(self._repo, mercurial.localrepo.localrepository)

	def isSSH( self ):
		if not isinstance(self._repo, mercurial.sshrepo.sshrepository):
			return False
		# This returns the proper SSH arguments to for the repository location
		args = self._repo.user and ("%s@%s" % (self._repo.user, self._repo.host)) or self._repo.host
		args = self._repo.port and ("%s -p %s") % (args, self._repo.port) or args
		return args

	# ACCESSORS
	# _________________________________________________________________________

	def hgrepo( self ):
		return self._repo

	def configpath( self ):
		path = self.path()
		return path + "/.hg/hgrc"

	def path(self):
		path = self._repo.path
		if path.endswith("/"):    path = path[:-1]
		if path.endswith(".hg"):  path = path[:-3]
		if path.endswith("/"):    path = path[:-1]
		return path

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

	# UTILITIES
	# _________________________________________________________________________

	def _changesetInfo( self, ref ):
		"""Returns informations on the given change set."""
		changeset  = self._repo.changelog.read(ref)
		cid, cauthor, ctime, cfiles, cdesc = changeset
		cauthor = cauthor.strip()
		cdate   = time.strftime('%d-%b-%Y', time.gmtime(ctime[0]))
		cdesc   = cdesc.replace("'", "''").strip()
		return cauthor, ctime, cdate, cdesc, cfiles

	def _property( self, name, value = None, add=False ):
		"""Gets a property set in this project configuration"""
		section, _property = name.split(".")
		if value == None:
			return self._ui.config(section, _property)
		else:
			if add:
				p = self._property(name)
				if p: self._property(name, p + ", " + value)
				else: self._property(name, value)
			else:
				self._ui.setconfig(section, _property, value)
				self.config.update(section, _property, value)
				assert self._property(name) == value

	def _properties( self, name=None ):
		"""Sets a property in this project configuration"""
		return map(string.strip, str(self._property(name)).split())

# EOF
