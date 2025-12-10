import requests
from datetime import timedelta
import pandas as pd
import time

from oven_time.config import PROJECT_ROOT, RETENTION_DAYS, FREQ_UPDATE

BASE_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-national-tr/records"

def fetch_raw(start, end, limit=100, vars=None):
    where = f"date_heure:['{start}' TO '{end}']"

    params = {
        "where": where,
        "order_by": "date_heure ASC",
        "limit": limit,
    }

    if vars is not None:
        # s’assurer qu’on a toujours date_heure
        select_cols = ["date_heure"] + list(vars)
        params["select"] = ",".join(select_cols)

    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()["results"]


def fetch_df(start=None, end=None, limit=100, vars=None) -> pd.DataFrame:
    if end is None:
        end = pd.Timestamp.now(tz="UTC")
    if start is None:
        start = end - timedelta(days=RETENTION_DAYS)

    rows = fetch_raw(start=start, end=end, limit=limit, vars=vars)

    # Aucun résultat -> renvoyer un DF vide avec un index temporel
    if not rows:
        return pd.DataFrame().set_index(
            pd.DatetimeIndex([], name="date_heure")
        )

    # Aplatit la structure JSON
    df = pd.json_normalize(rows)

    # Si la colonne "date_heure" n'existe pas directement, essayer "fields.date_heure"
    if "date_heure" not in df.columns:
        if "fields.date_heure" in df.columns:
            df["date_heure"] = df["fields.date_heure"]
        else:
            # Pas de colonne exploitable -> renvoyer un DF vide explicite
            return pd.DataFrame().set_index(
                pd.DatetimeIndex([], name="date_heure")
            )

    # parse la date et met en index
    df["date_heure"] = pd.to_datetime(df["date_heure"], errors="coerce")
    df = df.dropna(subset=["date_heure"])

    if df.empty:
        return pd.DataFrame().set_index(
            pd.DatetimeIndex([], name="date_heure")
        )

    df = df.set_index("date_heure").sort_index()

    return df

def update_eco2mix_data(retention_days=RETENTION_DAYS, verbose=True):
    def log(msg):
        if verbose:
            print(msg)
    
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load existing data
    eco2mix_file = raw_dir / "eco2mix.csv"
    if eco2mix_file.exists():
        existing = pd.read_csv(eco2mix_file, index_col=0, parse_dates=True)
        while len(existing) > 0 and existing.iloc[-1].isna().any():
            existing = existing.iloc[:-1]
        if len(existing) == 0:
            last_timestamp = None
            log("Existing data - None left after trimming")
        else:
            last_timestamp = existing.index.max()
            log(f"Existing data - Last timestamp: {last_timestamp}")
    else:
        existing = None
        last_timestamp = None
        log("Existing data - None")

    # 2. Determine download window
    now = pd.Timestamp.now(tz="UTC").floor("15min")
    if last_timestamp is None:
        start = now - pd.Timedelta(days=retention_days)
    else:
        start = last_timestamp + pd.Timedelta(minutes=15)
    log(f"Attempting to download data starting from: {start}")

    if start >= now:
        log("Data already up to date. Nothing to download.")
        return

    # 3. Download missing data & concatenate
    while start < now:
        try:
            new_data = fetch_df(start=start, end=now)
        except Exception as e:
            log(f"[update_eco2mix_data] Erreur dans fetch_df(start={start}, end={now}) : {e!r}")
            # on sort de la boucle pour ne pas boucler infiniment
            break

        # Si fetch_df renvoie None ou un DF vide : on log et on sort
        if new_data is None or len(new_data) == 0:
            log(f"[update_eco2mix_data] Aucune donnée reçue pour la fenêtre {start} -> {now}, arrêt du téléchargement.")
            break

        # Si l’index n’est pas de type datetime (au cas où)
        if not isinstance(new_data.index, pd.DatetimeIndex):
            log(f"[update_eco2mix_data] Index non temporel sur new_data, abandon de cette fenêtre.")
            break

        log(f"Downloaded data from {new_data.index.min()} to {new_data.index.max()}")

        if existing is not None:
            existing = pd.concat([existing, new_data])
        else:
            existing = new_data

        last_timestamp = existing.index.max()
        start = last_timestamp + pd.Timedelta(minutes=15)

    if existing is None or len(existing) == 0:
        log("Aucune donnée eco2mix disponible, rien à sauvegarder.")
        return

    # 5. Remove data older than retention_days
    limit = now - pd.Timedelta(days=retention_days)
    existing = existing[existing.index >= limit]
    log(f"Removed data older than: {limit}")

    # 6. Save final cleaned dataset
    existing.to_csv(eco2mix_file)
    log("Update complete.")



def background_updater(retention_days=RETENTION_DAYS, freq=FREQ_UPDATE):
    while True:
        update_eco2mix_data(retention_days=retention_days, verbose=True)
        time.sleep(freq * 60)  # freq: frequency of updates in minutes



if __name__ == "__main__":
    update_eco2mix_data(verbose=True)
