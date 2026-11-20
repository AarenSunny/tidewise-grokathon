#!/usr/bin/env bash
# Live beach-bacteria sources for SF and San Mateo, plus stale BeachWatch check. No secrets.
set -u
echo "== DataSF v3fv-x3ux freshness =="
curl -sSL -G 'https://data.sf.gov/resource/v3fv-x3ux.json' \
  --data-urlencode '$select=max(sample_date) as maxd, max(data_as_of) as asof, count(*) as n' --max-time 40; echo
echo "== DataSF latest per station =="
curl -sSL -G 'https://data.sf.gov/resource/v3fv-x3ux.json' \
  --data-urlencode '$select=source,max(sample_date) as last' --data-urlencode '$group=source' \
  --data-urlencode '$order=last DESC' --data-urlencode '$limit=8' --max-time 40; echo
echo "== DataSF recent Enterococcus rows =="
curl -sSL -G 'https://data.sf.gov/resource/v3fv-x3ux.json' \
  --data-urlencode "\$where=analyte='ENTERO' AND sample_date>'2026-11-10'" \
  --data-urlencode '$order=sample_date DESC' --data-urlencode '$limit=5' --max-time 40; echo
echo "== San Mateo latest posting (WP-JSON) =="
curl -sSL -G 'https://smchealth.org/wp-json/wp/v2/posts' --data-urlencode 'search=Beach and Creek Updates' \
  --data-urlencode 'per_page=3' --data-urlencode '_fields=id,date,slug,link,title' --max-time 30; echo
echo "== San Mateo RSS =="
curl -sSL 'https://smchealth.org/feed/' --max-time 30 | grep -o '<title>[^<]*Beach[^<]*</title>\|<pubDate>[^<]*</pubDate>' | head -4
echo "== BeachWatch (SWRCB) max sample date per county (stale check) =="
for c in "San Mateo" "San Francisco" "Marin"; do
  curl -sS -G 'https://data.ca.gov/api/3/action/datastore_search_sql' \
   --data-urlencode "sql=SELECT MAX(\"SampleDate\") AS maxd FROM \"7bd961cf-abe4-433b-8033-378161237ff3\" WHERE \"County\"='$c'" --max-time 60 \
   | python3 -c "import sys,json;print('$c',json.load(sys.stdin)['result']['records'])"
done
echo "== station join example =="
curl -sS -G 'https://data.ca.gov/api/3/action/datastore_search' --data-urlencode 'resource_id=98e628ff-d012-4982-ad32-b9f9ad8ab524' \
  --data-urlencode 'q=OCEAN#22' --data-urlencode 'limit=1' --max-time 40 | head -c 600; echo
