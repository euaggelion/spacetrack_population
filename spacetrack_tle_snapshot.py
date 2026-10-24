"""Download a 3LE snapshot from Space-Track.org for a given epoch range.

Usage:
    python spacetrack_tle_snapshot.py
    python spacetrack_tle_snapshot.py --config other_config.ini

Credentials and the output directory are read from config.ini
(see config.example.ini).
"""
 
from __future__ import annotations
 
import argparse
import configparser
from datetime import datetime, timedelta
from pathlib import Path
 
import pandas as pd
import spacetrack.operators as op
from spacetrack import SpaceTrackClient
 
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.ini"


def load_config(path: Path) -> configparser.ConfigParser:
    """Read the config file and check that the required keys are present."""
    if not path.is_file():
        raise SystemExit(
            f"Config file not found: {path}\n"
            "Copy config.example.ini to config.ini and fill it in."
        )
    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")
    required = {"spacetrack": ["login", "password"], "tle_snapshot": ["output_dir"]}
    for section, keys in required.items():
        for key in keys:
            if not config.get(section, key, fallback="").strip():
                raise SystemExit(f"Missing key in {path}: [{section}] {key}")
    return config

 
# Alpha-5 encoding: letters A-Z (skipping I and O) map to 10-33
# e.g. "T1234" → 27 * 10_000 + 1234 = 271_234
_ALPHA5 = {c: i + 10 for i, c in enumerate("ABCDEFGHJKLMNPQRSTUVWXYZ")}
 
def alpha5_to_int(sat_id: str) -> int:
    """Decode a 5-char TLE satellite ID (numeric or alpha-5) to an integer."""
    sat_id = sat_id.strip()
    if sat_id[0].isdigit():
        return int(sat_id)
    return _ALPHA5[sat_id[0]] * 10_000 + int(sat_id[1:])
 
def download_3le(login: str, password: str, start: datetime, end: datetime) -> list[str]:
    """Fetch 3LE lines from Space-Track for the given creation-date range."""
    st     = SpaceTrackClient(login, password)
    drange = op.inclusive_range(start, end)
 
    print(f"Downloading TLEs [{start.date()} → {end.date()}] …")
    lines = list(st.gp_history(
        iter_lines=True,
        creation_date=drange,
        orderby="NORAD_CAT_ID",
        format="3le",
    ))
    print(f"  {len(lines)} lines — {len(lines) // 3:,} objects")
    return lines
 
def parse_3le(lines: list[str]) -> pd.DataFrame:
    """Parse 3LE triplets into a DataFrame (name, line1, line2)."""
    records = []
    for i in range(0, len(lines) - 2, 3):
        raw_name = lines[i].strip()
        line1    = lines[i + 1].strip()
        line2    = lines[i + 2].strip()
 
        # Sanity check: line1/line2 must start with '1'/'2'
        if not (line1.startswith("1") and line2.startswith("2")):
            print(f"  [skip] malformed triplet at index {i}")
            continue
 
        # Line 0 is either "0 NAME" (3LE) or bare "NAME"
        name     = raw_name[2:] if raw_name.startswith("0 ") else raw_name
        norad_id = alpha5_to_int(line1[2:7])
        records.append({"norad_id": norad_id, "name": name, "line1": line1, "line2": line2})

    df = pd.DataFrame(records)
    # Keep only the first TLE per satellite (data is already sorted by creation_date asc)
    df = df.drop_duplicates(subset="norad_id", keep="first")
    return df
 
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG,
        help=f"Config file (default: {DEFAULT_CONFIG.name} next to the script)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    output_dir = Path(config["tle_snapshot"]["output_dir"]).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    epoch_start = datetime.combine(datetime.today().date(), datetime.min.time())
    epoch_end   = epoch_start + timedelta(days=1)
    output = output_dir / f"tle_{epoch_start:%Y%m%d}_{epoch_end:%Y%m%d}.csv"

    lines = download_3le(
        config["spacetrack"]["login"], config["spacetrack"]["password"],
        epoch_start, epoch_end,
    )
    df    = parse_3le(lines)
    print(df.head())
    df.to_csv(output, index=False)
    print(f"Saved → {output}  ({len(df):,} objects)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
