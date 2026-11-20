#!/usr/bin/env bash
# TideWise research probe: NOAA CO-OPS, NDBC, NWS, USNO. Read-only GETs, no keys.
# Usage: bash scripts/research_probes/probe_noaa.sh
set -u
UA='User-Agent: (tidewise-grokathon, github.com/AarenSunny/tidewise-grokathon)'
CO="https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
TODAY=$(date -u +%Y%m%d)
echo "### CO-OPS hi/lo predictions (MLLW, ft, local time)"
for s in 9414290 9414131 9414750 9414863 9414523 9415020; do
  echo "-- $s"; curl -s -m 30 "$CO?station=$s&product=predictions&datum=MLLW&interval=hilo&units=english&time_zone=lst_ldt&format=json&application=tidewise&begin_date=$TODAY&range=24" | head -c 300; echo
done
echo "### CO-OPS observed water level / water temp / wind (latest)"
for s in 9414290 9414750 9414863 9415020 9414131; do
  for p in water_level water_temperature wind; do
    echo "-- $s $p: $(curl -s -m 30 "$CO?station=$s&product=$p&datum=MLLW&units=english&time_zone=gmt&format=json&application=tidewise&date=latest" | tr -d '\n' | head -c 220)"
  done
done
echo "### CO-OPS current predictions (max/slack)"
for s in SFB1201 SFB1203 SFB1212 SFB1305; do
  echo "-- $s"; curl -s -m 30 "$CO?station=$s&product=currents_predictions&interval=MAX_SLACK&units=english&time_zone=lst_ldt&format=json&application=tidewise&begin_date=$TODAY&range=24" | head -c 300; echo
done
echo "### NDBC realtime2 (standard met + spectral summary)"
for b in 46026 46012 46237 46214 46013 46042 46239 FTPC1 AAMC1 RCMC1 PXOC1 TIBC1; do
  echo "-- $b HTTP $(curl -s -m 30 -o /tmp/ndbc_$b.txt -w '%{http_code}' https://www.ndbc.noaa.gov/data/realtime2/$b.txt)"; head -3 /tmp/ndbc_$b.txt
done
curl -s -m 30 https://www.ndbc.noaa.gov/data/realtime2/46237.spec | head -3
echo "### NWS points / hourly / alerts / SRF / CWF"
curl -s -m 30 -H "$UA" "https://api.weather.gov/points/37.4636,-122.4286" | python3 -c "import json,sys;d=json.load(sys.stdin)['properties'];print(d['gridId'],d['gridX'],d['gridY'],d['forecastHourly'],d['forecastZone'])"
curl -s -m 30 -H "$UA" "https://api.weather.gov/gridpoints/MTR/82,92/forecast/hourly" | python3 -c "import json,sys;d=json.load(sys.stdin)['properties'];print(d['updateTime']);print(json.dumps(d['periods'][0])[:400])"
curl -s -m 30 -H "$UA" "https://api.weather.gov/alerts/active?zone=PZZ545,PZZ530,PZZ531,CAZ509,CAZ006" | python3 -c "import json,sys;d=json.load(sys.stdin);[print(f['properties']['event'],'|',f['properties']['expires'],'|',f['properties']['geocode']['UGC']) for f in d['features']]"
curl -s -m 30 -H "$UA" "https://api.weather.gov/alerts/active?point=37.4636,-122.4286" | python3 -c "import json,sys;d=json.load(sys.stdin);[print('point:',f['properties']['event']) for f in d['features']]"
for t in SRF CWF; do
  ID=$(curl -s -m 30 -H "$UA" "https://api.weather.gov/products/types/$t/locations/MTR" | python3 -c "import json,sys;print(json.load(sys.stdin)['@graph'][0]['id'])")
  curl -s -m 30 -H "$UA" "https://api.weather.gov/products/$ID" | python3 -c "import json,sys;d=json.load(sys.stdin);t=d['productText'];print(d['issuanceTime']);i=t.find('CAZ509') if 'SRF' in t[:200] else t.find('PZZ545');print(t[i:i+700]);print('Rip Current mentions:',t.count('Rip Current'))"
done
echo "### USNO moon phases"
curl -s -m 30 "https://aa.usno.navy.mil/api/moon/phases/date?date=$(date +%Y-%m-%d)&nump=4" | head -c 500; echo
