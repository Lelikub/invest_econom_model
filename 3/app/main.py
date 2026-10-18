"""The only external entry point required to complete the assignment."""
import sys

for stream in (sys.stdout,sys.stderr):
    if hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8')

from src.interface import ApplicationInterface

if __name__=='__main__':
    raise SystemExit(ApplicationInterface().run())
