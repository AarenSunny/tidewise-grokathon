const PACIFIC_TIME_FORMATTER = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Los_Angeles',
  hour12: false,
  hour: '2-digit',
  minute: '2-digit',
});

export function isoToPacificMinutes(isoDatetime: string): number {
  const date = new Date(isoDatetime);
  if (Number.isNaN(date.getTime())) {
    return 0;
  }
  const parts = PACIFIC_TIME_FORMATTER.formatToParts(date);
  const hourPart = parts.find((p) => p.type === 'hour')?.value ?? '0';
  const minutePart = parts.find((p) => p.type === 'minute')?.value ?? '0';
  const hours = Number(hourPart) % 24;
  const minutes = Number(minutePart);
  return hours * 60 + minutes;
}

export function formatIsoToPacificTime(isoDatetime: string): string {
  return formatTime(isoToPacificMinutes(isoDatetime));
}

export function formatTime(minutesFromMidnight: number): string {
  const total = Math.round(minutesFromMidnight);
  const hours24 = Math.floor(total / 60);
  const mins = total % 60;
  const period = hours24 >= 12 ? 'PM' : 'AM';
  const hours12 = hours24 % 12 === 0 ? 12 : hours24 % 12;
  const minsStr = mins.toString().padStart(2, '0');
  return `${hours12}:${minsStr} ${period}`;
}

export function formatTimeNoPeriod(minutesFromMidnight: number): string {
  const total = Math.round(minutesFromMidnight);
  const hours24 = Math.floor(total / 60);
  const mins = total % 60;
  const hours12 = hours24 % 12 === 0 ? 12 : hours24 % 12;
  const minsStr = mins.toString().padStart(2, '0');
  return `${hours12}:${minsStr}`;
}

export function getPeriod(minutesFromMidnight: number): 'AM' | 'PM' {
  return Math.floor(minutesFromMidnight / 60) >= 12 ? 'PM' : 'AM';
}

export function formatRange(startMinutes: number, endMinutes: number): string {
  const startPeriod = getPeriod(startMinutes);
  const endPeriod = getPeriod(endMinutes);
  if (startPeriod === endPeriod) {
    return `${formatTimeNoPeriod(startMinutes)}–${formatTimeNoPeriod(endMinutes)} ${endPeriod}`;
  }
  return `${formatTime(startMinutes)}–${formatTime(endMinutes)}`;
}

export function formatRangeSpaced(startMinutes: number, endMinutes: number): string {
  const startPeriod = getPeriod(startMinutes);
  const endPeriod = getPeriod(endMinutes);
  if (startPeriod === endPeriod) {
    return `${formatTimeNoPeriod(startMinutes)} – ${formatTimeNoPeriod(endMinutes)} ${endPeriod}`;
  }
  return `${formatTime(startMinutes)} – ${formatTime(endMinutes)}`;
}

export function formatDuration(durationMinutes: number): string {
  const safe = Math.max(0, Math.round(durationMinutes));
  const hours = Math.floor(safe / 60);
  const mins = safe % 60;
  if (hours === 0) {
    return `${mins}m`;
  }
  return `${hours}h ${mins.toString().padStart(2, '0')}m`;
}

export function formatSignedHeight(heightFt: number): string {
  const abs = Math.abs(heightFt).toFixed(1);
  if (heightFt < 0) return `−${abs} ft`;
  if (heightFt > 0) return `+${abs} ft`;
  return `0.0 ft`;
}

export function formatHourTick(hour24: number, compact = false): string {
  const period = hour24 >= 12 ? 'PM' : 'AM';
  const hour12 = hour24 % 12 === 0 ? 12 : hour24 % 12;
  return compact ? `${hour12}` : `${hour12} ${period}`;
}

export function minutesToAxisPercent(
  minutes: number,
  axisStartMinutes: number,
  axisEndMinutes: number,
): number {
  const span = axisEndMinutes - axisStartMinutes;
  if (span <= 0) return 0;
  const pct = ((minutes - axisStartMinutes) / span) * 100;
  return Math.max(0, Math.min(100, pct));
}
