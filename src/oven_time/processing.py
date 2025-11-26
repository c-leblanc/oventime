import pandas as pd
from oven_time.config import PROJECT_ROOT

def clean_generation():
    generation = pd.read_csv(PROJECT_ROOT / "data/raw/generation.csv")
    generation = generation.drop(generation.index[0])#.drop(generation.columns[0], axis=1)
    generation = generation.rename(columns=
                                        {"Unnamed: 0":"time",
                                            "Biomass":"Biomass",
                                            "Energy storage":"Storage_PROD",
                                            "Energy storage.1": "Storage_CONS",
                                            "Fossil Gas":"Gas",
                                            "Fossil Hard coal":"Coal",
                                            "Fossil Oil":"Oil",
                                            "Hydro Pumped Storage":"PHS_PROD",
                                            "Hydro Pumped Storage.1":"PHS_CONS",
                                            "Hydro Run-of-river and poundage":"RoR",
                                            "Hydro Water Reservoir":"HydroDams",
                                            "Nuclear":"Nuclear",
                                            "Solar":"Solar",
                                            "Waste":"Waste",
                                            "Wind Offshore":"Wind_off",
                                            "Wind Onshore":"Wind_on"})

    gen_technos = generation.columns.drop("time")
    generation[gen_technos] = generation[gen_technos].apply(pd.to_numeric, errors="coerce")
    generation_detail = generation

    # Agreggation
    generation["RENEWABLE"] = generation["Wind_off"]+generation["Wind_on"]+generation["Solar"]+generation["RoR"]
    generation["NUCLEAR"] = generation["Nuclear"]  
    generation["STORAGE"] = generation["Storage_PROD"]-generation["Storage_CONS"]+generation["PHS_PROD"]+generation["HydroDams"]
    generation["GAS"] = generation["Gas"]
    generation["COAL"] = generation["Coal"]
    generation["OTHER_DISP"] = generation["Oil"]+generation["Biomass"]+generation["Waste"]

    generation_summary = generation[["time","RENEWABLE","NUCLEAR","STORAGE","GAS","COAL","OTHER_DISP"]]

    generation_detail.to_csv(PROJECT_ROOT / "data/processed/generation_detail.csv", index=False, float_format="%.0f")
    return(generation_summary)

def clean_load():
    load = pd.read_csv(PROJECT_ROOT / "data/raw/load.csv")
    #load = load.drop(load.columns[0], axis=1)
    load = load.rename(columns={"Unnamed: 0":"time","Actual Load":"load"})

    #load.to_csv(PROJECT_ROOT / "data/processed/load.csv", index=False, float_format="%.0f")
    return(load)

#def clean_trade():

def init_data():
    generation = clean_generation()
    load = clean_load()
    #clean_trade()
    #trade = pd.read_csv(PROJECT_ROOT / "data/processed/trade.csv")

    full_data = pd.merge(load,generation, on="time", how="inner")
    full_data.to_csv(PROJECT_ROOT / "data/processed/init_data.csv", index=False, float_format="%.0f")

    return(full_data)

def static_mix():
    data = init_data()
    
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
    data = init_data()

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
