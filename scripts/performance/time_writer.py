import resource
import subprocess
import sys
import pathlib

result = subprocess.run(sys.argv[2:])
pathlib.Path(sys.argv[1]).write_text(str(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
sys.exit(result.returncode)
