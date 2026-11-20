#!/usr/bin/env bash
# CDPH shellfish/biotoxin live-source probe. No secrets needed.
# www.cdph.ca.gov serves the wrong intermediate (leaf issuer = Sectigo Public Server
# Authentication CA OV R36, which is not sent). Fix: fetch the AIA intermediate and append it.
set -u
UA="${UA:-tidewise-research-probe}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
URL="https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx"

echo "== strict TLS (expected to FAIL, exit 60) =="
curl -sS -o /dev/null -w "%{http_code} verify=%{ssl_verify_result}\n" --max-time 30 -A "$UA" "$URL" 2>&1 | tail -1
echo "== leaf cert dates =="
echo | openssl s_client -connect www.cdph.ca.gov:443 -servername www.cdph.ca.gov 2>/dev/null | openssl x509 -noout -issuer -dates
echo "== workaround: add AIA intermediate =="
curl -sS -o "$TMP/r36.der" --max-time 20 http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt
openssl x509 -inform DER -in "$TMP/r36.der" -out "$TMP/r36.pem"
CABUNDLE="${CABUNDLE:-/etc/ssl/certs/ca-certificates.crt}"
cat "$CABUNDLE" "$TMP/r36.pem" > "$TMP/bundle.pem"
curl -sS -o "$TMP/adv.html" -w "%{http_code} verify=%{ssl_verify_result}\n" --max-time 60 -A "$UA" --cacert "$TMP/bundle.pem" "$URL"

echo "== dated 2026 headlines (newest first as on page) =="
python3 - "$TMP/adv.html" <<'PY'
import re, html, sys
t = open(sys.argv[1], encoding="utf-8", errors="replace").read()
t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
L = [l.strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", t)).replace("\u200b", "").split("\n") if l.strip()]
pat = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, 2026")
seen = set()
for i, l in enumerate(L):
    if pat.match(l) and i > 0 and l not in seen:
        seen.add(l)
        print(f"{L[i-1][:95]} || {l[:150]}")
    if len(seen) >= 12: break
PY

echo "== ArcGIS layer lastEditDate (static-pin check) =="
B="https://services2.arcgis.com/wi1yEacfYjH5viqb/arcgis/rest/services"
for L in "Health_Advisory_Symbols_(Red)/FeatureServer/0" "California_Coastal_Counties/FeatureServer/3" "All_Bivalve_Shellfish_Health_Advisory_Special_Advisory/FeatureServer/3"; do
  curl -sS --max-time 40 "$B/$L?f=json" | python3 -c "
import sys,json,datetime
d=json.load(sys.stdin); e=d.get('editingInfo',{}).get('lastEditDate')
print(d.get('name'), datetime.datetime.fromtimestamp(e/1000,datetime.timezone.utc).date() if e else None)"
done

echo "== RSS/feeds (expect 404) =="
for u in "https://www.cdph.ca.gov/Programs/OPA/Pages/NR_RSS.aspx" "https://www.cdph.ca.gov/Pages/RSS.aspx" "https://public.govdelivery.com/accounts/CACDPH/subscriber/new"; do
  echo "$(curl -sS -L -o /dev/null -w '%{http_code}' --max-time 30 --cacert "$TMP/bundle.pem" "$u") $u"
done
