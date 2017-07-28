import sys

# ------------------------------------------------------------------------------
#
# COLORED TERMINAL OUTPUT
#
# ------------------------------------------------------------------------------

BLACK = "BK"; RED = "RE"; BLUE="BL";  GREEN = "GR"; MAGENTA="MG"; CYAN = "CY"
BROWN = "BW"; YELLOW = "YL" ; WHITE = "WH"
PLAIN = ""  ; BOLD = "BOLD"
CODES = {
  BLACK         :"00;30", BLACK+BOLD    :"01;30",
  RED           :"00;31", RED+BOLD      :"01;31",
  GREEN         :"00;32", GREEN+BOLD    :"01;32",
  BROWN         :"00;33", BROWN+BOLD    :"01;33",
  BLUE          :"00;34", BLUE+BOLD     :"01;34",
  MAGENTA       :"00;35", MAGENTA+BOLD  :"01;35",
  CYAN          :"00;36", CYAN+BOLD     :"01;36",
  WHITE         :"00;37", WHITE+BOLD    :"01;37",
  YELLOW        :"00;28", YELLOW+BOLD   :"01;28",
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
	sys.stdout.write(format(question, weight=BOLD, color=WHITE) + " ")
	return sys.stdin.readline().lower().strip()

def error( *args ):
	sys.stdout.write(format("ERROR: ", color=RED, weight=BOLD) + format(
	" ".join(map(str,args)), color=RED) + "\n")

def warning( *args ):
	sys.stdout.write(format(" ".join(map(str,args)), YELLOW + BOLD) + "\n")

def info( *args ):
	sys.stdout.write(format(" ".join(map(str,args)),GREEN + BOLD) + "\n")

def log( *args ):
	sys.stdout.write(" ".join(map(str,args)) + "\n")
