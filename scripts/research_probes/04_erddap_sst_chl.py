#!/usr/bin/env python3
"""Probe CoastWatch ERDDAP: MUR SST, VIIRS chl-a, C-HARM, MUR anomaly."""
import json, urllib.request, urllib.parse

BASE = "https://coastwatch.pfeg.noaa.gov/erddap/griddap"

def get(url, timeout=90):
    print("GET", url[:160], "...")
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)

# MUR SST analysed_sst — lon is -180..180
mur = get(
    f"{BASE}/jplMURSST41.json?"
    + urllib.parse.quote("analysed_sst[(last)][(37.5):1:(37.55)][(-122.55):1:(-122.5)]", safe="[](),:")
)
print("MUR columns", mur["table"]["columnNames"])
print("MUR sample rows", mur["table"]["rows"][:3])

# VIIRS North Pacific 8-day chl-a (altitude dim required)
chl = get(
    f"{BASE}/erdVHNchla8day.json?"
    + urllib.parse.quote("chla[(last)][(0.0)][(37.5):1:(37.55)][(-122.55):1:(-122.5)]", safe="[](),:")
)
print("CHL columns", chl["table"]["columnNames"])
print("CHL sample", chl["table"]["rows"][:3])

# C-HARM v3.1 uses longitude 0..360 (232.5..)
charm = get(
    f"{BASE}/wvcharmV3_0day.json?"
    + urllib.parse.quote(
        "pseudo_nitzschia[(last)][(37.4):1:(37.6)][(237.3):1:(237.5)]", safe="[](),:"
    )
)
print("C-HARM columns", charm["table"]["columnNames"])
print("C-HARM sample", charm["table"]["rows"][:3])

# MUR anomaly
anom = get(
    f"{BASE}/jplMURSST41anom1day.json?"
    + urllib.parse.quote("sstAnom[(last)][(37.5):1:(37.52)][(-122.55):1:(-122.52)]", safe="[](),:")
)
print("ANOM columns", anom["table"]["columnNames"])
print("ANOM sample", anom["table"]["rows"][:3])
