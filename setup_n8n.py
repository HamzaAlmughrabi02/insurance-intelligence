"""Prepare the isolated V2 workflow definitions; use the documented deployment command."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parent/'prepare_v2_n8n.py'),run_name='__main__')
