"""Standalone PyInstaller entry point — outside the dograpper package to avoid __main__ conflicts."""
from dograpper.cli import main

if __name__ == "__main__":
    main()
