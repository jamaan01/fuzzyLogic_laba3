import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import FuzzyEditor


if __name__ == "__main__":
    FuzzyEditor().mainloop()
