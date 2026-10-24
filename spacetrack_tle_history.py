#!/usr/bin/env python3
"""
Download the full TLE history of one or more objects from Space-Track,
identified by their NORAD number (NORAD_CAT_ID).

Space-Track keeps the complete history of orbital data (`gp_history`
class), which makes it possible to retrieve every TLE since the object
was put into orbit.

Requirements:
    pip install requests

Usage:
    python spacetrack_tle_history.py 25544
    python spacetrack_tle_history.py 25544 20580 43700
    python spacetrack_tle_history.py 25544 --update   # only fetch TLEs newer
                                                        # than the last one
                                                        # already in norad.txt
    python spacetrack_tle_history.py 25544 --config other_config.ini

Credentials, the output directory and the output format are read from
config.ini (see config.example.ini).
"""

import argparse
import configparser
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.ini"
DEFAULT_FORMAT = "tle"
FORMATS = ("tle", "3le", "json", "csv", "xml")

BASE_URL = "https://www.space-track.org"
LOGIN_URL = f"{BASE_URL}/ajaxauth/login"
QUERY_URL = f"{BASE_URL}/basicspacedata/query"

# Space-Track asks users to limit their request rate
# (max ~30 requests/minute, ~300/hour). We pause between objects.
THROTTLE_SECONDS = 3


def load_config(path: Path) -> configparser.ConfigParser:
    """Read the config file and check that the required keys are present."""
    if not path.is_file():
        raise SystemExit(
            f"Config file not found: {path}\n"
            "Copy config.example.ini to config.ini and fill it in."
        )
    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")
    required = {"spacetrack": ["login", "password"], "tle_history": ["output_dir"]}
    for section, keys in required.items():
        for key in keys:
            if not config.get(section, key, fallback="").strip():
                raise SystemExit(f"Missing key in {path}: [{section}] {key}")
    fmt = config.get("tle_history", "format", fallback=DEFAULT_FORMAT).strip()
    if fmt not in FORMATS:
        raise SystemExit(
            f"Invalid format in {path}: [tle_history] format = {fmt} "
            f"(expected one of: {', '.join(FORMATS)})"
        )
    return config


def login(session: requests.Session, user: str, password: str) -> None:
    """Open an authenticated session with Space-Track."""
    resp = session.post(
        LOGIN_URL,
        data={"identity": user, "password": password},
        timeout=60,
    )
    resp.raise_for_status()
    # On authentication failure, Space-Track returns an HTTP error code
    # (401) with a JSON body such as {"Login": "..."}.
    if "Failed" in resp.text:
        raise SystemExit(
            "Authentication failed. Check login / password in config.ini."
        )


def tle_epoch_to_datetime(epoch_field: str) -> datetime:
    """Convert a TLE epoch field ('YYDDD.DDDDDDDD') to a UTC datetime."""
    year_2d = int(epoch_field[:2])
    day_of_year_frac = float(epoch_field[2:])
    year = 2000 + year_2d if year_2d < 57 else 1900 + year_2d
    return datetime(year, 1, 1) + timedelta(days=day_of_year_frac - 1)


def last_epoch_in_file(path: str) -> Optional[datetime]:
    """Return the epoch of the last TLE in a norad.txt file (tle/3le), or None."""
    if not os.path.exists(path):
        return None
    lines = [l for l in open(path, encoding="utf-8") if l.strip()]
    if len(lines) < 2:
        return None
    # Line 1 of the last record is always the second-to-last line,
    # whether the format is "tle" (2 lines) or "3le" (3 lines, name first).
    last_line1 = lines[-2].strip()
    return tle_epoch_to_datetime(last_line1[18:32].strip())


def fetch_history(
    session: requests.Session,
    norad_id: int,
    fmt: str,
    epoch_after: Optional[datetime] = None,
) -> str:
    """Fetch the GP/TLE history of an object and return the raw content.

    If `epoch_after` is given, only fetch TLEs whose epoch is strictly
    later than this date (incremental update).
    """
    parts = [
        QUERY_URL,
        "class", "gp_history",
        "NORAD_CAT_ID", str(norad_id),
    ]
    if epoch_after is not None:
        parts += ["EPOCH", f">{epoch_after:%Y-%m-%dT%H:%M:%S.%f}"]
    parts += ["orderby", "EPOCH asc", "format", fmt]
    url = "/".join(parts)
    resp = session.get(url, timeout=120)
    resp.raise_for_status()
    return resp.text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download the TLE history of objects from Space-Track."
    )
    parser.add_argument("norad_ids", nargs="+", type=int, help="NORAD numbers")
    parser.add_argument(
        "--update", "-u",
        action="store_true",
        help=(
            "Only fetch TLEs newer than the last one already in the "
            "norad.txt file (and append them) instead of downloading the "
            "whole history again. Requires format 'tle' or '3le'."
        ),
    )
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG,
        help=f"Config file (default: {DEFAULT_CONFIG.name} next to the script)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    output_dir = Path(config["tle_history"]["output_dir"]).expanduser()
    fmt = config.get("tle_history", "format", fallback=DEFAULT_FORMAT).strip()

    if args.update and fmt not in ("tle", "3le"):
        print("--update is only supported with format = 'tle' or '3le'.")
        return 1

    os.makedirs(output_dir, exist_ok=True)

    with requests.Session() as session:
        login(session, config["spacetrack"]["login"], config["spacetrack"]["password"])
        print("Authentication successful.")

        for i, norad_id in enumerate(args.norad_ids):
            if i > 0:
                time.sleep(THROTTLE_SECONDS)

            out_path = os.path.join(output_dir, f"{norad_id}.txt")

            epoch_after = None
            if args.update:
                epoch_after = last_epoch_in_file(out_path)
                if epoch_after is not None:
                    print(
                        f"Updating NORAD {norad_id} "
                        f"since {epoch_after:%Y-%m-%d %H:%M:%S}…"
                    )
                else:
                    print(f"No local history for {norad_id}, full download…")
            else:
                print(f"Downloading history for NORAD {norad_id}…")

            try:
                content = fetch_history(session, norad_id, fmt, epoch_after)
            except requests.HTTPError as exc:
                print(f"  HTTP error for {norad_id}: {exc}", file=sys.stderr)
                continue

            if not content.strip() or content.strip() == "[]":
                print(f"  {'Already up to date' if epoch_after else 'No data returned'} for {norad_id}.")
                continue

            append = args.update and epoch_after is not None
            if append:
                with open(out_path, "rb") as fh:
                    fh.seek(-1, os.SEEK_END)
                    needs_newline = fh.read(1) != b"\n"
                with open(out_path, "a", encoding="utf-8") as fh:
                    if needs_newline:
                        fh.write("\n")
                    fh.write(content)
            else:
                with open(out_path, "w", encoding="utf-8") as fh:
                    fh.write(content)

            # Approximate TLE count (line pairs in tle format).
            if fmt in ("tle", "3le"):
                n_lines = len([l for l in content.splitlines() if l.strip()])
                divisor = 2 if fmt == "tle" else 3
                verb = "appended" if append else "written"
                print(f"  {n_lines // divisor} TLE(s) {verb} -> {out_path}")
            else:
                print(f"  Written -> {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
