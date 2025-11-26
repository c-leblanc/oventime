import pandas as pd
from oven_time.config import PROJECT_ROOT
import oven_time.processing.format_table as fmt

def static_mix():
    data = fmt.init_data()
    
    # define tech columns (exclude index, time, Load)
    cols = data.columns.tolist()
    tech_cols = [c for c in cols if c not in ["time","load"]]

    # compute residual = exchanges
    data["TRADE"] = data["load"] - data[tech_cols].sum(axis=1)

    # compute shares
    share_df = data.copy()
    for c in tech_cols + ["TRADE"]:
        share_df[c] = share_df[c] / share_df["load"]

    share_df.to_csv(PROJECT_ROOT / "data/processed/static_mix.csv", index=False)
    return(share_df)


def variation_mix():
    data = fmt.init_data()

    # 0. Ordonner et indexer par le temps
    data = data.sort_values("time").set_index("time")

    cols = data.columns.tolist()
    tech_cols = [c for c in cols if c not in ["load"]]  # adapte selon tes noms

    data["TRADE"] = data["load"] - data[tech_cols].sum(axis=1)

    # 3. Recalculer Load_RES en variations à partir des colonnes de d
    data["load_RES"] = data["load"] - data["RENEWABLE"]

    # 4. On ne garde plus les composantes RES dans la suite
    data = data.drop(columns=["load", "RENEWABLE"])

    # 5. Passer en variations (diff)
    data = data.diff()

    # 6. Calculer les parts (delta techno / delta Load_RES)
    share_df = data.copy()
    cols = data.columns.tolist()
    for c in cols:
        share_df[c] = share_df[c] / share_df["load_RES"]

    share_df.to_csv(PROJECT_ROOT / "data/processed/variation_mix.csv", index=True)
    return(share_df)
