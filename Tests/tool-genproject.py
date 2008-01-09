# NOTE: This is a WIP test tool script to test the tools
import sys, os, random, shutil

# This was generated using 'do findr .py | xargs -n1 basename | cut -d. -f1 | sort | uniq | xargs echo'
FILENAMES = """actionscript actuator ajp ajp__base ajp__fork ajp_base ajp_fork amazon api-ssh apply-template asyncpass base basepage blocks browse build c camera catalogue cellspace client colors comic comments complex context contracts core curl curlclient decoder defaultclient delicious describe desktop dialog dialogs docommand doinchildmatrix dparser dparserpy-syntax__error dparserpy-syntax_error drivers easyapi easychanges easycommit easymerge easyproject element encoder engine entry environment error escape events exif family_query fcgi fcgi__app fcgi__base fcgi__fork fcgi_app fcgi_base fcgi_fork filestore findsystem firefox-bin-linux firefox-bin-macos font font_family_groups fontprovider form formatting frame function future generate-jsxml gifmaker glFreeType glo glyph glyphquery grammar green grid guessdescription gzip helloworld hg-easycommit hg-easymerge hgcheckcommit hgprojects hgsvnmerge html html2kiwi htmlElements idjango imaging importer importingmodule inlines install-kit interaction interfaces java javascript jsdriver jsimport jsjoin jskiwi jsmin jsonfilter jsparser jstest kit kiwi2html kiwi2lout kiwi2twiki layouts light link-projects linking localfiles locals mail main markup material mergetool metadata_query model modelbase modeltypes modelwriter module mysqlstorage net nopathinfo normalize objectpath oldinterfaces openglBase openglGlut openglPygame page parameter parsing passes paste__factory paste_factory pieces pnuts polygonal_text polygontessellator preforkserver primitives project projects proxy publisher pygamefont python python-module-loader query render_1 render_2 renderer3d rendererBase reporter resolution resolver rest runtests scanner scgi scgi__app scgi__base scgi__fork scgi_app scgi_base scgi_fork scrape sdoc session setup shader sheet splitter sprite sqlitestorage sqlstorage storage sugar tag tags templates templating test test-asyncbridge test-caching test-memoization test-users test2 test3 test4 test5 test6 test7 test8 test9 tests-server testsupport text_3d themeBase threadedserver threadpool tool-genproject toolsfont tpg tpggrammar tracking tree ttffiles typecast typedefs typer update-kit urls urwide users utilities vectorutilities vertex viewer web widgets wikipage win2k world writer wsgi""".split()

EXTENSIONS="txt py c cpp html js css".split()

def pick( some_list ):
	M  = len(some_list) - 1
	return some_list(int(random.random() * M))

def random( m, M ):
	return m + int(random.random() * (M-m))
	
def generate_filename():
	return "%s.%s" % (pick(FILENAME), pick(EXTENSION))

def generate_modification( path ):
	assert os.path.isfile(path)
	f = file(path, 'r') ; t = f.read() ; f.close()
	for change in random(1,20):
		pass
	
def generate_project( path ):
	pass

# EOF
