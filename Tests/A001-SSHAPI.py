#!/usr/bin/python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 fenc=latin-1 noet

from easyhg import easyapi

ssh_repo = easyapi.Repository("/home/sebastien/Workspace/James")
print ssh_repo.changes()
print ssh_repo.tags()
# EOF
