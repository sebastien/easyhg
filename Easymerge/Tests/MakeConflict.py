import os
from os import system, chdir, getcwd

DATA = (
	"Hello",
	"Hello World",
	"Hello, people from the world !",
	"Hello,\nPeople from\nThe World\n!",
)
 

def write(path, data):
	f = file(path, "w")
	f.write(data)
	f.close()

def hg(repo, command):
	chdir(repo)
	system("hg " + command)
	chdir("..")

def makeRepos():
	A = "branch-a"
	B = "branch-b"
	system("rm -rf branch-a ; mkdir branch-a")
	system("rm -rf branch-b" )
	hg(A, "init")
	write(A + "/hello.txt", DATA[0])
	hg(A, "add hello.txt")
	hg(A, "commit -m 0 -u me")
	write(A + "/hello.txt", DATA[1])
	hg(A, "commit -m 1 -u me")
	system("hg clone " + A + " " + B)
	write(A + "/hello.txt", DATA[2])
	hg(A, "commit -m 2 -u me")
	write(B + "/hello.txt", DATA[3])
	hg(B, "commit -m 2alt -u me")
	print "Now if you pull from any of the repos, you have a conflict !"

if __name__ == "__main__":
	chdir(os.path.dirname(os.path.abspath(__file__)))
	print getcwd()
	print "Making conflicts"
	makeRepos()

