#!/usr/bin/env python3
"""Check whether C-HARM datasets are currently published on CoastWatch/OceanView ERDDAP."""
import json, urllib.request, urllib.error

BASES = [
    "https://coastwatch.pfeg.noaa.gov/erddap",
    "https://oceanview.pfeg.noaa.gov/erddap",
]
IDS = [
    "wvcharmV3_0day",
    "wvcharmV3_0day_LonPM180",
    "wvcharmV3_1day",
    "charmForecast0dayV2",
    "charmForecast0day",
]

def get(url, timeout=30):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]
    except Exception as e:
        return None, str(e).encode()

for base in BASES:
    for ds in IDS:
        code, body = get(f"{base}/info/{ds}/index.json")
        print(f"{code}\t{base}\t{ds}\t{body[:120]!r}")

# search
for base in BASES:
    code, body = get(f"{base}/search/index.json?page=1&itemsPerPage=20&searchFor=charm")
    print(f"SEARCH {code} {base} -> {body[:200]!r}")
