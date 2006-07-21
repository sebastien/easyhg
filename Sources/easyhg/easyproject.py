#!/usr/bin/python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 fenc=latin-1 noet
# -----------------------------------------------------------------------------
# Project   : Mercurial - Easy tools
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# -----------------------------------------------------------------------------
# Author    : Sébastien Pierre                           <sebastien@xprima.com>
# -----------------------------------------------------------------------------
# Creation  : 01-Jun-2006
# Last mod  : 21-Jul-2006
# -----------------------------------------------------------------------------

import sys, os, string, time
try:
	import mercurial.ui, mercurial.hg, mercurial.commands
except:
	print "Failed to load Mercurial modules."
	sys.exit(-1)

try:
	from easyhg.easyapi import Repository, expand_path
except:
	print "Failed to load Mercurial-Easy modules."
	sys.exit(-1)

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
# REPOSITORIES
#
# ------------------------------------------------------------------------------

def Repository_load( repo, ui=None ):
	"""Creates a Central or a Working repository instance depending on the
	repository type."""
	if type(repo) in (str, unicode): repo = Repository(repo, ui=ui)
	if repo._property("project.parent"): repo = DevelopmentRepository(repo=repo, ui=ui)
	else: repo = CentralRepository(repo=repo, ui=ui)
	return repo

class ProjectRepository(Repository):
	"""This specific repository subclass offers an easy way to manipulate
	additional project meta-information managed by the easyproject extension."""

	CENTRAL     = "central"
	DEVELOPMENT = "development"

	def __init__(self, path=None, repo=None, ui=None):
		Repository.__init__(self, path=path, repo=repo, ui=ui)
		self._owners     = []
		self._developers = []

	def name(self):
		"""Returns the project name, if any."""
		return self._property("project.name")

	def type( self ):
		raise Exception("Not implemented")

	def parent( self ):
		raise Exception("Not implemented")

	def setParent( self, location ):
		"""Sets the given location to point to the parent repository."""
		self.config.update("paths",   "default", location)
		self.config.update("project", "parent",  location)

	def description(self):
		"""Returns the project description, if any."""
		return self._property("project.description")

	def owners(self):
		"""Returns the list of project owners, if any."""
		if not self._owners:
			self._owners = self._property("project.owner") or self._property("project.owners")
			if not self._owners: self._owners = []
			else: self._owners = map(string.strip, self._owners.split(","))
		return self._owners

	def developers(self):
		"""Returns the list of project developers, if any."""
		if not self._developers:
			authors = {}
			for changes in self.changes():
				if changes[0] in self.owners(): continue
				authors[changes[0]] = True
			self._developers = authors.keys()
		return self._developers

	def qualifiers( self ):
		qualifiers = {}
		if not self.name() and not self.description():
			qualifiers["unconfigured"] = True
		return qualifiers.keys()

	def summary( self ):
		"""Returns a text summary of this repository"""
		text	= ""
		if self.name():
			text += "name:        %s (%s)\n" % (self.name(), self.type())
		if self.description():
			text += "description: %s\n" % (self.description())
		text += "state:       %s\n" % (", ".join(self.qualifiers()))
		text += "path:        %s\n" % (self.path())
		owners		 = self.owners()
		developers	 = self.developers()
		if   len(owners) == 0:
			pass
		elif len(owners) ==1:
			text += "owner:    " + owners[0] + "\n"
		else:
			text += "owners    " + ", ".join(owners) + "\n"
		if   len(developers) == 0:
			pass
		elif len(developers) == 1:
			text += "developer:   " + developers[0] + "\n"
		else:
			text += "developers:  " + str(len(developers)) + "\n"
		return text

# ------------------------------------------------------------------------------
#
# CENTRAL PROJECT
#
# ------------------------------------------------------------------------------

class CentralRepository(ProjectRepository):
	"""Central repositories are the "reference" project repositories, where the latest
	stable version is stored."""

	def __init__( self, path=None, repo=None, ui=None ):
		ProjectRepository.__init__(self, path=path, repo=repo, ui=ui)

	def type(self):
		return ProjectRepository.CENTRAL

	def parent(self):
		"""Returns this repository parent"""
		return self

	def addChild( self, repository ):
		"""Adds the given Repository instance as a child of this repository.
		This will update this repository configuration."""
		assert isinstance(repository, DevelopmentRepository)
		if self.isSSH() or repository.isSSH():
			project_url = repository.config.get("project", "url")
			if not project_url:
				raise Repository.ConfigurationException("Project URL expected")
		elif self.isLocal() and self.isLocal():
			project_url = os.path.abspath(repository.path())
		else:
			raise Repository.Exception("Operation not supported")
		# We update the configuration
		children = self.config.get("project", "children")
		if children \
		and project_url in map(string.strip, children.split(",")):
			return
		if children:
			self.config.update("project", "children", children + ", " + project_url)
		else:
			self.config.update("project", "children", project_url)

	def children(self):
		"""Returns the absolute path to the child repositories for this central
		repository."""
		c = self._properties("projet.children")
		if c == ["None"]: return []
		else: return c

	def summary( self ):
		"""Returns a text summary of this repository"""
		lines = list(ProjectRepository.summary(self).split("\n"))
		c = self.children()
		if c:
			lines.append("children:    %d" % (len(c)))
		return "\n".join(lines[:-1])

	def qualifiers( self ):
		"""Returns a list of qualifiers that describe the state of the central
		project relatively to the children repositories."""
		res  = ProjectRepository.qualifiers(self)
		qualifiers = {}
		last_change = tuple(self.changes(1))
		cauthor, ctime, cdate, desc, cfiles = last_change[0]
		for child_repo_path in self.children():
			child_repo = Repository_load(child_repo_path)
			other_change = child_repo.change(1)
			if other_change[1] > ctime:
				qualifiers["incoming change"] = True
			# TODO: Add branch detection
			# TODO: Add local changes detection
		res.extend(qualifiers.keys())
		return res

# ------------------------------------------------------------------------------
#
# DEVELOPMENT REPOSITORY
#
# ------------------------------------------------------------------------------

class DevelopmentRepository(ProjectRepository):

	def __init__( self, path=None, repo=None, ui=None ):
		ProjectRepository.__init__(self, path=path, repo=repo, ui=ui)
		self._parent = None

	def name(self):
		return self.parent().name()

	def type(self):
		return ProjectRepository.DEVELOPMENT

	def description(self):
		return self.parent().description()

	def parent(self):
		if not self._parent:
			self._parent = Repository_load(self._property("project.parent"))
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
		lines = list(ProjectRepository.summary(self).split("\n"))
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
		res = ProjectRepository.qualifiers(self)
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
		res.extend(qualifiers.keys())
		return res

# ------------------------------------------------------------------------------
#
# COMMANDS
#
# ------------------------------------------------------------------------------

HELP = """\
project [info|status|parent|children|clone|help]

   The project command allows easy management of Mercurial repositories in a
   centralized or semi-centralized style, where there is a notion of "central"
   repository, and a set of "development" repositories link to this repository.

   Sub-commands:

       info/set    sets/gets particular project properties (name, description)
       status      displays the project status (different from hg status)
       parent      displays the project parent, or do commands in the parent
       children    displays the list of project children (if project is central)
       clone       clones the repository, including the project meta-information
       help        displays detailed help on a particular command

"""

HELP_COMMANDS = {
"info":"""\
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

""",
"status":"""\
project status

    Displays the status of this repository. This will tell you if there are
    incoming or outgoing changes.

""",
"parent":"""\
project parent [COMMAND|LOCATION]

    Displays information on this repository parent (only works if
    current repository is a development repository).

    If a LOCATION is given, the repository is turned into a development
    repository and the repository at the given location is used as the new
    parent.

    If a COMMAND is given, the command will be executed in the parent
    repository.

""",
"children": """\
project children

     Lists the repositories that are children of this project central
     repository

""",
"clone": """\
project clone LOCATION

    Clones the central repository for this project to the given location. The
    clone will be a development repository for the project.

"""
}
HELP_COMMANDS["set"] = HELP_COMMANDS["info"]

class Commands:
	"""This defines the set of Mercurial commands that constitute the project
	extension."""

	def __init__(self):
		pass

	def parent(self, ui, repo, *args, **opts):
		if args:
			parent_path = args[0]
			parent_repo = Repository_load(parent_path)
			if parent_repo:
				if isinstance(parent_repo, DevelopmentRepository):
					ui.write("Using given development parent repository instead\n")
					parent_repo = parent_repo.parent()
				# We set the parent repository
				repo.setParent(parent_path)
				try:
					parent_repo.addChild(repo)
				except Repository.ConfigurationException, e:
					ui.write("ERROR: " + str(e) + "\n")
					ui.write("Set your project URL (in Mercurial syntax).\n")
					ui.write("Ex: hg project set url=ssh://myip/myrepo\n")
					return
				# TODO: The parent directory should be notified of children
				# And save both configurations
				repo.config.save()
				parent_repo.config.save()
			else:
				self.main(ui, repo, *args, **opts)
		else:
			if isinstance(repo, CentralRepository):
				ui.warn("This is a central repository, it has no parent\n")
			else:
				repo = repo.parent()

	def info(self, ui, repo, *args, **opts):
		if not args:
			ui.write(repo.summary() + "\n")
		for arg in args:
			if arg.find("=")!=-1 and len(arg.split("=")) == 2:
				key, value = map(string.strip, arg.split("="))
				key = "project." + key
				old = repo._property(key)
				if old == value:
					ui.write("Value '%s' already set to %s\n" % (key, old))
				else:
					repo._property(key, value)
					if old == None: old = ""
					else: old = " (was %s)" % (old)
					ui.write("Setting '%s' to '%s'%s\n" % (key, value, old))
			else:
				raise Exception("Bad argument: " + arg)
			repo.config.save()

	def help(self, ui, repo, *args, **opts):
		if not args:
			ui.write(HELP)
		else:
			command_help = HELP_COMMANDS.get(args[0].lower())
			if not command_help:
				ui.write(HELP)
			else:
				ui.write(command_help)

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
		os.system("hg clone '%s' '%s'" % (Repository.locate("."), destination))
		repo_clone = DevelopmentRepository(destination)
		repo_clone.set("parent", repo.path())
		repo_clone.config.save()

	def main(self, ui, repo, *args, **opts):
		if len(args) == 0: args = ["info"]
		cmd = args[0]
		# We ensure that the given repository is wrapped in our wrapper
		if not isinstance(repo, Repository):
			repo = Repository_load(repo.path)
		# And we process the arguments
		if   cmd == "info" or cmd == "set":
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
