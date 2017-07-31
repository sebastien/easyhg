Easy-Hg / User-Friendly extensions for Mercurial
================================================

Mercurial Easy provides *command-line GUIs* for committing and merging
(operations you surely do daily), which provide both instant feedback, useful
information and error checking.

It features two main tools:

- `easycommit`, a curses-based commit interaface
- `easymerge`

Installation
============

EasyHG requires `urwid` to be installed.

```
pip install --user easyhg
```

Easycommit
----------

Easycommit has the following features:

- Fields to structure your commit: tags, scope, summary and details.
- Add/remove files to the commit
- Review changes directly from the editor

How to run easycommit:

```
hg easycommit
```

To enable easy commit, edit your `~/.hgrc`

```
[extensions]
easycommit = <PATH TO easyhg/commit.py>
```

alternatively, you can replace Mercurial's default commit with easycommit

```
[extensions]
commit = <PATH TO easyhg/commit.py>
```


Easymerge
----------

Easycommit has the following features:

- Conflicts can be resolved/unresolved in any order
- Review the differences between your merge and the current/other/base versions
- Quickly revert a bad merge
- Supports many tools: gvimdiff, meld, diffuse, kdiff3, etc

How to run easymerge:

```
easymerge
```

To enable easy commit, edit your `~/.hgrc`

```
[ui]
mergetool = <PATH TO easyhg/merge.py>
```

# EOF
