#!/usr/bin/python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 et
# -----------------------------------------------------------------------------
# Project   : Mercurial - Project extension
# -----------------------------------------------------------------------------
# Author    : Sébastien Pierre                           <sebastien@xprima.com>
# -----------------------------------------------------------------------------
# License   : GNU Public License <http://www.gnu.org/licenses/gpl.html>
# Creation  : 01-Jun-2006
# Last mod  : 02-Jun-2006
# -----------------------------------------------------------------------------

from mercurial.demandload import demandload
from mercurial.i18n import gettext as _
demandload(globals(), 'mercurial.ui mercurial.hg os string time')

# ------------------------------------------------------------------------------
#
# TOOLS
#
# ------------------------------------------------------------------------------

def update_configuration( path, values ):
    """Updates the [project] section of the Mercurial configuration to be filled
    with the given set of values. If the section does not exist, it will be
    appended, if it already exists, it will be rewrited."""
    f = open(path, 'r') ; text = f.read() ; f.close()
    result          = []
    current_section = None
    # For every line of the Mercurial RC file
    for line in text.split("\n"):
        # If we are in a section, we log it
        if line.strip().startswith("["):
            current_section = line.strip()[1:-1].strip().lower()
            result.append(line)
            last_section = {}
            # We take care of the paths.default-push
            if current_section == "paths" and values.get("parent"):
                result.append("default-push = %s" % (values[parent]))
        elif current_section == "project":
            for key, value in values.items():
                result.append("%s = %s" % (key, value))
            current_section = "SKIP"
        elif current_section == "paths" and values.get("parent"):
            if line.strip().lower().startwith("default-push"): pass
            else: result.append(line)
        elif current_section == "SKIP":
            pass
        else:
            result.append(line)
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
    if repo.get("parent"): repo = WorkingRepository(path)
    else: repo = CentralRepository(path)
    return repo

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
            self_ui    = ui
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
            self._repo     = repo
        else:
            self._path     = self._ui.expandpath(path)
            if self._path.endswith(".hg"):
                self._path = os.path.dirname(self._path)
            self._repo     = mercurial.hg.repository(self._ui, self._path)
        self._updated      = {}
        self._owners       = []
        self._developers   = []

    def get( self, value ):
        return self._ui.config("project", value)

    def set( self, name, value ):
        self._ui.setconfig("project", name, value)
        assert self.get(name) == value
        self._updated[name] = value

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
        return self._path

    def _changesetInfo( self, ref ):
        changeset  = self._repo.changelog.read(ref)
        cid, cauthor, ctime, cfiles, cdesc = changeset
        cauthor = cauthor.strip()
        cdate     = time.strftime('%d-%b-%Y', time.gmtime(ctime[0]))
        cdesc     = cdesc.replace("'", "''").strip()
        return cauthor, ctime, cdate, cdesc, cfiles

    def count( self ):
        """Returns the number of changes in this repository."""
        return self._repo.changelog.count()

    def changes( self, n=None ):
        """Yields the n (10 by default) latest changes in this
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
        text    = ""
        text += "Name        : %s (%s)\n" % (self.name(), self.type())
        text += "Description : %s\n" % (self.description())
        text += "Path        : %s\n" % (self._path)
        owners         = self.owners()
        developers     = self.developers()
        if   len(owners) == 0:
            pass
        elif len(owners) ==1:
            text += "Owner       : " + owners[0] + "\n"
        else:
            text += "Owners      : " + ", ".join(owners) + "\n"
        if   len(developers) == 0:
            pass
        elif len(developers) == 1:
            text += "Developer   : " + developers[0] + "\n"
        else:
            text += "Developers  : " + ", ".join(developers)
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

# ------------------------------------------------------------------------------
#
# WORKING PROJECT
#
# ------------------------------------------------------------------------------

class WorkingRepository(Repository):
    
    def __init__(self, path, config=None):
        Repository.__init__(self, path)
        self._parent = None

    def name(self):
        return self.parent().name()

    def description(self):
        return self.parent().description()

    def type(self):
        return "working"

    def parent(self):
        if not self._parent:
            self._parent = Repository_load(self.get("parent"))
        return self._parent

    def owners(self):
        r = []
        r.extend(self._owners)
        for own in self._parent.owners():
            if own not in r: r.append(own)
        return r
        
    def developers(self):
        r = []
        r.extend(self._developers)
        for dev in self._parent.developers():
            if dev not in r: r.append(dev)
        return r

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
        if not self.isSynchronized(): meta.append("out of sync")
        if self.isModified(): meta.append("modified")
        lines[0] = "Name        : %s (%s)" % (self.name(), ", ".join(meta))
        lines.insert(3, "Parent      : " + self._parent._path)
        return "\n".join(lines)

# ------------------------------------------------------------------------------
#
# COMMANDS
#
# ------------------------------------------------------------------------------

HELP = """\
project [info|parent|clone]

   Enables easy management of repositories for projects with a central
   repository and many working repositories related to it.

   A central repository can be given a 'name' and a 'description', and each
   working repository can be related to by setting the 'parent' property to
   point to the central repository.

project info [property=value...]

    Displays a summary of the project, and telling wether the current repository
    is the central or a working directory. If arguments are given, properties
    can be modified in the project configuration (.hg/hgrc, [project] section).

project parent [LOCATION]

    Displays information on this repository parent (only works if
    current repository is a working repository). If a location is given, the
    repository parent is set and the repository becomes a workinf repository.

project clone LOCATION

    Clones the central repository for this project to the given location. The
    clone will be a working repository for the project.

""" 

class Commands:
    """This defines the set of Mercurial commands that constitute the project
    extension."""

    def __init__(self):
        pass

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
            ui.write(HELP)
        elif cmd == "parent":
            if isinstance(repo, CentralRepository):
                ui.warn("This is a central repository, and it has no parent\n")
            else:
                repo = repo.parent()
                self.main(ui, repo, *args[1:], **opts)

    def info(self, ui, repo, *args, **opts):
        if not args:
            ui.write(repo.summary() + "\n")
        for arg in args:
            print repo.parent().summary()
            if arg.find("=")!=-1 and len(arg.split("=")) == 2:
                key, value = map(string.strip, arg.split("="))
                old = repo.get(key)
                repo.set(key, value)
                ui.write("Setting '%s' to '%s' (was %s)\n" % (key, value, old))
            else:
                raise Exception("Bad argument: " + arg)
            repo.updateConfig()

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
