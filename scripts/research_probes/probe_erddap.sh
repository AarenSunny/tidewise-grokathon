#!/usr/bin/env bash
# TideWise research probe: satellite SST / chlorophyll / HAB via ERDDAP griddap. No keys.
set -u
P="https://coastwatch.pfeg.noaa.gov/erddap/griddap"
O="https://oceanwatch.pifsc.noaa.gov/erddap/griddap"
q(){ echo "-- $1"; curl -s -m 90 -w "  [HTTP %{http_code}, %{time_total}s]\n" "$1"; }
echo "### Primary: CoastWatch West Coast Node (pfeg)"
q "$P/jplMURSST41.csv?analysed_sst%5B(last)%5D%5B(37.75)%5D%5B(-122.9)%5D"
q "$P/jplMURSST41.csv?analysed_sst%5B(last)%5D%5B(37.75)%5D%5B(-122.5)%5D"   # near-shore pixel -> NaN (land mask)
q "$P/jplMURSST41anom1day.csv?sstAnom%5B(last)%5D%5B(37.75)%5D%5B(-122.9)%5D"
q "$P/jplMURSST41clim.csv?mean_sst%5B(322)%5D%5B(37.75)%5D%5B(-122.9)%5D,standard_deviation%5B(322)%5D%5B(37.75)%5D%5B(-122.9)%5D"
q "$P/jplMURSST42.csv?sst_anomaly%5B(last)%5D%5B(37.75)%5D%5B(-122.875)%5D"
q "$P/erdVHNchla1day.csv?chla%5B(last)%5D%5B(0.0)%5D%5B(37.6)%5D%5B(-122.6)%5D"
q "$P/erdVHNchla8day.csv?chla%5B(last)%5D%5B(0.0)%5D%5B(37.6)%5D%5B(-122.6)%5D"
q "$P/wvcharmV3_0day.csv?pseudo_nitzschia%5B(last)%5D%5B(37.5)%5D%5B(237.4)%5D,particulate_domoic%5B(last)%5D%5B(37.5)%5D%5B(237.4)%5D,cellular_domoic%5B(last)%5D%5B(37.5)%5D%5B(237.4)%5D,chla_filled%5B(last)%5D%5B(37.5)%5D%5B(237.4)%5D"
echo "### Backup servers"
for h in https://coastwatch.noaa.gov/erddap https://polarwatch.noaa.gov/erddap https://upwell.pfeg.noaa.gov/erddap; do
  echo "-- $h HTTP $(curl -s -m 45 -o /dev/null -w '%{http_code}' "$h/griddap/jplMURSST41.csv?analysed_sst%5B(last)%5D%5B(37.75)%5D%5B(-122.9)%5D")"
done
q "$O/goes-poes-1d-ghrsst-RAN.csv?analysed_sst%5B(last)%5D%5B(37.75)%5D%5B(237.1)%5D"
q "$O/noaa_snpp_chla_daily.csv?chlor_a%5B(last)%5D%5B(0.0)%5D%5B(37.6)%5D%5B(237.4)%5D"
q "$O/noaacwBLENDEDsstDaily.csv?analysed_sst%5B(last)%5D%5B(37.75)%5D%5B(237.1)%5D"
echo "### NASA CMR (MUR granule listing, no auth; download itself needs Earthdata login)"
curl -s -m 40 "https://cmr.earthdata.nasa.gov/search/granules.json?short_name=MUR-JPL-L4-GLOB-v4.1&sort_key=-start_date&page_size=1" | python3 -c "import json,sys;e=json.load(sys.stdin)['feed']['entry'][0];print(e['title'],e['time_start'])"
