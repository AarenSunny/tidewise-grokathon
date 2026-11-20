#!/usr/bin/env python3
"""C-HARM availability + staleness probe (CoastWatch/OceanView ERDDAP).

Usage: python3 08_charm_status.py [N_REPEATS] [SECONDS_BETWEEN]
Prints local-time stamped HTTP status + latency per probe, then data age from
time_coverage_end. C-HARM has been observed to flap (404 unknown datasetID,
503, one 23 s response) so repeat before declaring it down.
"""
import json, sys, time, datetime, urllib.request, urllib.error

BASES = ["https://coastwatch.pfeg.noaa.gov/erddap", "https://oceanview.pfeg.noaa.gov/erddap"]
IDS = ["wvcharmV3_0day", "wvcharmV3_1day", "wvcharmV3_3day"]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
GAP = float(sys.argv[2]) if len(sys.argv) > 2 else 10

def get(url, timeout=60):
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200], time.time() - t0
    except Exception as e:
        return None, str(e).encode(), time.time() - t0

end_times = {}
for i in range(N):
    for base in BASES:
        for ds in IDS:
            code, body, dt = get(f"{base}/info/{ds}/index.json")
            stamp = datetime.datetime.now().astimezone().strftime("%H:%M:%S %Z")
            print(f"{stamp}\t{code}\t{dt:.2f}s\t{base.split('//')[1].split('/')[0]}\t{ds}")
            if code == 200 and base.startswith("https://coastwatch"):
                try:
                    for r in json.loads(body)["table"]["rows"]:
                        if r[0] == "attribute" and r[1] == "NC_GLOBAL" and r[2] == "time_coverage_end":
                            end_times[ds] = r[4]
                except Exception:
                    pass
    if i < N - 1:
        time.sleep(GAP)

now = datetime.datetime.now(datetime.timezone.utc)
for ds, e in end_times.items():
    end = datetime.datetime.strptime(e, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    print(f"{ds}: time_coverage_end={e}  age={(now-end).total_seconds()/86400:.1f} days")
if not end_times:
    print("No 200 from coastwatch in this run (404/503) - retry with backoff.")
