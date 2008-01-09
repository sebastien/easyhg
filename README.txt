== Mercurial-Easy
== UI love for Hg


What is it ?
============

Even though it's documented
[here](http://www.selenic.com/mercurial/wiki/index.cgi/EasycommitExtension) and
[here](http://www.selenic.com/mercurial/wiki/index.cgi/EasymergeExtension) the
_Mercurial-Easy_ project aims at providing a set of cool tools to make your life
easier.

Mercurial Easy provides *command-line GUIs* for commiting and merging
(operations you surely do daily), which provide both instant feedback, useful
information and easy of use.

Also, you can enjoy the fact that these tools are written in Python too and are
released under the BSD license.

We've been enjoying Mercurial-Easy since 2006 !

How does it look like ?
=======================

See it for yourself !

<img src="http://www.ivy.fr/mercurial/easy/commit.png" />

<img src="http://www.ivy.fr/mercurial/easy/merge.png" />

How to install ?
================

First you should get the [latest
tarball](http://www.ivy.fr/mercurial/easy/mercurial-easy-latest.tar.gz) if you
don't alrady have it. Of course you need [Python](http://www.python.org) and
[Mercurial](http://www.selenic.com/mercurial) too (but we don't support 0.9.5
yet).

Then, you can unpack your tarball, cd into it, and start doing this:

>    python setup.py install

or

>    python setup.py intall --prefix=~/where/you/want

You will then have the following modules installed:

 -    'easyhg' the Mercurial-Easy project
 -    'urwid' a library required by Mercurial-Easy
 -    'urwide' another library also required by Mercurial-Easy
 -    'easymerge.py' which is a script that you should use when mergeing

To know where Mercurial-Easy is installed, simply do:

>	python -c 'import os,easyhg;print os.path.dirname(os.path.abspath(easyhg.__file__))'

For me it will tell you that it is installed here:

>   /Users/sebastien/Local/lib/python2.5/site-packages/easyhg

You can now edit your '~/.hgrc' file:

>	[extensions]
>	# Mercurial-Easy tools
>	commit    = ~/Projects/Mercurial-Easy/Sources/easyhg/easycommit.py
>	changes   = ~/Projects/Mercurial-Easy/Sources/easyhg/easychanges.py
>	project   = ~/Projects/Mercurial-Easy/Sources/easyhg/easyproject.py

And you can disable any of these, of course !

# EOF
