/** Daylight bands for the 48–72h timeline. Geometry only — not condition data. */

const RAD = Math.PI / 180;

export function sunTimesUtc(date, lat, lon) {
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth();
  const day = date.getUTCDate();
  const dayOfYear = Math.floor(
    (Date.UTC(year, month, day) - Date.UTC(year, 0, 0)) / 86400000
  );
  const zenith = 90.833;
  const lngHour = lon / 15;

  function event(rising) {
    const approx = dayOfYear + ((rising ? 6 : 18) - lngHour) / 24;
    const mean = 0.9856 * approx - 3.289;
    let longitude = mean + 1.916 * Math.sin(mean * RAD) + 0.02 * Math.sin(2 * mean * RAD) + 282.634;
    longitude = (longitude + 360) % 360;
    let rightAsc = Math.atan(0.91764 * Math.tan(longitude * RAD)) / RAD;
    rightAsc = (rightAsc + 360) % 360;
    const lQuad = Math.floor(longitude / 90) * 90;
    const raQuad = Math.floor(rightAsc / 90) * 90;
    rightAsc = (rightAsc + (lQuad - raQuad)) / 15;
    const sinDec = 0.39782 * Math.sin(longitude * RAD);
    const cosDec = Math.cos(Math.asin(sinDec));
    const cosHour = (Math.cos(zenith * RAD) - sinDec * Math.sin(lat * RAD)) / (cosDec * Math.cos(lat * RAD));
    if (cosHour > 1 || cosHour < -1) return null;
    const hourAngle = (rising ? 360 - Math.acos(cosHour) / RAD : Math.acos(cosHour) / RAD) / 15;
    let universal = hourAngle + rightAsc - 0.06571 * approx - 6.622 - lngHour;
    let dayOffset = 0;
    while (universal < 0) {
      universal += 24;
      dayOffset -= 1;
    }
    while (universal >= 24) {
      universal -= 24;
      dayOffset += 1;
    }
    return Date.UTC(year, month, day + dayOffset, 0, 0, 0) + universal * 3600000;
  }

  return { sunrise: event(true), sunset: event(false) };
}

export function daylightBands(startMs, endMs, lat, lon) {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return [];
  const bands = [];
  const first = Date.UTC(
    new Date(startMs).getUTCFullYear(),
    new Date(startMs).getUTCMonth(),
    new Date(startMs).getUTCDate() - 1
  );
  const last = endMs + 86400000;
  for (let cursor = first; cursor <= last; cursor += 86400000) {
    const { sunrise, sunset } = sunTimesUtc(new Date(cursor), lat, lon);
    if (sunrise == null || sunset == null || sunset <= sunrise) continue;
    const bandStart = Math.max(sunrise, startMs);
    const bandEnd = Math.min(sunset, endMs);
    if (bandEnd > bandStart) bands.push({ start: bandStart, end: bandEnd });
  }
  return bands;
}

export function fractionBetween(value, start, end) {
  const span = end - start;
  if (span <= 0) return 0;
  return Math.min(1, Math.max(0, (value - start) / span));
}
