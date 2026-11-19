#!/usr/bin/env bash
# CDPH shellfish advisory pages + ArcGIS feature services.
# Note: cdph.ca.gov may fail strict TLS on some clients; -k used only for probe.
set -euo pipefail

for url in \
  "https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx" \
  "https://www.cdph.ca.gov/Programs/CEH/DRSEM/Pages/EMB/Shellfish/Annual-Mussel-Quarantine.aspx" \
  "https://www.cdph.ca.gov/Programs/CEH/DRSEM/Pages/EMB/Shellfish/Marine-Biotoxin-Monitoring-Program.aspx"
do
  code=$(curl -sS -k -o /tmp/cdph.html -w "%{http_code}" --max-time 45 "$url" || true)
  echo "$code $url"
done

echo "== ArcGIS special advisory polygons =="
curl -sS -k --max-time 30 \
  "https://services2.arcgis.com/wi1yEacfYjH5viqb/arcgis/rest/services/All_Bivalve_Shellfish_Health_Advisory_Special_Advisory/FeatureServer/3/query?where=1%3D1&outFields=TITLE,DESCRIPTION,DATE,VISIBLE&returnGeometry=false&f=json" \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print([(f["attributes"]["TITLE"],f["attributes"].get("VISIBLE")) for f in d.get("features",[])])'

echo "== ArcGIS advisory county points =="
curl -sS -k --max-time 30 \
  "https://services2.arcgis.com/wi1yEacfYjH5viqb/arcgis/rest/services/Health_Advisory_Symbols_(Red)/FeatureServer/0/query?where=1%3D1&outFields=County_Name,Latitude,Longitude&returnGeometry=false&f=json" \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print(len(d.get("features",[])),"counties");print([f["attributes"]["County_Name"] for f in d.get("features",[])[:8]])'
