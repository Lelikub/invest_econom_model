from pathlib import Path
import os
import sys

APP=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
os.environ.setdefault("MPLCONFIGDIR", str(APP/".mplcache"))
if (APP/".deps").is_dir():
    sys.path.insert(0,str(APP/".deps"))

from src.interface import ApplicationInterface

if __name__=="__main__":
    raise SystemExit(ApplicationInterface(APP).run())
