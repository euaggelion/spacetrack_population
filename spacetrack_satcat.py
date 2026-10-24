#!/usr/bin/env python3
"""
Télécharge le catalogue SATCAT complet depuis Space-Track.

Prérequis :
    pip install requests

Usage :
    python spacetrack_satcat.py
    python spacetrack_satcat.py --current-only   # uniquement les objets encore en orbite (CURRENT=Y)
    python spacetrack_satcat.py --config autre_config.ini

Les identifiants et le dossier de sortie sont lus dans config.ini
(voir config.example.ini).
"""

from __future__ import annotations

import argparse
import configparser
from datetime import datetime
from pathlib import Path

import requests

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.ini"

BASE_URL  = "https://www.space-track.org"
LOGIN_URL = f"{BASE_URL}/ajaxauth/login"
QUERY_URL = f"{BASE_URL}/basicspacedata/query"


def load_config(path: Path) -> configparser.ConfigParser:
    """Lit le fichier de configuration et vérifie les clés nécessaires."""
    if not path.is_file():
        raise SystemExit(
            f"Fichier de configuration introuvable : {path}\n"
            "Copie config.example.ini en config.ini et renseigne-le."
        )
    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")
    required = {"spacetrack": ["login", "password"], "satcat": ["output_dir"]}
    for section, keys in required.items():
        for key in keys:
            if not config.get(section, key, fallback="").strip():
                raise SystemExit(f"Clé manquante dans {path} : [{section}] {key}")
    return config


def login(session: requests.Session, user: str, password: str) -> None:
    """Ouvre une session authentifiée auprès de Space-Track."""
    resp = session.post(
        LOGIN_URL,
        data={"identity": user, "password": password},
        timeout=60,
    )
    resp.raise_for_status()
    if "Failed" in resp.text:
        raise SystemExit(
            "Échec de l'authentification. Vérifie LOGIN / PASSWORD."
        )


def fetch_satcat(session: requests.Session, current_only: bool) -> str:
    """Récupère le catalogue SATCAT et renvoie le contenu CSV brut."""
    parts = [QUERY_URL, "class", "satcat"]
    if current_only:
        parts += ["CURRENT", "Y"]
    parts += ["orderby", "NORAD_CAT_ID asc", "format", "csv"]
    url = "/".join(parts)
    resp = session.get(url, timeout=120)
    resp.raise_for_status()
    return resp.text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Télécharge le catalogue SATCAT depuis Space-Track."
    )
    parser.add_argument(
        "--current-only", action="store_true",
        help="Ne récupère que les objets actuellement en orbite (CURRENT=Y)",
    )
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG,
        help=f"Fichier de configuration (défaut : {DEFAULT_CONFIG.name} à côté du script)",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        help="Dossier de sortie, remplace celui du fichier de configuration",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    output_dir = args.output_dir or Path(config["satcat"]["output_dir"]).expanduser()

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"satcat_{datetime.today():%Y%m%d}.csv"

    with requests.Session() as session:
        login(session, config["spacetrack"]["login"], config["spacetrack"]["password"])
        print("Authentification réussie.")
        print("Téléchargement du catalogue SATCAT…")
        content = fetch_satcat(session, args.current_only)

    if not content.strip():
        print("Aucune donnée retournée par Space-Track.")
        return 1

    out_path.write_text(content, encoding="utf-8")
    n_objects = max(0, len(content.strip().splitlines()) - 1)  # -1 pour l'en-tête
    print(f"{n_objects:,} objets écrits -> {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
