#!/usr/bin/env bash
# FIRMS (key-free CSV + optional MAP_KEY area API), EONET, NASA POWER, EPA UV, BeachWatch CKAN
set -euo pipefail

echo "== EONET wildfires (bbox roughly SF Bay) =="
curl -sS --max-time 30 \
  "https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open&limit=10&bbox=-123.5,37.0,-121.5,38.5" \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print("events",len(d.get("events",[])));
print([(e["id"],e["title"]) for e in d.get("events",[])[:5]])'

echo "== FIRMS MODIS USA 24h CSV (no key) =="
curl -sS --max-time 60 -o /tmp/firms_modis.csv \
  "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_USA_contiguous_and_Hawaii_24h.csv"
head -2 /tmp/firms_modis.csv
echo "lines=$(wc -l </tmp/firms_modis.csv)"

echo "== FIRMS NOAA-20 VIIRS USA 24h CSV (no key) =="
curl -sS --max-time 60 -o /tmp/firms_n20.csv \
  "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv"
head -2 /tmp/firms_n20.csv

if [[ -n "${FIRMS_MAP_KEY:-}" ]]; then
  echo "== FIRMS area API with MAP_KEY =="
  curl -sS --max-time 60 \
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/${FIRMS_MAP_KEY}/VIIRS_NOAA20_NRT/-123.5,37.0,-121.5,38.5/1" | head -5
else
  echo "Skip FIRMS area API (set FIRMS_MAP_KEY to test). Register at https://firms.modaps.eosdis.nasa.gov/api/map_key"
fi

echo "== NASA POWER daily (note multi-day lag; fill -999) =="
curl -sS --max-time 60 \
  "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude=-122.47&latitude=37.81&start=20261101&end=20261118&format=JSON" \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print("fill",d["header"]["fill_value"]);print(list(d["properties"]["parameter"].keys()));
sw=d["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]; print("SW last nonfill", [(k,v) for k,v in sw.items() if v!=-999][-3:])'

echo "== EPA UV hourly by ZIP =="
curl -sS --max-time 30 "https://data.epa.gov/efservice/getEnvirofactsUVHOURLY/ZIP/94121/JSON" \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d[:3] if isinstance(d,list) else d)'

echo "== BeachWatch CKAN datastore (advisories sample) =="
curl -sS --max-time 45 \
  "https://data.ca.gov/api/3/action/datastore_search?resource_id=d5cd6a23-829c-426d-a63e-689a55a3db9c&limit=2" \
  | python3 -c 'import json,sys;r=json.load(sys.stdin)["result"];print("total",r["total"]);print(r["records"][0] if r["records"] else None)'
