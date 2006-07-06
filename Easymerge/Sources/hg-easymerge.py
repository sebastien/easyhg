#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 et
# -----------------------------------------------------------------------------
# Project   : Mercurial - SVN-like merging tool
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                           <sebastien@xprima.com>
# License   : GNU Public License         <http://www.gnu.org/licenses/gpl.html>
# Creation  : 05-May-2006
# Last mod  : 09-May-2006
# History   :
#             09-May-2006 - Documentation and terminology update
#             08-May-2006 - Added list, resolve, undo, and the Conflicts class.
#             05-May-2006 - First implementation
# -----------------------------------------------------------------------------

import os, sys, re, shutil, difflib

__version__ = "0.2.2"
PROGRAM_NAME = os.path.splitext(os.path.basename(__file__))[0]

MERGETOOL = 'gvimdiff'
if os.environ.has_key("MERGETOOL"): MERGETOOL = os.environ.get("MERGETOOL")

USAGE = """\
%s %s

    hg-svnmerge is tool for Subversion-like merging in Mercurial. It gives more
    freedom to the resolution of conflicts, the user can individually pick the
    changes and resolve them with its preferred set of tools.

    The tool used to do the merging has to be set into this script or into the
    $MERGETOOL environment variable. By default, it is 'gvimdiff'

Commands :

    list    [DIRECTORY]                     - list registered conflicts
    resolve [CONFLICT] [parent|other|merge] - resolves all/given conflict(s)
    undo    [CONFLICT]                      - undo a resolution
    clean   [DIRECTORY]                     - cleans up the conflict files
    commit                                  - try to commit the changes (TODO)

Usage:

    Mercurial will automatically invoke this command when merging, so that it
    creates three files in the same directory as the ORIGINAL file with
    extensions '.current', '.parent' or '.other' corresponding to copies of the
    CURRENT, PARENT and OTHER files.

    You can then proceed to `resolve` the different conflicts that may have
    happened when merging. You can `list` the conflicts, and then `resolve` them
    one by one. Whenever you made a mistake, and want to quickly undo a
    resolution, use the `undo` command.

    Once you resolved all conflicts, you can `commit` to save your changes in
    your repository. Committing automatically cleans the current directory from
    files created by hg-svnmerge, but you can also `clean` the directory
    whenever you want (for instance, when you do not want to merge anymore).
""" % (PROGRAM_NAME, __version__)

CLEAN_MATCH    = re.compile("^.+\.(current|parent|other)(\.\d+)?$")
CONFLICTS_FILE = ".hgconflicts"

# ------------------------------------------------------------------------------
#
# COLORED TERMINAL OUTPUT
#
# ------------------------------------------------------------------------------

BLACK = "BK"; RED = "RE"; BLUE="BL";  GREEN = "GR"; MAGENTA="MG"; CYAN = "CY"
BROWN = "BW"
PLAIN = ""  ; BOLD = "BOLD" 
CODES = {
  BLACK         :"00;30", BLACK+BOLD    :"01;30",
  RED           :"00;31", RED+BOLD      :"01;31",
  GREEN         :"00;32", GREEN+BOLD    :"01;32",
  BROWN         :"00;33", BROWN+BOLD    :"01;33",
  BLUE          :"00;34", BLUE+BOLD     :"01;34",
  MAGENTA       :"00;35", MAGENTA+BOLD  :"01;35",
  CYAN          :"00;36", CYAN+BOLD     :"01;36",
}

def format( message, color=BLACK, weight=PLAIN ):
  """Formats the message to be printed with the following color and weight"""
  return '[0m[' + CODES[color+weight] + 'm' + str(message) + '[0m'

# -----------------------------------------------------------------------------
#
# LOGGING
#
# -----------------------------------------------------------------------------

def ask( question ):
    print format(question, weight=BOLD) + " ",
    return sys.stdin.readline().lower().strip()

def error( *args ):
    print format("ERROR: ", color=RED, weight=BOLD) + format(
    " ".join(map(str,args)), color=RED)

def warning( *args ):
    print format(" ".join(map(str,args)),MAGENTA)

def info( *args ):
    print format(PROGRAM_NAME + ": " + " ".join(map(str,args)),CYAN)

def log( *args ):
    print " ".join(map(str,args))

# -----------------------------------------------------------------------------
#
# UTILITIES
#
# -----------------------------------------------------------------------------

def readlines(p):
    """Reads the content of the file at the given path and returns a list of its
    lines."""
    f = open(p, 'rt') ; t = f.read() ; f.close()
    return t.split("\n")

def cutpath( root, path ):
    """Cuts the root from the given path if the path is prefixed with the
    root."""
    if not root[-1] == "/": root = root + "/"
    if path.startswith(root): return path[len(root):]
    else: return path

def backup_existing( path ):
    """If the given path exists and is a file, the path will be copied to a file
    in the same directory, with the same name suffixed by a number (.1, .2, .3),
    depending on the number of already existing backups."""
    if not os.path.isfile(path): return
    new_path = path ; i = 1
    while os.path.exists(new_path):
        new_path = "%s.%s" % (path, i)
        i += 1
    shutil.copy(path, new_path)
    return new_path

def ensure_notexists( path ):
    if os.path.exists(path):
        raise Exception(path)

def diff_count( a, b ):
    """Returns the number of lines conflicting between a and b and the total
    number of lines in a."""
    # We count the lines with no conflict
    no_conflict = 0
    a, b        = readlines(a), readlines(b)
    for line in difflib.ndiff(a, b):
        if line.startswith(" "):
            no_conflict += 1
    return no_conflict / float(len(a)) * 100

# -----------------------------------------------------------------------------
#
# CONFLICTS CLASS
#
# -----------------------------------------------------------------------------

class Conflict:
    """Represents a conflict between two files."""

    RESOLVED   = "resolved"
    UNRESOLVED = "unresolved"
    SEPARATOR  = "--vs--"

    def __init__( self, number, path, state=None ):
        if not state: state = Conflict.UNRESOLVED
        assert type(number) == int
        self.number    = number
        self.state     = state
        self._path     = path

    def resolve(self):
        self.state = self.RESOLVED

    def unresolve(self):
        self.state = self.UNRESOLVED

    def path( self ):
        return self._path

    def current( self ):
        return self._path + ".current"

    def parent( self ):
        return self._path + ".parent"

    def other( self ):
        return self._path + ".other"

    @staticmethod
    def parse( line, number=-1 ):
        """Returns a new conflict from the given conflict string
        representation."""
        line     = line.strip()
        colon    = line.find(":")
        if not line or colon == -1: return
        number   = line[:colon].strip()
        sep      = line.find(Conflict.SEPARATOR)
        original = line[colon+1:sep].strip()
        if number.startswith("R"):
            status = Conflict.RESOLVED
            number = number[1:]
        else: status = Conflict.UNRESOLVED
        return Conflict(int(number), original, status)

    def asString( self ):
        a = cutpath(os.path.abspath(os.getcwd()), self.path())
        b = cutpath(os.path.abspath(os.getcwd()), self.other())
        p = self.state == self.RESOLVED and "R" or ""
        return "%s%4s: %s %s %s" % (p, self.number, a, self.SEPARATOR, b)

    def __str__( self ):
        return self.asString()

class Conflicts:
    """This is a utility class that represents the list of conflicts, and
    whether they are resolved or not. It is used by all commands, and makes it
    easy to manage the conflicts file."""

    def __init__( self, path ):
        # We look for the parent directory where the conflicts file is located
        search_path = path = os.path.abspath(path)
        last_path   = None
        while search_path != last_path:
            conflicts_path = os.path.join(search_path, CONFLICTS_FILE)
            hg_path        = os.path.join(search_path, ".hg")
            if os.path.isfile(conflicts_path): break
            if os.path.isdir(hg_path): break
            last_path   = search_path
            search_path = os.path.basename(last_path)
        # We modify the path to be the search path if we found either a HG repo
        # or a conflicts file
        if last_path != search_path: path = search_path
        # Now we can initialize the object
        self._path = os.path.join(path, CONFLICTS_FILE)
        self._conflicts = None
        self.load()

    def load( self ):
        """Reads the conflicts from the file, if it exists"""
        self._conflicts = []
        if not os.path.isfile(self._path): return
        f = file(self._path, "rt")
        # We read the lines and fill in the _conflicts list
        for line in f.readlines():
            result = Conflict.parse(line[:-1], number=len(self._conflicts))
            if result: self._conflicts.append(result)
        f.close()

    def save( self ):
        """Writes back the conflicts to the file, overwriting it."""
        f = file(self._path, "w")
        f.write(str(self))
        f.close()

    def resolved( self, number=None ):
        """Returns the list of resolved conflicts"""
        if number == None:
            return tuple(c for c in self._conflicts if c.state == Conflict.RESOLVED)
        else:
            res = tuple(c for c in self._conflicts if c.state ==
            Conflict.RESOLVED and c.number == number)
            if not res: return None
            else: return res[0]

    def unresolved( self, number=None):
        """Returns the list of unresolved conflicts"""
        if number == None:
            return tuple(c for c in self._conflicts if c.state == Conflict.UNRESOLVED)
        else:
            res = tuple(c for c in self._conflicts if c.state ==
            Conflict.UNRESOLVED and c.number == number)
            if not res: return None
            else: return res[0]

    def add( self, path, other ):
        """Adds a new conflict between the given files, and returns the conflict
        as a (STATE, ID, FILES) triple."""
        path    = os.path.abspath(path)
        other   = os.path.abspath(other)
        next    = 0
        # We do not add a conflict twice
        for c in self._conflicts:
            if  c.path()  != path \
            and c.other() != other:
                next += 1
            else:
                return c
        # Eventually adds the conflict
        next     = len(self.unresolved())
        conflict = Conflict(next, path)
        assert other == conflict.other(), "Internal error"
        self._conflicts.append(conflict)
        return conflict

    def asString(self, color=True):
        res = ""
        unresolved       = self.unresolved()
        resolved         = self.resolved()
        # We handle unresolved conflicts
        if unresolved:
            for conflict in unresolved:
                if color:
                    res += format(str(conflict), color=RED) + "\n"
                else:
                    res += str(conflict) + "\n"
        # And handle resolved conflicts
        if resolved:
            for conflict in resolved:
                if color:
                    res += format(str(conflict), color=GREEN) + "\n"
                else:
                    res += str(conflict) + "\n"
        # We remove the trailing EOL

        return res[:-1]

    def __str__( self ):
        return self.asString(color=False)

# -----------------------------------------------------------------------------
#
# COMMANDS
#
# -----------------------------------------------------------------------------


def add_conflict(root, path, other ):
    """Adds the given conflict to the list of conflicts (stored in a
    '.hgconflicts' file), in the given root directory."""
    conflicts = Conflicts(root)
    c = conflicts.add(path, other)
    conflicts.save()
    return c

def list_conflicts(rootdir):
    """Lists the conflicts in the given directory."""
    conflicts = Conflicts(rootdir)
    print conflicts.asString()

def resolve_conflict(rootdir, number, action="merge"):
    """Resolves the given conflict by merging at first."""
    conflicts = Conflicts(rootdir)
    number    = int(number)
    conflict  = conflicts.unresolved(number)
    if not conflict:
        error("No conflict found: %s" % (number))
        return
    elif conflict.state == Conflict.RESOLVED:
        warning("Conflict already resolved. Doing nothing.")
        return
    # Resolving the conflict
    conflict_file = format(conflict.path(),color=RED)
    if   action == "merge":
        log("Resolving conflict", conflict_file ,"by",
        format("manual merging",color=BLUE,  weight=BOLD))
        os.system("%s %s %s" % (MERGETOOL, conflict.path(), conflict.other()))
    elif action == "keep":
        log("Resolving conflict", conflict_file ,"by",
        format("keeping the file as it is",color=BLUE,  weight=BOLD))
        pass
    elif action == "update":
        log("Resolving conflict", conflict_file, "by",
        format("using the .other file", color=BLUE, weight=BOLD))
        shutil.copy(conflict.other(), conflict.path())
    else:
        raise Exception("Unknown resolution action: " + action)
    res = ask("Did you resolve the conflict (y/n) ? ")
    if res == "y":
        info("Conflict resolved")
        conflict.resolve()
    conflicts.save()

def resolve_conflicts(rootdir, *numbers):
    """Resolves the given list of conflicts"""
    conflicts = Conflicts(rootdir)
    numbers   = map(int, numbers)
    if not numbers:
       unresolved = conflicts.unresolved()
       if not unresolved:
           warning("No conflict to resolve")
           return
       for conflict in unresolved:
        resolve_conflict(rootdir, conflict.number) 
    else:
        for number in numbers:
           resolve_conflict(rootdir, number) 


def undo_conflicts(rootdir, *numbers):
    """Undo the given conflicts."""
    conflicts = Conflicts(rootdir)
    numbers   = map(int, numbers)
    warning("NOTE: Undoing conflicts will revert your changes on the conflict file.")
    for number in numbers:
        conflict = conflicts.resolved(number)
        if not conflicts:
            error("No conflict with id: %s" % (number))
            continue
        if conflict.state == Conflict.UNRESOLVED:
            error("Conflict is unresolved, so there is nothing to undo: %s" % (number))
            continue
        res = ask("Do you want to undo conflict on %s (y/n) ? " % (conflict.path()))
        if res == "y":
            log("Undoing conflict resolution, using %s as original data" % (conflict.current()))
            conflict.unresolve()
            shutil.copy(conflict.current(), conflict.path())
        else:
            log("Conflict left as it is.")

    conflicts.save()

def clean(rootdir):
    """Cleans the given directory from the conflict backup files and from the
    conflicts file itself."""
    # If there is a conflicts file, we remove it
    conflicts_file = os.path.join(rootdir, CONFLICTS_FILE)
    if os.path.isfile(conflicts_file): os.unlink(conflicts_file)
    # And we clean the directory
    for root, dirs, files in os.walk(rootdir):
        for name in files:
            if CLEAN_MATCH.match(name):
                path = os.path.join(root, name)
                print "Cleaning up:", cutpath(rootdir, path) 
                os.unlink(path)
        if ".hg" in dirs: dirs.remove(".hg")

# -----------------------------------------------------------------------------
#
# MAIN
#
# -----------------------------------------------------------------------------
RE_NUMBER = re.compile("\d+")
def run(args):
    """Runs the command with the given arguments."""
    root = os.path.abspath(os.getcwd())
    # Command: list [DIRECTORY]
    if len(args) in (1,2) and args[0] == "list":
        if len(args) == 2: root = os.path.abspath(args[1])
        # We list the conflicts in the directory
        list_conflicts(root)
        return 0
    # Command: resolve [CONFLICT...]
    elif len(args) >= 1 and args[0] == "resolve":
        conflicts = filter(lambda c:RE_NUMBER.match(c), args[1:])
        if len(conflicts) == 1:
            conflict = conflicts[0]
            if   len(args) == 2:
                resolve_conflict(root, conflict, "merge")
            elif len(args) == 3:
                action = args[2].lower()
                resolve_conflict(root, conflict, action)
            else:
                error("resolve expects a list of conflicts, or a conflict and an action")
        else:
            # We list the conflicts in the directory
            resolve_conflicts(root, *conflicts)
        return 0
    # Command: undo CONFLICT...
    elif len(args) >= 2 and args[0] == "undo":
        conflicts = args[1:]
        # We list the conflicts in the directory
        undo_conflicts(root, *conflicts)
        return 0
    # Command: clean [DIRECTORY]
    elif len(args) in (1,2) and args[0].startswith("clean"):
        # The directory to be cleaned up may be given, so we ensure it is
        # present
        if len(args) == 2: root = os.path.abspath(args[1])
        # We clean the directory
        clean(root)
        return 0
    # Command: commit
    elif len(args) == 1 and args[0] == "commit":
        tip     = os.popen("hg tip").read()
        success = os.system("hg commit")
        success = os.popen("hg tip").read() != tip
        if success:
            info("Commit successful, cleaning up conflict resolution data.")
            clean(root)
            return 0
        else:
            info("Commit aborted, nothing done")
            return -1
    # Command: ORIGINAL PARENT NEWER
    elif len(args) == 3:
        info("Registering conflict")
        # We prepare the destination paths
        original, parent, other = map(os.path.abspath, args)
        original_copy = original + ".current"
        parent_copy   = original + ".parent"
        other_copy    = original + ".other"
        # We print the conflict
        conflict = add_conflict(root, original, other_copy)
        print "Conflict %4d:" % (conflict.number)
        print cutpath(root, original), "[" + str(int(diff_count(original, other))) + "%]"
        print "  parent      ", cutpath(root, parent_copy)
        print "  current     ", cutpath(root, original_copy)
        print "  other       ", cutpath(root, other_copy)
        # We backup .orig, .parent and .new that may already be tehre
        try:
            map(ensure_notexists, (parent_copy, original_copy, other_copy))
        except Exception, e:
            error("Previous conflict files present. Please run", PROGRAM_NAME, "clean")
            return -1
        # And we create the new ones
        shutil.copyfile(original, original_copy)
        shutil.copyfile(parent,   parent_copy)
        shutil.copyfile(other,    other_copy)
        info("You can resolve conflicts with:", PROGRAM_NAME, "resolve 0 (keep|update|merge)")
        return 0
    else:
        print USAGE
        return -1

if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))

# EOF
