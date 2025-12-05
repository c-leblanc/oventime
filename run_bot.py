import sys
from pathlib import Path
import threading

# Ajouter src au PYTHONPATH
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from oven_time import bot, api_eco2mix


if __name__ == "__main__":
    
    # démarrer la tâche d'update en arrière-plan
    t = threading.Thread(target=api_eco2mix.background_updater, daemon=True)
    t.start()

    bot.main()
