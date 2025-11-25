import pandas as pd
from oven_time.config import PROJECT_ROOT

def static_mix():
    data = pd.read_csv(PROJECT_ROOT / "data/processed/full_data.csv")
    
    # define tech columns (exclude index, time, Load)
    cols = data.columns.tolist()
    tech_cols = [c for c in cols if c not in ["time","Load"]]

    # compute residual = exchanges
    data["Exchanges"] = data["Load"] - data[tech_cols].sum(axis=1)

    # compute shares
    share_df = data.copy()
    for c in tech_cols + ["Exchanges"]:
        share_df[c] = share_df[c] / share_df["Load"]

    share_df.to_csv(PROJECT_ROOT / "data/processed/static_mix.csv", index=False)


def variation_mix():
    data = pd.read_csv(PROJECT_ROOT / "data/processed/full_data.csv")

    # 0. Ordonner et indexer par le temps
    data = data.sort_values("time").set_index("time")

    # 1. Colonnes techno 
    cols = data.columns.tolist()
    tech_cols = [c for c in cols if c not in ["Load"]]  # adapte selon tes noms

    # 2. Définir Exchanges en variations
    data["Trade"] = data["Load"] - data[tech_cols].sum(axis=1)

    # 3. Recalculer Load_RES en variations à partir des colonnes de d
    data["Load_RES"] = (
        data["Load"]
        - data["Wind_off"]
        - data["Wind_on"]
        - data["Solar"]
        - data["RoR"]
    )

    # 4. On ne garde plus les composantes RES dans la suite
    data = data.drop(columns=["Load", "Wind_off", "Wind_on", "Solar", "RoR"])

    # 5. Passer en variations (diff)
    data = data.diff()

    # 6. Calculer les parts (delta techno / delta Load_RES)
    share_df = data.copy()
    cols = data.columns.tolist()
    for c in cols:
        share_df[c] = share_df[c] / share_df["Load_RES"]

    share_df.to_csv(PROJECT_ROOT / "data/processed/variation_mix.csv", index=True)
