# reformat_nsrdb.py
# Robust NSRDB reformatter: finds the true header row, builds a single 'datetime' column,
# and saves per-file outputs into ~/Desktop/Solar Data/formatted

from pathlib import Path
import pandas as pd

# === 1) Point to your Solar Data root ===
BASE_FOLDER = Path("/Users/akshathkandadai/Desktop/Solar Data")  # <- exact path
OUTPUT_FOLDER = BASE_FOLDER / "formatted"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

print("BASE FOLDER IS:", BASE_FOLDER)
print("CONTENTS:", list(BASE_FOLDER.iterdir()))

# --- small helpers ------------------------------------------------------------
EXPECTED_SET_YMDHM = {"Year", "Month", "Day"}  # 'Hour'/'Minute' may be absent in some variants

def find_header_row(csv_path: Path, max_scan: int = 80):
    """
    Scan the file line-by-line to locate the real header row.
    Return (header_index, header_cols) or (None, None) if not found.
    """
    with csv_path.open("r", encoding="utf-8", errors="ignore") as f:
        for i, raw in enumerate(f):
            if i > max_scan:
                break
            cols = [c.strip().strip('"') for c in raw.strip().split(",")]

            colset = set(cols)

            # Case A: classic NSRDB after metadata: Year, Month, Day (and often Hour, Minute)
            if EXPECTED_SET_YMDHM.issubset(colset):
                return i, cols

            # Case B: two-column time (Date + Time) variants
            if ("Date" in colset and "Time" in colset) or ("Date/Time" in colset):
                return i, cols

            # Case C: single time column variants
            if any(c in colset for c in ["Local Time", "Timestamp"]):
                return i, cols

    return None, None

def build_datetime(df: pd.DataFrame) -> pd.Series:
    """Create a 'datetime' Series from any of the supported time header patterns."""
    cols = [c.strip() for c in df.columns]
    df.columns = cols  # normalize whitespace

    # Most common NSRDB format
    if {"Year", "Month", "Day"}.issubset(df.columns):
        hour = df["Hour"] if "Hour" in df.columns else 0
        minute = df["Minute"] if "Minute" in df.columns else 0
        return pd.to_datetime(
            dict(year=df["Year"], month=df["Month"], day=df["Day"], hour=hour, minute=minute),
            errors="coerce"
        )

    # Date + Time split
    if "Date" in df.columns and "Time" in df.columns:
        return pd.to_datetime(df["Date"].astype(str) + " " + df["Time"].astype(str), errors="coerce")

    # One-column timestamp variants
    for key in ["Local Time", "Date/Time", "Timestamp"]:
        if key in df.columns:
            return pd.to_datetime(df[key], errors="coerce")

    # If we reach here, we couldn't make a datetime
    return pd.Series(pd.NaT, index=df.index)

# --- 2) Walk all bus folders and process CSVs ---------------------------------
for folder in BASE_FOLDER.iterdir():
    if not folder.is_dir():
        continue
    if folder.name in {"formatted", ".DS_Store"}:
        continue

    print(f"📁 Entering folder: {folder.name}")
    for csv_file in folder.glob("*.csv"):
        print(f"  → Processing {csv_file.name}")
        try:
            header_idx, header_cols = find_header_row(csv_file)
            if header_idx is None:
                print(f"    ⚠️  Could not locate header row in {csv_file.name}; skipping.")
                continue

            # Read with the detected header line
            df = pd.read_csv(
                csv_file,
                skiprows=header_idx,   # skip metadata rows ABOVE the real header
                header=0,              # first non-skipped row is the header
                low_memory=False
            )

            # Build datetime
            dt = build_datetime(df)
            if dt.isna().all():
                print(f"    ⚠️  No recognizable date/time columns in {csv_file.name}; skipping.")
                continue

            df.insert(0, "datetime", dt)

            # Optionally drop the decomposed date fields (uncomment if you want them gone)
            for c in ["Year", "Month", "Day", "Hour", "Minute", "Date", "Time", "Date/Time", "Local Time", "Timestamp"]:
                if c in df.columns and c != "datetime":
                    df.drop(columns=c, inplace=True, errors="ignore")

            # Remove obvious metadata unit columns if present
            unit_cols = [c for c in df.columns if c.endswith(" Units")]
            if unit_cols:
                df.drop(columns=unit_cols, inplace=True, errors="ignore")

            # Reorder columns: datetime first
            cols = ["datetime"] + [c for c in df.columns if c != "datetime"]
            df = df[cols]

            # Write output
            out_name = f"{folder.name}_{csv_file.name}"
            out_path = OUTPUT_FOLDER / out_name
            df.to_csv(out_path, index=False)
            print(f"    ✅ Wrote {out_path.name}")

        except Exception as e:
            print(f"    ❌ Failed on {csv_file.name}: {e}")

print("\n✅ Finished! Check the 'formatted' folder inside Solar Data.")

from pathlib import Path
import shutil

BASE_FOLDER = Path("/Users/akshathkandadai/Desktop/Solar Data")
FORMATTED = BASE_FOLDER / "formatted"

print("Organizing formatted files...")

for csv_file in FORMATTED.glob("*.csv"):
    name = csv_file.stem        # ex: "101_287105_33.41_-113.82_1998"
    node = name.split("_")[0]   # everything before first "_"

    node_folder = FORMATTED / node
    node_folder.mkdir(exist_ok=True)

    destination = node_folder / csv_file.name
    shutil.move(str(csv_file), str(destination))

    print(f"✔︎ Moved {csv_file.name} → {node_folder.name}/")

print("\n✅ Done! Check your 'formatted' folder — each node now has its own subfolder.")

