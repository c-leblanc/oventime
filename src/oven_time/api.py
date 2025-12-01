from entsoe import EntsoePandasClient
import pandas as pd
import os
from pathlib import Path

from oven_time.config import COUNTRY_CODE
from oven_time.config import ENTSOE_API_KEY
from oven_time.config import PROJECT_ROOT

def download_raw_data(start, end):
    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)

    load = client.query_load(country_code=COUNTRY_CODE, start=start, end=end)
    generation = client.query_generation(country_code=COUNTRY_CODE, start=start, end=end, psr_type=None, include_eic=False)
    print("Data downloaded from "+str(start)+" to "+str(end))

    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    load.to_csv(raw_dir / "load.csv")
    generation.to_csv(raw_dir / "generation.csv")

def download_raw_data_INSTANT():
    now = pd.Timestamp.now(tz='UTC').ceil("15min")
    just_before = now - pd.Timedelta(hours=0.25)
    download_raw_data(start=just_before,end=now)

def download_raw_data_12H():
    now = pd.Timestamp.now(tz='UTC').ceil("15min")
    halfday_ago = now - pd.Timedelta(hours=12)
    download_raw_data(start=halfday_ago,end=now)

def download_raw_data_24H():
    now = pd.Timestamp.now(tz='UTC').ceil("15min")
    yesterday = now - pd.Timedelta(hours=24)
    download_raw_data(start=yesterday,end=now)

def update_raw_data(retention_days=7):
    """
    Met à jour les données load.csv et generation.csv :
    - Lit les données existantes si elles existent
    - Trouve la période manquante
    - Télécharge uniquement les nouveaux points
    - Supprime les données trop anciennes
    - Sauvegarde proprement
    """

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------
    # 1. Charger données existantes
    # -----------------------------
    load_file = raw_dir / "load.csv"
    gen_file = raw_dir / "generation.csv"

    if load_file.exists():
        load = pd.read_csv(load_file, index_col=0, parse_dates=True)
        last_timestamp = load.index.max()
        print("Last time stamp already present in load file: "+str(last_timestamp))
    else:
        load = None
        last_timestamp = None
        print("No last time stamp in load file.")

    if gen_file.exists():
        generation = pd.read_csv(gen_file, index_col=0, header=[0,1], parse_dates=True)
        last_timestamp_gen = generation.index.max()
        print("Last time stamp already present in generation file: "+str(last_timestamp_gen))
    else:
        generation = None
        print("No last time stamp in generation file.")

    # ----------------------------------------
    # 2. Déterminer la période à télécharger
    # ----------------------------------------
    now = pd.Timestamp.now(tz='UTC').floor("15min")
    print("Current time considered: "+str(now))

    if last_timestamp is None:
        # Aucun fichier existant → télécharger 30 jours par défaut
        start = now - pd.Timedelta(days=retention_days)
    else:
        start = last_timestamp + pd.Timedelta(minutes=15)  # éviter duplicate
        print("Download attempt will start from "+str(start))

    if start >= now:
        print("Data already up to date.")
        return

    # ------------------------------
    # 3. Télécharger données manquantes
    # ------------------------------
    
    try:
        new_load = client.query_load(COUNTRY_CODE, start=start, end=now)
        new_gen = client.query_generation(COUNTRY_CODE, start=start, end=now,
                                            psr_type=None, include_eic=False)
        # Convertir en UTC
        new_load.index = new_load.index.tz_convert("UTC")
        new_gen.index = new_gen.index.tz_convert("UTC")

        print("Data downloaded from "+str(start)+" to "+str(now))
    except Exception:
        print("No new data available (Last data = "+str(last_timestamp)+").")
        return

    # ------------------------------
    # 4. Concaténer avec les anciennes
    # ------------------------------
    if load is not None:
        load = pd.concat([load, new_load])
        generation = pd.concat([generation, new_gen])
    else:
        load = new_load
        generation = new_gen

    # -----------------------------------------
    # 5. Supprimer les données trop anciennes
    # -----------------------------------------
    limit = now - pd.Timedelta(days=retention_days)
    load = load[load.index >= limit]
    generation = generation[generation.index >= limit]
    print("Data before "+str(limit)+" removed.")

    # ------------------------------
    # 6. Sauvegarde finale
    # ------------------------------
    load.to_csv(load_file)
    generation.to_csv(gen_file)

    print("Update finished.")



if __name__ == "__main__":
    update_raw_data()