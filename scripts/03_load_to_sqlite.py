import sqlite3
import pandas as pd
from pathlib import Path

IN_PATH = Path("data/processed/02_segmented.csv")
DB_PATH = Path("data/processed/bank_churn.db")
TABLE_NAME = "customers"

def load_to_sqlite(csv_path: Path, db_path: Path, table_name: str) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"Segmented CSV not found at {csv_path}. Run scripts/02_clean_segment.py first.")

    df = pd.read_csv(csv_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)

    # if_exists="replace" means re-running this script always rebuilds the
    # table fresh from the latest CSV, rather than appending duplicate rows
    # on every run.
    df.to_sql(table_name, conn, if_exists="replace", index=False)

    conn.close()
    print(f"Loaded {len(df)} rows into table '{table_name}' at {db_path}")

def verify_load(db_path: Path, table_name: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cur.fetchone()[0]

    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cur.fetchall()]

    print(f"Verification: {row_count} rows, {len(columns)} columns")
    print(f"Columns: {columns}")

    conn.close()

def main():
    load_to_sqlite(IN_PATH, DB_PATH, TABLE_NAME)
    verify_load(DB_PATH, TABLE_NAME)


if __name__ == "__main__":
    main()

