"""Restart only this edition's backend after source updates."""
import os,sys
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parent
pid=ROOT/'backend.pid'
if pid.exists():
 try:
  p=psutil.Process(int(pid.read_text()))
  assert any(str(ROOT/'backend/integration.py').lower().replace('\\','/')==a.lower().replace('\\','/') for a in p.cmdline())
  p.terminate();p.wait(15)
 except psutil.NoSuchProcess:pass
sys.path.insert(0,str(ROOT));import launcher
launcher.spawn([sys.executable,'-u',str(ROOT/'backend/integration.py')],'backend',dict(os.environ,PORT='8786'))
print('Restarted isolated V2 backend only.')
