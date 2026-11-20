#!/usr/bin/env bash
# TideWise research probe: beach bacteria, shellfish advisories, fire/smoke, UV/solar. No keys used.
set -u
echo "### SF beach water quality (DataSF Socrata, dataset v3fv-x3ux)"
curl -sL -m 40 "https://data.sf.gov/resource/v3fv-x3ux.json?\$where=analyte%20IS%20NOT%20NULL&\$limit=4&\$order=sample_date%20DESC" | head -c 900; echo
echo "### CDPH shellfish advisories page (HTML, no API)"
curl -sL -m 40 -o /tmp/cdph.html -w 'HTTP %{http_code}\n' "https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx"
python3 -c "import re,html;t=html.unescape(re.sub(r'<[^>]+>',' ',open('/tmp/cdph.html',errors='ignore').read()));t=re.sub(r'\s+',' ',t);i=t.find('CDPH Updates');print(t[i:i+500] if i>=0 else t[:300])"
echo "### CDFW health advisories page (HTML, no API)"
curl -sL -m 40 -o /tmp/cdfw.html -w 'HTTP %{http_code}\n' "https://wildlife.ca.gov/Fishing/Ocean/Health-Advisories"
echo "### NASA EONET open events in Bay Area bbox"
curl -s -m 30 "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&bbox=-123.2,37.2,-121.8,38.2&limit=20" | python3 -c "import json,sys;d=json.load(sys.stdin);[print(e['id'],e['title'],e['categories'][0]['id'],e['geometry'][-1]['date'],e['geometry'][-1]['coordinates']) for e in d['events']]"
echo "### NASA FIRMS (requires MAP_KEY; this shows the no-key error)"
curl -s -m 30 "https://firms.modaps.eosdis.nasa.gov/api/area/csv/MAP_KEY/VIIRS_SNPP_NRT/-123.2,37.2,-121.8,38.2/1" | head -c 200; echo
# with key: FIRMS_MAP_KEY=... ; curl ".../api/area/csv/$FIRMS_MAP_KEY/VIIRS_SNPP_NRT/-123.2,37.2,-121.8,38.2/1"
echo "### NASA POWER daily point (UV index, shortwave, T2M) - check latency"
S=$(date -d '-20 days' +%Y%m%d); E=$(date +%Y%m%d)
curl -s -m 40 "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_UV_INDEX,ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude=-122.5&latitude=37.7&start=$S&end=$E&format=JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin);print(d['header'])
for k,v in d['properties']['parameter'].items():
  g=[(a,b) for a,b in v.items() if b!=-999]; print(k,'last non-fill:',g[-1] if g else None)"
echo "### EPA Envirofacts UV index forecast (no key) - Half Moon Bay ZIP 94019"
curl -s -m 30 "https://data.epa.gov/efservice/getEnvirofactsUVDAILY/ZIP/94019/JSON"; echo
curl -s -m 30 "https://data.epa.gov/efservice/getEnvirofactsUVHOURLY/ZIP/94019/JSON" | head -c 400; echo
