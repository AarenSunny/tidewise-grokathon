#!/usr/bin/env bash
# NWS api.weather.gov — requires a descriptive User-Agent.
set -euo pipefail
UA="${UA:-TideWiseResearch/1.0 (research; contact via github.com/AarenSunny/tidewise-grokathon)}"
H=(-H "User-Agent: $UA" -H "Accept: application/geo+json")

echo "== points (SF) =="
curl -sS "${H[@]}" "https://api.weather.gov/points/37.8063,-122.4659" | python3 -c 'import json,sys;p=json.load(sys.stdin)["properties"];print(p["gridId"],p["gridX"],p["gridY"],p["forecast"],p["forecastZone"])'

echo "== active CA alerts (marine/beach subset) =="
curl -sS "${H[@]}" "https://api.weather.gov/alerts/active?area=CA" | python3 -c '
import json,sys
from collections import Counter
feats=json.load(sys.stdin).get("features",[])
print("total",len(feats))
print(Counter(f["properties"]["event"] for f in feats).most_common(12))
'

echo "== marine zone PZZ545 forecast =="
curl -sS "${H[@]}" "https://api.weather.gov/zones/forecast/PZZ545/forecast" | python3 -c '
import json,sys
d=json.load(sys.stdin)
print(d["properties"]["periods"][0]["name"], d["properties"]["periods"][0]["detailedForecast"][:200])
'

echo "== latest SRF from MTR =="
curl -sS "${H[@]}" "https://api.weather.gov/products/types/SRF/locations/MTR" | python3 -c '
import json,sys
g=json.load(sys.stdin).get("@graph",[])
print("count",len(g),"latest",g[0]["id"],g[0]["issuanceTime"] if g else None)
if g:
  import urllib.request
  req=urllib.request.Request("https://api.weather.gov/products/"+g[0]["id"], headers={"User-Agent":"TideWiseResearch/1.0"})
  body=urllib.request.urlopen(req, timeout=30).read().decode()
  prod=json.loads(body)
  print((prod.get("productText") or "")[:500])
'
