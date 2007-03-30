== Mercurial Easy Tools
== Friendly extensions to make users happy
-- Author: Sébastien Pierre <sebastien@xprima.com>
-- Version: 1.0

[Mercurial](http://www.selenic.com/mercurial) is an easy to use, versatile,
distributed revision control system written in the Python language. The
distributed nature of Mercurial makes it well-suited for open source
development, but sometimes less easy than other RCS when used in a centralized
style.

The setup we use at XPrima is as follows:

 - All projects are hosted on a single Linux file server, accessible through
   Samba and SSH.
 - Developers have their workspace on the same file server.
 - Developers work either on Win32 or Linux.

In particular:

 - We have a `Projects` directory with all projects (in development or retired)
 - We have a `Home` directory with all developer workspaces (where projects are
   checked out).

The purpose of the _XPrima Mercurial Extensions_ is to fulfill the following
requirements :

 - Add the notion of _central_ and _developer_ repositories
 - Add per-project meta-information such as description and list of developers
 - Allow per-project locking of files or directories
 - Provide tools to ease the resolution of conflicts (when merging)
 - Provide tools to ensure rich, structured commits
 - Provide tools to give developers and managers an overview of the development
   process

In this respect, we offer the following tools:

 - _Easychanges_, which eases the browsing of changes in the current repository
 - _Easycommit_, which eases the writing of richer commit messages
 - _Easymerge_, which makes merging easier by providing additional
   functionalities
 - _Project_, which adds per-project meta-information and the ability to define
   central and "development" repositories.

Mercurial Easychanges
====================

    TODO

Mercurial Easycommit
====================

    TODO

Mercurial Easymerge
===================

    The [Mercurial](http://www.selenic.com/mercurial) version control system has a
    default method of merging conflicts that has some limitations:

     - Conflicts must be resolved by the user in an arbitrary order
     - It is not possible to resolve a conflict in multiple, interrupted steps
     - It is not easy to get access to the different revisions in conflict

    The purpose of the Mercurial _Easymerge_ tool is simply to help developers
    resolve conflicts that may occur within a merge :

     - Conflicts are attributed a number, and can be resolved in any order
     - Conflict resolution can be undone if necessary
     - Resolution process can be stopped and resumed at will
     - All available revisions for a conflict are made available on the filesystem

    _Easymerge_ is available as a `hg-easymerge` command line utility, which has to be
    installed by adding the following line in your `~/.hgrc`:

    >	merge = hg-easymerge

    This enables _Easymerge_ to be invoked whenever you use the `hg merge` command.

    Usage
    -----

    Easymerge is automatically started when you do a `merge` with Mercurial. It will
    automatically populate your working directory with `.current`, `.other` and
    `.original` versions of each file where there is a conflict. You should not edit
    these files

    1. Listing conflicts
    --------------------

    >	hg-easymerge list

    2. Resolving a conflict
    -----------------------

    >	hg-easymerge resolve 0

    >	hg-easymerge resolve 0 merge

    >	hg-easymerge resolve 0 keep

    >	hg-easymerge resolve 0 update

    >	hg-easymerge resolve 5 9 2

    3. Undoing a resolution
    -----------------------

    >	hg-easymerge undo 0

    4. Commiting the changes
    ------------------------

    >	hg-easymerge commit

    5. Cleaning up
    --------------

    >	hg-easymerge clean

Mercurial Easyproject
=====================

    Mercurial can be used in a _centralized_ style, where there is a single location
    for the "main" (central) project repositories, and where each individual
    developer maintain its changes in a local repository, where it pushes and pull
    to the central repository.

    >                         <----------- clone ----------- 
    >    [WORKING REPOSITORY] <----------- pull  ----------- [CENTRAL REPOSITORY]
    >          (many)         ------------ push  ---------->        (one)

    In this case, it is useful to explicitly create a link between the working
    repository and the central repository, and to provide tools to easily check the
    state between both.

    Features
    --------

    The Mercurial project extension adds support for describing projects in such
    environments:

      - A project can be named and described
      - A project has a number of owners, responsible for the central repository,
        and a number of developers, having their own "branches"
      - A working repository for a project inherits the information from the central
        repository it is bound to.

    The main purpose of the project extension is to have an easy summary of the
    project status:

    >	hg project
    >	Name        : GuestPW (working)
    >	Description : Time-based Apache 1.3 authentication module
    >	Path        : /home/sebastien/Workspace/GuestPassword
    >	Parent      : /home/sebastien/Network/Home/Projects/guestpw
    >	Owner       : sebastien@xprima.com
    >	Developer   : sebastien@xprima.com

    Gives you information on the current project (wether development or central
    repository), by qualifying the state of the development repository or
    repositories compared to the central repository:

     == Relative state of repositories
     ===========================================================================
     Central state || Development state || Central qualifier || Dev qualifier
     ===========================================================================
     R50           || R50               || -                 || up to date
     ---------------------------------------------------------------------------
     R51           || R50               || -                 || out of date
     ---------------------------------------------------------------------------
     R50           || R51               || incoming change   || outgoing change
     ---------------------------------------------------------------------------
     R50           || R50 (alt)         || incoming branch   || outgoing branch
     ---------------------------------------------------------------------------
     local changes || -                 || changed           || central changed
     ---------------------------------------------------------------------------
     -             || local changes     || in development    || in development
     ===========================================================================

    Additional .hgrc properties
    ---------------------------

    Some properties were added to the `.hg/hgrc` file, which are all contained
    within the `[project]` section.

     == Project extension properties
     ===========================================================================
     Property      || Type        || Description
     ===========================================================================
     name          || central     || project name
     ---------------------------------------------------------------------------
     description   || central     || project description
     ---------------------------------------------------------------------------
     owner(s)      || central     || name and email of project owners. Owners are 
                   ||             || responsible for ensuring the quality of the
                   ||             || project.
     ---------------------------------------------------------------------------
     developers(s) || central     || name and email of people who contributed
                   ||             || to the project.
     ---------------------------------------------------------------------------
     parent        || development || the path to the parent central directory
     ===========================================================================

# vim: ts=4 tw=80 sw=4 et fenc=latin-1 syn=kiwi
