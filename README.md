# spacetrack_population

Scripts to download data from [space-track.org](https://www.space-track.org) and analyse the population of objects in orbit.

The project has two parts:

1. **Download**: three Python scripts fetch three types of files from Space-Track.
2. **Analysis**: Jupyter notebooks read these files and produce tables and plots.

```
Space-Track ──► spacetrack_satcat.py        ──► satcat_YYYYMMDD.csv            ──┐
            ──► spacetrack_tle_snapshot.py  ──► tle_YYYYMMDD_YYYYMMDD.csv      ──┼──► analysis notebooks
            ──► spacetrack_tle_history.py   ──► <NORAD>.txt                    ──┘
```

## Setup

### Space-Track account

You need a (free) account on [space-track.org](https://www.space-track.org/auth/createAccount).

### Python environment

The scripts and notebooks run in a conda environment. Orekit is only needed for the `tle_history_elements*` and `tle_population_geo` notebooks.

```bash
conda create -n orekit-env -c conda-forge python=3.11 orekit pandas numpy matplotlib ipykernel
conda activate orekit-env
pip install requests spacetrack
```

The notebooks that use Orekit also need the Orekit data file `orekit-data.zip`, available from the [orekit-data repository](https://gitlab.orekit.org/orekit/orekit-data).

### Configuration file

Every script and notebook reads `config.ini`, located at the project root. To create it, copy the template and fill it in:

```bash
cp config.example.ini config.ini
```

| Section | Key | Purpose |
|---|---|---|
| `[spacetrack]` | `login`, `password` | Space-Track credentials |
| `[satcat]` | `output_dir` | folder of the `satcat_YYYYMMDD.csv` files |
| `[tle_snapshot]` | `output_dir` | folder of the `tle_YYYYMMDD_YYYYMMDD.csv` files |
| `[tle_history]` | `output_dir` | folder of the `<NORAD>.txt` files |
| `[tle_history]` | `format` | history format: `tle` (default), `3le`, `json`, `csv`, `xml` |
| `[orekit]` | `data_path` | Orekit data file or folder |

> ⚠️ `config.ini` holds your password: never commit it.

## Downloading the data

Each script accepts `--config other_file.ini` to use another configuration file.

Space-Track limits the request rate (about 30 per minute and 300 per hour). Avoid running the scripts in a loop.

### 1. The SATCAT catalogue: `spacetrack_satcat.py`

This script downloads the full catalogue of objects tracked by Space-Track: one object per row, whether still in orbit or already decayed.

```bash
python spacetrack_satcat.py                     # full catalogue
python spacetrack_satcat.py --current-only      # only objects still in orbit
python spacetrack_satcat.py --output-dir /tmp   # overrides output_dir from config.ini
```

- **Output**: `satcat_YYYYMMDD.csv` (today's date) in `[satcat] output_dir`.
- **Content**: NORAD number (`NORAD_CAT_ID`), international designator, name, type (`OBJECT_TYPE`: `PAYLOAD`, `DEBRIS`, `ROCKET BODY`, `UNKNOWN`), country, launch and decay dates (`DECAY`), period, inclination, apogee and perigee, radar size…

It is the reference for the **nature** of each object. The other files are joined to SATCAT on the NORAD number.

### 2. TLEs of all objects at a given date: `spacetrack_tle_snapshot.py`

This script downloads the TLEs of all catalogued objects published during the day: a snapshot of the population in orbit.

```bash
python spacetrack_tle_snapshot.py
```

- **Output**: `tle_YYYYMMDD_YYYYMMDD.csv` in `[tle_snapshot] output_dir`. The two dates bound the requested day.
- **Content**: one row per object, with columns `norad_id`, `name`, `line1`, `line2`. If an object has several TLEs during the day, only the first one is kept.
- **Period**: the script takes the current day, from 00:00 to 00:00 the next day. For another date, change `epoch_start` in `main()`.

An object whose TLE was not updated that day is missing from the file. Compare the number of objects in the snapshot with the number of objects in orbit in SATCAT.

### 3. TLE history of one object: `spacetrack_tle_history.py`

This script downloads every TLE of one or more objects, since they were put into orbit.

```bash
python spacetrack_tle_history.py 25544                # ISS
python spacetrack_tle_history.py 25544 20580 43700    # several objects
python spacetrack_tle_history.py 25544 --update       # only appends new TLEs
```

- **Output**: `<NORAD>.txt` in `[tle_history] output_dir`, in the format set in `config.ini`.
- **`--update`**: the script reads the epoch of the last TLE already in the file, downloads only the newer TLEs and appends them to the file. This option only works with the `tle` and `3le` formats.
- **Several objects**: the script pauses 3 s between objects to stay within Space-Track's limits.

## Analysing the data

Open the notebooks from the project root, next to `config.ini`, with the `orekit-env` kernel. At the top of each notebook, a parameter cell sets which files to read.

Some notebooks save their figures in `outputs/`. Create this folder if it does not exist.

| Notebook | Input data | What it shows |
|---|---|---|
| `satcat_analysis.ipynb` | SATCAT | breakdown by category and by country; recently launched objects (by launch, country, programme); new objects per month; spatial density vs altitude, computed from the SATCAT perigees and apogees |
| `tle_density.ipynb` | TLE snapshot + SATCAT | spatial density (objects/km³) of the objects currently in orbit vs altitude, in total and per category (satellites, debris, upper stages, unknown), in LEO and up to GEO |
| `tle_population.ipynb` | TLE snapshot + SATCAT | inclination vs semi-major axis for the whole population, in LEO and in GEO, then a focus on Chinese objects (PRC) |
| `tle_population_geo.ipynb` | TLE snapshot + SATCAT + Orekit | geostationary population: breakdown by country, longitude of the objects computed with Orekit, occupation of the GEO arc by country |
| `tle_history_elements.ipynb` | TLE history of one object + Orekit | orbital elements of one object over time: mean elements (TLE, SGP4/TEME) and osculating Keplerian elements (EME2000) |
| `tle_history_elements_geo.ipynb` | TLE history of one object + Orekit | same analysis for a GEO satellite, plus its geographic longitude and longitude drift rate |

### Parameters to adjust

- **Snapshot notebooks** (`tle_density`, `tle_population`, `tle_population_geo`): `TLE_SNAPSHOT` and `SATCAT` are the names of the files to read. For consistent results, pick a SATCAT downloaded close to the snapshot date.
- **History notebooks**: `NORAD_ID` selects the object. `START` and `END` optionally restrict the period (`None` for the full history). Download the object's history first with `spacetrack_tle_history.py`.
- **`satcat_analysis.ipynb`**: `SATCAT_FILE` selects the file. `ON_ORBIT_ONLY = True` keeps only the objects still in orbit.

## End-to-end example

```bash
conda activate orekit-env
python spacetrack_satcat.py             # → satcat_20261107.csv
python spacetrack_tle_snapshot.py       # → tle_20261107_20261108.csv
python spacetrack_tle_history.py 25544  # → 25544.txt
```

Then, in `tle_density.ipynb`, set `TLE_SNAPSHOT = "tle_20261107_20261108.csv"` and `SATCAT = "satcat_20261107.csv"`, and run all cells.
