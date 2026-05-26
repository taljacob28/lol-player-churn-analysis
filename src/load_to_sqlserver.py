"""
Load the cleaned data into SQL Server.

Reads player_match.csv and player_features.csv and writes them to two base tables,
fact_player_match (one row per player per match) and dim_player (one row per
player). The star schema dimensions and the analysis queries then run from the
.sql scripts in the sql/ folder.

Edit the CONNECTION block for your machine, then run from the project root:
    python src/load_to_sqlserver.py
"""

import urllib.parse

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

import config

# --- CONNECTION (edit for your machine) ---
SERVER = r"TAL-JACOB\TALJACOB"      # your SQL Server instance
DATABASE = "LoLChurnAnalysis"
DRIVER = "ODBC Driver 17 for SQL Server"   # use 18 if that is what you have
# Windows auth. For SQL auth, add UID and PWD to the string below.
# ------------------------------------------


def odbc(database):
    s = (f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={database};"
         f"Trusted_Connection=yes;TrustServerCertificate=yes;")
    return URL.create("mssql+pyodbc", query={"odbc_connect": s})


def ensure_database():
    master = create_engine(odbc("master"), isolation_level="AUTOCOMMIT")
    with master.connect() as conn:
        conn.execute(text(
            f"IF DB_ID('{DATABASE}') IS NULL CREATE DATABASE [{DATABASE}];"))
    print(f"Database {DATABASE} ready.")


def main():
    ensure_database()
    engine = create_engine(odbc(DATABASE), fast_executemany=True)

    fact = pd.read_csv(config.DATA / "player_match.csv")
    dim = pd.read_csv(config.DATA / "player_features.csv")

    fact.to_sql("fact_player_match", engine, if_exists="replace",
                index=False, chunksize=2000)
    print(f"fact_player_match loaded: {len(fact):,} rows")

    dim.to_sql("dim_player", engine, if_exists="replace",
               index=False, chunksize=1000)
    print(f"dim_player loaded: {len(dim):,} rows")

    print("Done. Now run sql/01_star_schema.sql then sql/02_analysis_queries.sql in SSMS.")


if __name__ == "__main__":
    main()
