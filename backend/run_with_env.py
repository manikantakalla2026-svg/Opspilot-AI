"""Run a command with a dotenv file, without printing secrets or changing root env."""
import os
from pathlib import Path
import subprocess
import sys
from dotenv import dotenv_values

values = {key: value for key, value in dotenv_values(sys.argv[1]).items() if value is not None}
raise SystemExit(subprocess.call(sys.argv[2:], env={**os.environ, **values}))
