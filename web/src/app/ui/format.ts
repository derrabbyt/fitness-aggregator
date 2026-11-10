/** Number and date formatting shared by every page. Dates are "YYYY-MM-DD" in local time. */

const NUMBER = new Intl.NumberFormat('en-US');

/** 1980 → "1,980"; null → "–". */
export function fmt(n: number | null | undefined, digits = 0): string {
  if (n == null) return '–';
  return digits
    ? n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : NUMBER.format(Math.round(n));
}

/** With a sign and a real minus: 48 → "+48", -48 → "−48", 0 → "0". */
export function signed(n: number | null | undefined, digits = 0): string {
  if (n == null) return '–';
  const s = fmt(Math.abs(n), digits);
  return n > 0 ? `+${s}` : n < 0 ? `−${s}` : s;
}

/** Hours as "7 h 36". */
export function hoursMinutes(hours: number | null | undefined): string {
  if (hours == null) return '–';
  const m = Math.round(hours * 60);
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`;
}

/** Today's date in local time. */
export function todayIso(): string {
  return isoDate(new Date());
}

/** YYYY-MM-DD in local time (toISOString would use UTC). */
export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function parseIso(day: string): Date {
  return new Date(`${day}T12:00:00`);
}

export function addDays(day: string, n: number): string {
  const d = parseIso(day);
  d.setDate(d.getDate() + n);
  return isoDate(d);
}

export function isIsoDate(value: string | null | undefined): value is string {
  return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(parseIso(value).getTime());
}

/** "Tue 10 Nov" (with the year when it isn't this year's). */
export function dayLabel(day: string, withWeekday = true): string {
  const d = parseIso(day);
  const parts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
  if (withWeekday) parts.weekday = 'short';
  if (d.getFullYear() !== new Date().getFullYear()) parts.year = 'numeric';
  return d.toLocaleDateString('en-GB', parts).replace(',', '');
}

/** "Tue" */
export function weekday(day: string): string {
  return parseIso(day).toLocaleDateString('en-GB', { weekday: 'short' });
}

/** A time span from now: "35 min", "7 h", "2 days". */
export function ago(hours: number): string {
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} min`;
  if (hours < 48) return `${Math.round(hours)} h`;
  return `${Math.round(hours / 24)} days`;
}
