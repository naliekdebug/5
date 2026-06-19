import os
import sys

# Ensure the repository root is importable so `import autotrader` works when
# running the test suite without installing the package.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
