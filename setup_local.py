import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parent/"configure_v2.py"),run_name="__main__")
