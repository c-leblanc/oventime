import pandas as pd
from pathlib import Path

from oventime.config import PROJECT_ROOT

def init_data():
    # If no recent changes in raw data, reloads last processed data
    output_path = Path(PROJECT_ROOT / "data/processed/init_data.parquet")
    input_path = Path(PROJECT_ROOT / "data/raw/eco2mix.parquet")
    if output_path.exists():
        out_mtime = output_path.stat().st_mtime
        if input_path.stat().st_mtime <= out_mtime:
            return pd.read_parquet(output_path)
    
    data = pd.read_parquet(PROJECT_ROOT / "data/raw/eco2mix.parquet")
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

    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    data.to_parquet(PROJECT_ROOT / "data/processed/init_data.parquet")

    return(data)

if __name__ == "__main__":
    print(init_data())
