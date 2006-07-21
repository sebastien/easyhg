#!/usr/bin/python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 fenc=latin-1 noet
# -----------------------------------------------------------------------------
# Project   : Mercurial - Project extension
# -----------------------------------------------------------------------------
# Author   : Sébastien Pierre                            <sebastien@xprima.com>
# -----------------------------------------------------------------------------
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# Creation  : 01-Jun-2006
# Last mod  : 10-Jul-2006
# -----------------------------------------------------------------------------

import sys
try:
	from mercurial.demandload import demandload
	from mercurial.i18n import gettext as _
except:
	print "Failed to load Mercurial modules."
	sys.exit(-1)

demandload(globals(), 'mercurial.ui mercurial.hg mercurial.commands os string time')

# TODO: Add default-push for working repositories

__doc__ = """\
Mercurial project extension aims at making the use of Mercurial in a
centralized environment easier. This extension allows the annotation of
repositories, so that is is possible to specify a central repository, as well as
a set of "working repositories", linked to the central repository.

This extension also defines a Repository class that eases the access to
Mercurial repository information.
"""

# ------------------------------------------------------------------------------
#
# TOOLS
#
# ------------------------------------------------------------------------------

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

class RepositoryException(Exception): pass

def Repository_load( path ):
	"""Creates a Central or a Working repository instance depending on the
	repository type."""
	repo = Repository(path)
	if repo.get("parent"): repo = DevelopmentRepository(path)
	else: repo = CentralRepository(path)
	return repo

def Repository_locate( path="." ):
	path	 = os.path.abspath(path)
	print path
	old_path = None
	while old_path != path:
		hg_path  = os.path.join(path, ".hg")
		if os.path.isdir(hg_path): return path
		old_path = path
		path	 = os.path.dirname(path)
	return None

class Repository:
	"""The Repository class abstracts Mercurial repositories under a simple API
	and allows to make the distinction between the Central and Working
	repository.

	This class was designed to easily give important information about a
	repository (tags, changes), in a format that can be easily used by UIs."""

	def __init__(self, path=None, repo=None, ui=None):
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
			self._repo	 = repo
		else:
			self._path	 = self._ui.expandpath(path)
			if self._path.endswith(".hg"):
				self._path = os.path.dirname(self._path)
			self._repo	 = mercurial.hg.repository(self._ui, self._path)
		self._updated	  = {}
		self._owners	   = []
		self._developers   = []

	def get( self, value ):
		"""Gets a property of this project"""
		return self._ui.config("project", value)

	def mget( self, value ):
		"""Gets a property of with multiple values"""
		return map(string.strip, str(self.get(value)).split())

	def set( self, name, value ):
		"""Sets a property for this project (the property has a single
		value)."""
		self._ui.setconfig("project", name, value)
		assert self.get(name) == value
		self._updated[name] = value

	def add( self, name, value ):
		"""Adds the given value to the given property."""
		p = self.get(name)
		if p: self.set(name, p + ", " + value)
		else: self.set(name, value)

	def name(self):
		return self.get("name")

	def description(self):
		return self.get("description")

	def type(self):
		raise Exception("Must be implemented by subclass")

	def owners(self):
		if not self._owners:
			self._owners = self.get("owner") or self.get("owners")
			if not self._owners: self._owners = []
			else: self._owners = map(string.strip, self._owners.split(","))
		return self._owners

	def developers(self):
		if not self._developers:
			authors = {}
			for changes in self.changes():
				if changes[0] in self.owners(): continue
				authors[changes[0]] = True
			self._developers = authors.keys()
		return self._developers

	def path(self):
		return expand_path(self._path)

	def _changesetInfo( self, ref ):
		changeset  = self._repo.changelog.read(ref)
		cid, cauthor, ctime, cfiles, cdesc = changeset
		cauthor = cauthor.strip()
		cdate	 = time.strftime('%d-%b-%Y', time.gmtime(ctime[0]))
		cdesc	 = cdesc.replace("'", "''").strip()
		return cauthor, ctime, cdate, cdesc, cfiles

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
		"""Yields tag name, rev and date for each tag within this repository."""
		tags = []
		for name, ref in self._repo.tagslist():
			cauthor, ctime, cdate, desc, cfiles = self._changesetInfo(ref)
			tags.append((name, self._repo.changelog.rev(ref), cdate))
		tags.reverse()
		return tags
 
	def summary( self ):
		"""Returns a text summary of this repository"""
		text	= ""
		text += "name:        %s (%s)\n" % (self.name(), self.type())
		text += "description: %s\n" % (self.description())
		text += "path:        %s\n" % (self._path)
		owners		 = self.owners()
		developers	 = self.developers()
		if   len(owners) == 0:
			pass
		elif len(owners) ==1:
			text += "owner:	   " + owners[0] + "\n"
		else:
			text += "Owners	   " + ", ".join(owners) + "\n"
		if   len(developers) == 0:
			pass
		elif len(developers) == 1:
			text += "developer:   " + developers[0] + "\n"
		else:
			text += "developers:  " + str(len(developers)) + "\n"
		return text

	def updateConfig( self ):
		"""Updates this repository configuration file to reflect the changes
		made to the repository."""
		if not self._updated: return
		values = {}
		for key, value in self._ui.configitems("project"): values[key] = value
		for key, value in self._updated.items(): values[key] = value
		hgrc = os.path.join(self._path, ".hg", "hgrc")
		update_configuration(hgrc, values)

# ------------------------------------------------------------------------------
#
# CENTRAL PROJECT
#
# ------------------------------------------------------------------------------

class CentralRepository(Repository):
	"""Central repositorys are the "reference" project repositories, where the latest
	stable version is stored."""

	def __init__(self, path, config=None):
		Repository.__init__(self, path)

	def type(self):
		return "central"

	def parent(self):
		"""Returns this repository, as it has no parent."""
		return self

	def children(self):
		"""Returns the absolute path to the child repositories for this central
		repository."""
		c = self.mget("children")
		if c == ["None"]: return []
		else: return c

	def summary( self ):
		"""Returns a text summary of this repository"""
		lines = list(Repository.summary(self).split("\n"))
		c = self.children()
		if c:
			lines.append("children:    %d" % (len(c)))
		return "\n".join(lines[:-1])

	def qualifiers( self ):
		"""Returns a list of qualifiers that describe the state of the central
		project relatively to the children repositories."""
		qualifiers = {}
		last_change = self.changes(1)
		cauthor, ctime, cdate, desc, cfiles = last_change
		for child_repo_path in self.children():
			child_repo = Repository_load(child_repo_path)
			other_change = child_repo.change(1)
			if other_change[1] > ctime:
				qualifiers["incoming change"] = True
			# TODO: Add branch detection
			# TODO: Add local changes detection
		return qualifiers.keys()

# ------------------------------------------------------------------------------
#
# DEVELOPMENT REPOSITORY
#
# ------------------------------------------------------------------------------

class DevelopmentRepository(Repository):
	
	def __init__(self, path, config=None):
		Repository.__init__(self, path)
		self._parent = None

	def name(self):
		return self.parent().name()

	def description(self):
		return self.parent().description()

	def type(self):
		return "development"

	def parent(self):
		if not self._parent:
			self._parent = Repository_load(self.get("parent"))
			# We ensure that this repository is registered in the parent
			if self._path not in self._parent.mget("children"):
				self._parent.add("children", self._path)
				self._parent.updateConfig()
		return self._parent

	def isSynchronized( self ):
		"""Tells wether this repository is synchronized with the parent
		repository."""
		return not self._repo.findincoming(self._parent._repo)
 
	def isModified( self ):
		"""Tells wether this repository has outgoing changesets."""
		return self._repo.findoutgoing(self._parent._repo)

	def summary( self ):
		"""Returns a text summary of this repository"""
		lines = list(Repository.summary(self).split("\n"))
		meta  = [self.type()]
		meta.extend(self.qualifiers())
		if not self.isSynchronized(): meta.append("out of sync")
		if self.isModified(): meta.append("modified")
		lines[0] = "name:        %s (%s)" % (self.name(), ", ".join(meta))
		lines.insert(3, "parent:      " + self._parent._path)
		return "\n".join(lines)

	def qualifiers( self ):
		"""Returns a list of qualifiers that describe the state of the central
		project relatively to the children repositories."""
		qualifiers         = {}
		last_change        = tuple(self.parent().changes(1))[0]
		parent_last_change = tuple(self.parent().changes(1))[0]
		cauthor, ctime, cdate, desc, cfiles = last_change
		if last_change == parent_last_change:
			qualifiers["up to date"] = True
			return qualifiers
		elif last_change[1] < parent_last_change[1]:
			qualifiers["out of date"] = True
		elif last_change[1] > parent_last_change[1]:
			qualifiers["outgoing change"] = True
		else:
			qualifiers["up to date"] = True
		return qualifiers.keys()
# ------------------------------------------------------------------------------
#
# COMMANDS
#
# ------------------------------------------------------------------------------

HELP = """\
project [info|parent|clone]

   Enables easy management of repositories for projects with a central
   repository and many development repositories related to it.

   A central repository can be given a 'name' and a 'description', and each
   development repository can be related to by setting the 'parent' property to
   point to the central repository.

project info [property=value...]

    Displays a summary of the project, and telling wether the current repository
    is the central or a development directory. If arguments are given, properties
    can be modified in the project configuration (.hg/hgrc, [project] section).

    Supported properties for Central repositories:
    
        name          = a string with the project name
        description   = a string with the project description
        owner(s)      = comma-separated list of name <email> for project owners

    for development repositories:

        parent        = path to the parent repository

project status

    Displays the status of this repository. This will tell you if there are
    incoming or outgoing changes.

project parent [COMMAND|LOCATION]

    Displays information on this repository parent (only works if
    current repository is a development repository). If a location is given, the
    repository parent is set and the repository becomes a workinf repository.

project children

     Lists the repositories that are children of this project central
     repository

project clone LOCATION

    Clones the central repository for this project to the given location. The
    clone will be a development repository for the project.

""" 

class Commands:
	"""This defines the set of Mercurial commands that constitute the project
	extension."""

	def __init__(self):
		pass

	def parent(self, ui, repo, *args, **opts):
		if isinstance(repo, CentralRepository):
			ui.warn("This is a central repository, it has no parent\n")
		else:
			repo = repo.parent()
			self.main(ui, repo, *args[1:], **opts)

	def info(self, ui, repo, *args, **opts):
		if not args:
			ui.write(repo.summary() + "\n")
		for arg in args:
			if arg.find("=")!=-1 and len(arg.split("=")) == 2:
				key, value = map(string.strip, arg.split("="))
				old = repo.get(key)
				repo.set(key, value)
				ui.write("Setting '%s' to '%s' (was %s)\n" % (key, value, old))
			else:
				raise Exception("Bad argument: " + arg)
			repo.updateConfig()

	def help(self, ui, repo, *args, **opts):
		ui.write(HELP)

	def children(self, ui, repo, *args, **opts ):
		children = repo.parent().children()
		if not children:
			ui.write("This project has no children (yet)\n")
		else:
			if len(children) == 1:
				ui.write("This project has %d child:\n" % (len(children)))
			else:
				ui.write("This project has %d children:\n" % (len(children)))
			for c in children:
				r = Repository_load(c)
				ui.write(" - ", c, " (",
				", ".join(Repository_load(c).owners()), ")\n")

	def clone(self, ui, repo, *args, **opts ):
		destination = os.path.abspath(args[0])
		if os.path.exists(destination):
			ui.write("The destination directory should not exist.\n")
			sys.exit(-1)
		# mercurial.commands.clone(ui, ".", destination)
		# TODO: Should use mercurial.commands once opts problem is fixed
		os.system("hg clone '%s' '%s'" % (Repository_locate("."), destination))
		repo_clone = DevelopmentRepository(destination)
		repo_clone.set("parent", repo.path())
		repo_clone.updateConfig()

	def main(self, ui, repo, *args, **opts):
		if len(args) == 0: args = ["info"]
		cmd = args[0]
		# We ensure that the given repository is wrapped in our wrapper
		if not isinstance(repo, Repository):
			repo = Repository_load(repo.path)
		# And we process the arguments
		if   cmd == "info":
			self.info(ui, repo, *args[1:])
		elif cmd == "help":
			self.help(ui, repo, *args[1:])
		elif cmd == "parent":
			self.parent(ui, repo, *args[1:], **opts)
		elif cmd == "children":
			self.children(ui, repo, *args[1:], **opts)
		elif cmd == "clone":
			self.clone(ui, repo, *args[1:], **opts)
		else:
			ui.warn("Unknown command: ", cmd, "\n")

# ------------------------------------------------------------------------------
#
# MERCURIAL COMMAND REGISTRATION
#
# ------------------------------------------------------------------------------

commands = Commands()
cmdtable = {
	"project": ( commands.main, [], 'hg project info|clone|parent' )
}
# EOF
