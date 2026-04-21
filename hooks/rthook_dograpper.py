import sys
import os

# pathex entries are analysis-time only; add src to sys.path at runtime too
_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src = os.path.join(_here, "src")
if _src not in sys.path and os.path.isdir(_src):
    sys.path.insert(0, _src)
