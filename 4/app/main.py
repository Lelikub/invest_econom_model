"""Single external entry point. Paths are independent of caller's cwd."""
from src.interface import ApplicationInterface

if __name__=='__main__':
    raise SystemExit(ApplicationInterface().run())
