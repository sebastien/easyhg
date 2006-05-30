#!/usr/bin/python
# Encoding: iso-8859-1
# vim: tw=80 ts=2 sw=2 et
# -----------------------------------------------------------------------------
# Project   : Mercurial - Repository Management Extensions
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre <sebastien@xprima.com>
# License   : GNU Public License <http://www.gnu.org/licenses/gpl.html>
# Creation  : 25-May-2006
# Last mod  : 25-May-2006
# History   :
#             25-May-2006 - First implementation
# -----------------------------------------------------------------------------

import os, os.path, sys, time, string, ConfigParser
import mercurial.ui, mercurial.node, mercurial.hg

# ------------------------------------------------------------------------------
#
# UTILITIES
#
# ------------------------------------------------------------------------------

def error( *args ):
  return
  sys.stderr.write("%s\n" % (" ".join(map(str,args))))

def fatal( *args ):
  return
  error(*args) ; sys.exit(-1)

def log( *args ):
  return
  sys.stdout.write("%s\n" % (" ".join(map(str,args))))

def lookup_repository( path ):
  """Looks for a repository in the current path or in the ancestors of the given
  path. Returns None if no hg directory exists, otherwise, returns the directory
  where the .hg subdirectory resides."""
  path = os.path.abspath(path)
  while path and path != os.path.dirname(path) \
  and not os.path.isdir(os.path.join(path, ".hg")):
    path = os.path.dirname(path)
  path = os.path.join(path, ".hg")
  if os.path.isdir(path):
    return os.path.dirname(path)
  else:
    return None

def expand_path( path ):
  """Expands env variables and ~ symbol into the given path, and makes it
  absolute."""
  path = os.path.expanduser(path)
  path = string.Template(path).substitute(os.environ)
  return os.path.abspath(path)

def checksEnvironment():
  """Ensures that the PROJECTS and WORKSPACE environment variables are
  defined."""
  if not os.environ.has_key("PROJECTS"):
    fatal("PROJECTS environment variable must be defined")
  if not os.environ.has_key("WORKSPACE"):
    fatal("WORKSPACE environment variable must be defined")
 
# ------------------------------------------------------------------------------
#
# REPOSITORIES
#
# ------------------------------------------------------------------------------

class RepositoryException(Exception): pass

def Repository_load( path ):
  """Creates a Central or a Working repository instance depending on the
  repository type."""
  proj = Repository(path)
  config, errors = proj._loadConfiguration()
  if config.get("project.parent"): proj = WorkingRepository(path, config)
  else: proj = CentralRepository(path, config)
  return proj
  
class Repository:
  """The Repository class abstracts central and working repositorys. This is where
  common attributes and methods are defined."""

  def __init__(self, path):
    self._path        = expand_path(path)
    self._description = None
    self._type        = None
    self._parent      = None
    self._developers  = []
    self._owners      = []
    if not os.path.isdir(os.path.join(self._path, ".hg")):
      raise RepositoryException("Repository directory has no Mercurial repository: " + path)
    self._ui       = mercurial.ui.ui(quiet=True)
    self._repo     = mercurial.hg.repository(self._ui, self._path)

  def name(self):
    raise Exception("Must be implemented by subclass")

  def description(self):
    raise Exception("Must be implemented by subclass")

  def type(self):
    raise Exception("Must be implemented by subclass")

  def owners(self):
    raise Exception("Must be implemented by subclass")
    
  def developers(self):
    raise Exception("Must be implemented by subclass")

  def path(self):
    return self._path

  def _changesetInfo( self, ref ):
      changeset     = self._repo.changelog.read(ref)
      cid, cauthor, ctime, cfiles, cdesc = changeset
      cauthor = cauthor.strip()
      cdate   = time.strftime('%d-%b-%Y', time.gmtime(ctime[0]))
      cdesc   = cdesc.replace("'", "''").strip()
      return cauthor, ctime, cdate, cdesc, cfiles

  def count( self ):
    """Returns the number of changes in this repository."""
    return self._repo.changelog.count()

  def changes( self, n=10 ):
    """Yields the n (10 by default) latest changes in this
    repository. Each change is returned as (author, date, description, files)"""
    changes_count = self._repo.changelog.count()
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

  def _loadConfiguration(self):
    """Reads this repository configuration and returns a configuration dictionary
    along with a list of errors (as strings)."""
    desc_path = os.path.join(self._path, ".project")
    if not os.path.isfile(desc_path):
      raise RepositoryException("Repository description expected: " + desc_path)
    # Reads the repository description
    parser = ConfigParser.ConfigParser()
    try:
      parser.read(desc_path)
    except ConfigParser.ParsingError, e:
      fatal(str(e))
    config = {}
    errors = []
    for section in parser.sections():
      for option in parser.options(section):
        key = section.lower() + "." + option.lower()
        val = parser.get(section, option).strip()
        if   key == "project.name":
          config[key] = val
        elif key == "project.description":
          config[key] = val
        elif key == "project.parent":
          config[key] = val
        elif key == "project.type":
          val = val.lower()
          if val in ("central", "working"):
            config[key] = val
          else:
            errors.append("Expected 'central' or 'working' for %s: got %s" % (key, val))
        elif key in ("project.owner", "project.owners"):
            config["project.owners"] = val
        elif key in ("project.developer", "project.developers"):
            config["project.developers"] = val
        else:
          errors.append("Invalid configuration option: " + key)
     # We log the errors in the configuration 
    if len(errors) == 1:
      log("%s error in configuration file:" % (len(errors)))
      error(errors[0])
    elif len(errors) > 1:
      log("%s errors in configuration file:" % (len(errors)))
      for err in errors:
        error(" - ", err)
    # And return the result
    return config, errors

  def update( self, config=None ):
    if not config: return
    self._developers  = config.get("project.developers") or []
    self._owners      = config.get("project.owners") or []
    if self._developers:
      self._developers = map(string.strip,self._developers.split(","))
    if self._owners:
      self._owners     = map(string.strip,self._owners.split(","))
 
  def summary( self ):
    """Returns a text summary of this repository"""
    text  = ""
    text += "Name        : %s (%s)\n" % (self.name(), self.type())
    text += "Description : " + self.description() + "\n"
    text += "Path        : " + self._path + "\n"
    owners     = self.owners()
    developers = self.developers()
    if len(owners) ==1:
      text += "Owner       : " + owners[0] + "\n"
    else:
      text += "Owners      : " + ", ".join(owners) + "\n"
    if len(developers) == 1:
      text += "Developer   : " + developers[0] + "\n"
    else:
      text += "Developers  : " + ", ".join(developers)
    return text

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
    self.update(config)

  def name(self):
    return self._name

  def type(self):
    return "central"

  def description(self):
    return self._description or "No description given"

  def owners(self):
    return self._owners
    
  def developers(self):
    return self._developers

  def update(self, config=None):
    Repository.update(self, config)
    if not config: config, errors = self._loadConfiguration()
    else: errors = ()
    # Now we validate the integraty of the description
    if not config.has_key("project.name"):
      fatal("Central repository must be named.")
    if not config.has_key("project.description"):
      error("Central repository should have a description.")
    if config.has_key("project.parent"):
      fatal("Central repositorys are not allowed to have a parent.")
    if not config.get("project.owners"):
      fatal("Central repository must have at least one owner.")
    if not config.get("project.developers"):
      error("Central repository should have developers.")
    # And update the repository properties
    self._name        = config.get("project.name")
    self._description = config.get("project.description")

# ------------------------------------------------------------------------------
#
# WORKING PROJECT
#
# ------------------------------------------------------------------------------

class WorkingRepository(Repository):
  
  def __init__(self, path, config=None):
    Repository.__init__(self, path)
    self.update(config)

  def name(self):
    return self._parent.name()

  def description(self):
    return self._parent.description()

  def type(self):
    return "working"

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

  def update(self, config=None):
    Repository.update(self, config)
    if not config: config, errors = self._loadConfiguration()
    else: errors = ()
    # Now we validate the integraty of the description
    if config.has_key("project.name"):
      fatal("Working repository cannot be named. Name is inherited from parent")
    if config.has_key("project.description"):
      fatal("Working repository cannot be described. Description is inherited from parent")
    if not config.has_key("project.parent"):
      fatal("Working repository must have a parent.")
    if not config.get("project.owners"):
      fatal("Working repository must have an owner (add a [project] owner=Your Name).")
    # And update the repository properties
    self._parent      = Repository_load(config.get("project.parent"))
    # We now ensure that the .hg/hgrc file has the default_push value properly
    # set
    hgrc_path = os.path.join(self.path(), ".hg", "hgrc")
    if not os.path.isfile(hgrc_path):
      text = "[paths]\ndefault-push=%s\n" % (self._parent.path())
    else:
      hgrc             = file(hgrc_path, "r")
      text             = ""
      default_push     = False
      in_paths_section = False
      # For every line of the Mercurial RC file
      for line in hgrc.readlines():
        # Are we in a section ?
        if line.strip().startswith("["):
          # If this is the path section, we log this
          if line.strip()[1:-1].strip().lower() == "paths":
            paths_section    = True
            in_paths_section = True
          # If it is another section, and we had a paths section
          elif in_paths_section:
            text += "default-push=%s\n" % (self._parent.path())
            in_paths_section = False
            default_push     = True
          else:
            in_paths_section = False
          text += line 
        # We skip any default-push 
        elif line.strip().lower().startswith("default-push"):
          pass
        else:
          text += line 
      # We may have to add the default-push and its enclosing section
      if not default_push:
        if not in_paths_section: text += "[paths]\n"
        text += "default-push=%s\n" % (self._parent.path())
      hgrc.close()
    # We update the hgrc file as well
    hgrc = file(hgrc_path, "w")
    hgrc.write(text)
    hgrc.close()

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
# COMMAND LINE INTERFACE
#
# ------------------------------------------------------------------------------

command = "hgproject"
USAGE = """
%(command)s [PATH]

    Displays a summary of the repository in the current directory or given PATH.
    This only works if you have previously edited project information for this
    repository.

%(command)s edit

    Edits the `.hg/project` file where the project configuration resides. You
    will start with a template that will allow you to specify wether you
    consider the current project repository as a central or working repository.

%(command)s parent [COMMAND]

    Executes the given Mercurial command in the project parent repository. The
    $CHILD environment variable will be set to the current repository path.

""" % locals()

def run( args ):
  repo = lookup_repository(".")
  if not repo:
    error("No repository found")
    return -1
  proj = Repository_load(repo)
  print proj.summary()

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------

if __name__ == "__main__":
  args = sys.argv[1:]
  result = run(args) or 1
  sys.exit(result)

# EOF
