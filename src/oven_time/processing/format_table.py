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

    generation["Storage"] = generation["Storage_PROD"] - generation["Storage_CONS"]
    generation = generation.drop(columns=["Storage_PROD", "Storage_CONS"])
    generation["PHS"] = generation["PHS_PROD"] - generation["PHS_CONS"]
    generation = generation.drop(columns=["PHS_PROD", "PHS_CONS"])

    generation.to_csv(PROJECT_ROOT / "data/processed/generation.csv", index=False)

def clean_load():
    load = pd.read_csv(PROJECT_ROOT / "data/raw/load.csv")
    #load = load.drop(load.columns[0], axis=1)
    load = load.rename(columns={"Unnamed: 0":"time","Actual Load":"Load"})

    load.to_csv(PROJECT_ROOT / "data/processed/load.csv", index=False)

#def clean_trade():

def merge_data():
    clean_generation()
    generation = pd.read_csv(PROJECT_ROOT / "data/processed/generation.csv")
    clean_load()
    load = pd.read_csv(PROJECT_ROOT / "data/processed/load.csv")
    #clean_trade()
    #trade = pd.read_csv(PROJECT_ROOT / "data/processed/trade.csv")

    full_data = pd.merge(generation, load, on="time", how="inner")
    full_data.to_csv(PROJECT_ROOT / "data/processed/full_data.csv", index=False)