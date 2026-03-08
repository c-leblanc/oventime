import pandas as pd
from pathlib import Path

from oventime.config import PROJECT_ROOT

_cache = {"data": None, "mtime": None}

def init_data():
    output_path = Path(PROJECT_ROOT / "data/processed/init_data.parquet")
    input_path = Path(PROJECT_ROOT / "data/raw/eco2mix.parquet")

    # Recalcule le parquet traité si les données brutes ont changé
    if not output_path.exists() or input_path.stat().st_mtime > output_path.stat().st_mtime:
        data = pd.read_parquet(input_path)
        
        data = data.drop(["perimetre","nature","date","heure"], axis=1)
        data = data.drop(['ech_physiques','taux_co2', 'ech_comm_angleterre', 'ech_comm_espagne','ech_comm_italie', 'ech_comm_suisse', 'ech_comm_allemagne_belgique'], axis=1)

        data["RENEWABLE"] = data["eolien"] + data["solaire"] + data["hydraulique_fil_eau_eclusee"]
        data["NUCLEAR"] = data["nucleaire"]
        data["STORAGE"] = data['hydraulique_lacs'] + data['hydraulique_step_turbinage'] + data['pompage'] + data['destockage_batterie'] + data['stockage_batterie']
        data["GAS_CCG"] = data['gaz_ccg']
        data["GAS_TAC"] = data['gaz_tac']
        data["OTHER"] = data['charbon']+data['gaz_autres']+data['fioul_tac']+data['fioul_autres']+data['gaz_cogen']+data['fioul_cogen']+data["bioenergies"]

        data = data[["RENEWABLE","NUCLEAR","STORAGE","GAS_CCG","GAS_TAC","OTHER"]]
        
        # drop the observations where data is not available
        data = data.dropna(how="any")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        data.to_parquet(output_path)
        _cache["data"] = data
        _cache["mtime"] = output_path.stat().st_mtime
        return data

    # Recharge depuis disque uniquement si le fichier a changé depuis le dernier appel
    current_mtime = output_path.stat().st_mtime
    if _cache["data"] is None or _cache["mtime"] != current_mtime:
        _cache["data"] = pd.read_parquet(output_path)
        _cache["mtime"] = current_mtime
    
    return _cache["data"]


if __name__ == "__main__":
    print(init_data())
