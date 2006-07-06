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

MERGETOOL = 'gvimdiff'
if os.environ.has_key("MERGETOOL"): MERGETOOL = os.environ.get("MERGETOOL")

USAGE = """\
hg-svnmerge %s

    hg-svnmerge is tool for Subversion-like merging in Mercurial. It gives more
    freedom to the resolution of conflicts, the user can individually pick the
    changes and resolve them with its preferred set of tools.

    The tool used to do the merging has to be set into this script or into the
    $MERGETOOL environment variable. By default, it is 'gvimdiff'

Commands :

    list    [DIRECTORY]             - list registered conflicts
    resolve [CONFLICT]              - resolves all/given conflict(s)
    undo    [CONFLICT]              - undo a resolution
    clean   [DIRECTORY]             - cleans up the conflict files
    commit                          - try to commit the changes (TODO)

    CURRENT PARENT OTHER            - registers a conflict (used by Mercurial)

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
""" % (__version__)

CLEAN_MATCH    = re.compile("^.+\.(current|parent|other)(\.\d+)?$")
CONFLICTS_FILE = ".hgconflicts"

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

class Conflicts:
    """This is a utility class that represents the list of conflicts, and
    whether they are resolved or not. It is used by all commands, and makes it
    easy to manage the conflicts file."""

    RESOLVED   = "resolved"
    UNRESOLVED = "unresolved"

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
            line = line[:-1]
            line = line.strip()
            if not line or line.find(":") == -1: continue
            colon  = line.find(":")
            number = line[:colon].strip()
            files  = line[colon+1:].strip()
            if number.startswith("R"):
                self._conflicts.append([Conflicts.RESOLVED, int(number[1:]), files])
            else:
                self._conflicts.append([Conflicts.UNRESOLVED, int(number), files])
        f.close()

    def save( self ):
        """Writes back the conflicts to the file, overwriting it."""
        f = file(self._path, "w")
        f.write(str(self))
        f.close()

    def resolved( self ):
        """Returns the list of resolved conflicts"""
        return tuple(c for c in self._conflicts if c[0] == Conflicts.RESOLVED)

    def unresolved( self ):
        """Returns the list of unresolved conflicts"""
        return tuple(c for c in self._conflicts if c[0] == Conflicts.UNRESOLVED)

    def add( self, original, parent ):
        """Adds a new conflict between the given files, and returns the conflict
        as a (STATE, ID, FILES) triple."""
        original = os.path.abspath(original)
        parent   = os.path.abspath(parent)
        next     = 0
        # We do not add a conflict twice
        conflict = "'%s' '%s'" % (original, parent)
        for c in self._conflicts:
            if conflict == c[-1]: return c
            next += 1
        next     = len(self.unresolved())
        c = [Conflicts.UNRESOLVED, next + 1, conflict]
        self._conflicts.append(c)
        return c

    def resolve( self, conflictid ):
        """Resolve the conflict with the given id. Returns the modified
        conflict of None if not found."""
        conflictid = int(conflictid)
        for conflict in self._conflicts:
            if conflict[1] == conflictid:
                conflict[0] = Conflicts.RESOLVED
                return conflict
        return None

    def unresolve( self, conflictid ):
        """Uneesolve the conflict with the given id. Returns the modified
        conflict of None if not found."""
        conflictid = int(conflictid)
        for conflict in self._conflicts:
            if conflict[1] == conflictid:
                conflict[0] = Conflicts.UNRESOLVED
                return conflict
        return None

    def __str__(self):
        res = ""
        u   = c = 0
        unc = self.unresolved()
        rec = self.resolved()
        # We handle unresolved conflicts
        if unc:
            res += "Unresolved conflicts\n"
            res += "====================\n"
            for c in self.unresolved():
                u += 1 ; res += "%4d:%s\n" % (u, c[2])
        else:
            res += "No unresolved conflicts\n"
        # And handle resolved conflicts
        if rec:
            res += "Resolved conflicts\n"
            res += "==================\n"
            r    = 0
            for c in self.resolved():
                r += 1 ; res += "%4s:%s\n" % ("R" + str(r), c[2])
        else:
            res += "No resolved conflicts\n"
        # We remove the trailing EOL
        return res[:-1]

# -----------------------------------------------------------------------------
#
# COMMANDS
#
# -----------------------------------------------------------------------------

def add_conflict(root, current, other ):
    """Adds the given conflict to the list of conflicts (stored in a
    '.hgconflicts' file), in the given root directory."""
    conflicts = Conflicts(root)
    c = conflicts.add(current, other)
    conflicts.save()
    return c

def list_conflicts(rootdir):
    """Lists the conflicts in the given directory."""
    conflicts = Conflicts(rootdir)
    print conflicts

def resolve_conflicts(rootdir, *numbers):
    """Lists the conflicts in the given directory."""
    conflicts = Conflicts(rootdir)
    numbers   = map(int, numbers)
    for _, cid, files in conflicts.unresolved():
        if not numbers or cid in numbers:
            print "Resolving conflict", cid, "between", files
            os.system("meld " + files)
            print "Did you resolve the conflict (y/n) ? ",
            res = sys.stdin.readline().lower().strip()
            if res == "y":
                print "Conflict resolved"
                conflicts.resolve(cid)
    conflicts.save()

def undo_conflicts(rootdir, *numbers):
    """Undo the given conflicts."""
    conflicts = Conflicts(rootdir)
    numbers   = map(int, numbers)
    print "NOTE: Undoing conflicts will revert your changes. Use with caution."
    for state, cid, files in conflicts.resolved():
        if state == Conflicts.UNRESOLVED: continue
        if numbers == None or cid in numbers:
            print "Conflict", cid, files
            print "Do you want to undo this conflict (y/n) ? ",
            res = sys.stdin.readline().lower().strip()
            if res == "y":
                print "Undoing the resolution"
                conflicts.unresolve(cid)
                source = files[1:].find("'")
                source = files[1:source+1]
                shutil.copy(source + ".current", source)
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

def run(args):
    """Runs the command with the given arguments."""
    root = os.path.abspath(os.getcwd())
    # Command: clean [DIRECTORY]
    if len(args) in (1,2) and args[0] == "list":
        if len(args) == 2: root = os.path.abspath(args[1])
        # We list the conflicts in the directory
        list_conflicts(root)
        return 0
    # Command: resolve [CONFLICT...]
    elif len(args) >= 1 and args[0] == "resolve":
        conflicts = ()
        if len(args) == 1: conflicts = args[1:]
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
    elif len(args) in (1,2) and args[0] == "clean":
        # The directory to be cleaned up may be given, so we ensure it is
        # present
        if len(args) == 2: root = os.path.abspath(args[1])
        # We clean the directory
        clean(root)
        return 0
    # Command: ORIGINAL PARENT NEWER
    elif len(args) == 3:
        # We prepare the destination paths
        original, parent, other = map(os.path.abspath, args)
        original_copy = original + ".current"
        parent_copy   = original + ".parent"
        other_copy    = original + ".other"
        # We print the conflict
        _, cid, _ = add_conflict(root, original, other_copy)
        print "Conflict %4d:" % (cid)
        print cutpath(root, original), "[" + str(int(diff_count(original, other))) + "%]"
        print "  parent      ", cutpath(root, parent_copy)
        print "  current     ", cutpath(root, original_copy)
        print "  other       ", cutpath(root, other_copy)
        # We backup .orig, .parent and .new that may already be tehre
        map(backup_existing, (parent_copy, original_copy, other_copy))
        # And we create the new ones
        shutil.copyfile(original, original_copy)
        shutil.copyfile(parent,   parent_copy)
        shutil.copyfile(other,    other_copy)
        return 0
    else:
        print USAGE
        return - 1

if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))

# EOF
