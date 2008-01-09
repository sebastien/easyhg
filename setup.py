#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Mercurial-Easy
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 09-Feb-2006
# Last mod  : 09-Feb-2007
# -----------------------------------------------------------------------------

import sys ; sys.path.insert(0, "Sources")
from distutils.core import setup

SUMMARY     = "A collection of tools to make Mercurial (even more) user friendly"
DESCRIPTION = """\
Mercurial-Easy notably provides Easycommit and Easymerge which make commiting
and merging in Mercurial a real pleasure. Mercurial-Easy uses the amazing
URWID command-line GUI library, which is embedded in this package.
"""
# ------------------------------------------------------------------------------
#
# SETUP DECLARATION
#
# ------------------------------------------------------------------------------

setup(
    name         = "Mercurial-Easy",
    version      = "0.9.4",

    author       = "Sebastien Pierre", author_email = "sebastien@ivy.fr",
    description   = SUMMARY, long_description  = DESCRIPTION,
    license      = "Revised BSD License",
    keywords     = "Mercurial, dvcs, scm, tool, interface, gui, command-line",
    url          = "http://www.ivy.fr/mercurial/easy",
    package_dir  = { "": "Sources" },
    modules_dir  = { "": "Sources" },
    packages     = ["easyhg","urwid"],
    py_modules      = ["urwide"],
    scripts      = ["Sources/easyhg/easymerge.py"]
)

# EOF
