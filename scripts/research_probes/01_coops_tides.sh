#!/usr/bin/env bash
# Verify NOAA CO-OPS metadata + datagetter for SF Bay / Half Moon Bay region.
# No auth required. Run: bash scripts/research_probes/01_coops_tides.sh
set -euo pipefail
UA="${UA:-TideWiseResearch/1.0}"
MD="https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
DG="https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

echo "== water level stations (filter client-side) =="
curl -sS -A "$UA" "$MD/stations.json?type=waterlevels&units=english" | python3 -c '
import json,sys
sts=json.load(sys.stdin)["stations"]
for s in sorted(sts, key=lambda x:x["id"]):
  lat,lon=float(s["lat"]),float(s["lng"])
  if 37.0<=lat<=38.5 and -123.5<=lon<=-121.8:
    print(s["id"], s["name"], lat, lon)
'

echo "== sample hi/lo predictions SF 9414290 =="
curl -sS -A "$UA" "$DG?date=today&station=9414290&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&format=json"
echo
echo "== sample latest water level SF =="
curl -sS -A "$UA" "$DG?date=latest&station=9414290&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json"
echo
echo "== current predictions Golden Gate entrance SFB1201 =="
curl -sS -A "$UA" "$DG?date=today&station=SFB1201&product=currents_predictions&time_zone=lst_ldt&units=english&format=json&interval=MAX_SLACK" | head -c 800
echo
