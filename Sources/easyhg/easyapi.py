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
# Last mod  : 24-Jul-2006
# -----------------------------------------------------------------------------

import os, string, time, datetime, re, tempfile, base64
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
# CONFIGURATION FUNCTIONS
#
# ------------------------------------------------------------------------------

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

	def unset( self, sectionName, name ):
		section = self.section(sectionName)
		if section:
			for property_value in section:
				if property_value[0] == name:
					section.remove(property_value)
					self._updated["%s.%s" % (sectionName, name)] = None
					return property_value[1]
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
		return self._repo.readConfiguration()

	def save( self ):
		return self._repo.writeConfiguration(self.asString())

def expand_path( path ):
	"""Expands env variables and ~ symbol into the given path, and makes it
	absolute."""
	path = os.path.expanduser(path)
	path = string.Template(path).substitute(os.environ)
	return os.path.abspath(path)

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
		if self.isSSH():
			api = MercurialSSH(self)
			api.bind(self)
		elif self.isLocal():
			api = MercurialLocal(self)
			api.bind(self)
		else:
			raise RepositoryNotSupported(self._repo.__class__.__name__)
		# And the configuration
		try:
			self.config   = Configuration(self)
		except Configuration.NotFound:
			self.config   = Configuration()

	def isLocal( self ):
		return isinstance(self._repo, mercurial.localrepo.localrepository)

	def isSSH( self ):
		return isinstance(self._repo, mercurial.sshrepo.sshrepository)

	# ACCESSORS
	# _________________________________________________________________________

	def hgrepo( self ):
		"""Returns the Mercurial repository object."""
		return self._repo

	def configpath( self ):
		"""Returns the path to the repository configuration file."""
		path = self.path()
		return path + "/.hg/hgrc"

	def path(self):
		"""Returns the path to the repository, without the trailing .hg"""
		path = self._repo.path
		if path.endswith("/"):    path = path[:-1]
		if path.endswith(".hg"):  path = path[:-3]
		if path.endswith("/"):    path = path[:-1]
		return path
	
	def url(self):
		if self.isSSH():
			return self.hgrepo().url
		else:
			return self.path()

	# UTILITIES
	# _________________________________________________________________________

	def _property( self, name, value = None, add=False ):
		"""Gets a property set in this project configuration"""
		section, _property = name.split(".")
		if value == None:
			return self.config.get(section, _property) or self._ui.config(section, _property)
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

# ------------------------------------------------------------------------------
#
# CHANGESET
#
# ------------------------------------------------------------------------------

class ChangeSet:
	"""This class represents a changeset."""

	def __init__( self ):
		self.num      = -1
		self.id       = None
		self.time     = None
		self.datetime = None
		self.zone     = None
		self.user     = None
		self.files    = []
		self.description = ""

	def abstime( self ):
		# And apply the timezone information
		zone = self.zone
		zmod = datetime.timedelta(hours=int(zone[1:3]), minutes=int(zone[3:]))
		if zone[0] == "+": date = self.datetime + zmod
		else: date = self.datetime - zmod
		return date.timetuple()

	def isNewer( self, changeset ):
		return self.abstime() > changeset.abstime()

	def __eq__( self, changeset ):
		if isinstance( changeset, ChangeSet ):
			return self.id == changeset.id
		else:
			return changeset == self

	def __str__( self ):
		return """\
changeset:   %s:%s
user:        %s
date:        %s %s
files:       %s
description:
%s
""" % (self.num, self.id, self.user, time.strftime("%a %b %d %H:%M:%S %Y",self.time), self.zone, " ".join(self.files),
self.description)

# ------------------------------------------------------------------------------
#
# TAG
#
# ------------------------------------------------------------------------------

class Tag:

	def __init__( self, name ):
		self.name = name
		self.id   = None
		self.num  = None
	
	def __str__( self ):
		return "%-31s%5d:%s" % (self.name, self.num, self.id)

# ------------------------------------------------------------------------------
#
# MERCURIAL API
#
# ------------------------------------------------------------------------------

class MercurialAPI:
	"""The Mercurial API defines an abstract interface that defines various
	methods that allow to access information on a Mercurial repository. It is
	porvided as a convenient Object-Oriented wrapper around the Mercurial
	commands.
	
	The API works well either locally or through an SSH connection."""

	def __init__( self, repo ):
		self._repo = repo

	def bind( self, repo ):
		assert isinstance(repo, Repository)
		repo.count   = self.count
		repo.changes = self.changes
		repo.tags    = self.tags
		repo.writeConfiguration = self.writeConfiguration
		repo.readConfiguration = self.readConfiguration

		self._start()

	def _start( self ):
		"""A private function that is called once the API was bound."""
		pass

	def count( self ):
		"""Returns the number of changes in this repository."""
		raise Exception("Not implemented")

	def changes( self, n=None ):
		"""Yields the n (all by default) latest changes in this
		repository. Each change is returned as (author, date, description, files)"""
		raise Exception("Not implemented")

	def tags( self ):
		"""Returns tag name, rev and date for each tag within this repository."""
		raise Exception("Not implemented")
	
	def readConfiguration( self ):
		"""Reads the .hg/hgrc configuration file, and returns it as a string."""
		raise Exception("Not implemented")

	def writeConfiguration( self, text ):
		"""Writes the given .hg/hgrc configuration file."""
		raise Exception("Not implemented")

	def _parseChangelog( self, changelog ):
		"""Parses Mercurial 'hg log -v' text output, and returns an array of
		ChangeSet instances from that."""
		changeset = None
		changes   = []
		for line in changelog:
			if line.startswith("changeset:"):
				if changeset: changes.append(changeset)
				changeset = ChangeSet()
				line, c_num, c_id     = line.split(":",2)
				changeset.num = int(c_num)
				changeset.id  = c_id
			elif line.startswith("user:"):
				assert changeset
				changeset.user = line.split(":", 1)[1].strip()
			elif line.startswith("date"):
				assert changeset
				date = line.split(":", 1)[1].strip()
				zone = date[-5:]
				date = date[:-6]
				# We interpret the date
				changeset.time = date = time.strptime(date, "%a %b %d %H:%M:%S %Y")
				changeset.datetime = date = apply(datetime.datetime, date[:7])
				changeset.date = date.timetuple()
				changeset.zone = zone
			elif line.startswith("files:"):
				changeset.files = line.split(":", 1)[1].strip().split()
			elif line.startswith("description:"):
				pass
			elif changeset:
				if changeset and changeset.description[-2:] != "\n\n":
					changeset.description += (line + "\n")
		if changes[-1] != changes:
			if changeset: changes.append(changeset)
		for c in  changes:
			if c.description[-1] == "\n": c.description = c.description[:-1]
		return changes

	def _parseTags( self, tagslist ):
		result = []
		for line in tagslist:
			colon = line.rfind(":")
			space = line.rfind(" ", 0, colon)
			tag   = Tag(line[:space].strip())
			tag.num = int(line[space+1:colon])
			tag.id  = line[colon+1:]
			result.append(tag)
		return result

# ------------------------------------------------------------------------------
#
# MERCURIAL LOCAL API
#
# ------------------------------------------------------------------------------

class MercurialLocal(MercurialAPI):
	"""This is an implementation for interacting with Mercurial through the
	local filesystem."""

	END_TOKEN = "@@MERCURIAL_SHELL_END@@"

	def __init__( self, repo ):
		MercurialAPI.__init__(self, repo)
		self._shin   = None
		self._shout  = None
		self._sherr  = None
		self._changes = None
		self._tags    = None
	
	def _start( self ):
		self._startShell()

	# SSH INTERACTION
	# _________________________________________________________________________

	def _startShell( self, shell="sh" ):
		self._shin, self._shout, self._sherr = os.popen3(shell)
		self._doCommand("cd " + self._repo.path())
		current = self._doCommand("pwd")[0]

	def _closeShell( self ):
		self._doCommand("exit")
		self._shout.close()
		self._shin.close()
		self._sherr.close()

	def _doCommand( self, cmd, *args ):
		cmd = "%s %s" % (cmd, " ".join(map(str, args)))
		self._shin.write(cmd + "\n")
		self._shin.write("echo %s\n" % (self.END_TOKEN))
		self._shin.flush()
		result = []
		while True:
			line = self._shout.readline()
			if line.strip().endswith(self.END_TOKEN): break
			result.append(line[:-1])
		return result

	# API IMPLEMENTATION
	# _________________________________________________________________________

	def changes( self, n=None ):
		if not self._changes:
			self._changes = self._parseChangelog( self._doCommand("hg log -v"))
		if n == 1:
			return self._changes[0]
		elif n != None:
			return self._changes[:n]
		else:
			return self._changes

	def count( self ):
		return len(self._changes)

	def tags( self, n=None ):
		if not self._tags:
			self._tags = self._parseTags( self._doCommand("hg tags"))
		return self._tags

	def readConfiguration( self ):
		res = self._doCommand("cat .hg/hgrc")
		return "\n".join(res)

	def writeConfiguration( self, text ):
		cmd  = "echo '%s'" % (base64.b64encode(text))
		cmd += "| python -c 'import sys, base64;print base64.b64decode(sys.stdin.read())'"
		cmd += "> .hg/hgrc" 
		self._doCommand(cmd)

# ------------------------------------------------------------------------------
#
# MERCURIAL SSH API
#
# ------------------------------------------------------------------------------

class MercurialSSH(MercurialLocal):
	"""This class implements methods for interacting with a Mercurial repository
	through the SSH protocol."""

	END_TOKEN = "@@MERCURIAL_SSH_END@@"

	def __init__( self, repo ):
		MercurialLocal.__init__(self, repo)
	
	def _sshParameters( self ):
		# This returns the proper SSH arguments to for the repository location
		hgrepo = self._repo.hgrepo()
		args = hgrepo.user and ("%s@%s" % (hgrepo.user, hgrepo.host)) or hgrepo.host
		args = hgrepo.port and ("%s -p %s") % (args, hgrepo.port) or args
		return args

	def _startShell( self ):
		MercurialLocal._startShell(self, "ssh %s sh" % (self._sshParameters()))

# EOF
