import sys
from pathlib import Path

# Ajouter src au PYTHONPATH
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from oven_time.bot import main  # adapte au point d’entrée réel

if __name__ == "__main__":
    main()
