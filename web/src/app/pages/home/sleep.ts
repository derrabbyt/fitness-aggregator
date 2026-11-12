import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, map, of } from 'rxjs';
import { addDays } from '../../ui/format';

/**
 * Sleep is fa-api data, not the coach's (ADR 0001): GET /api/sleep?date= (or
 * ?start=&end= for several nights) and its `phone` field, the night ending on that date estimated from phone use
 * (src/fitness_aggregator/phone_sleep.py). A missing night or any error is
 * null, so the page shows "–".
 */
export interface Night {
  date: string;
  /** Hours asleep. */
  asleep: number;
  /** Local times "HH:MM". */
  from: string;
  to: string;
}

/** The `phone` field of /api/sleep (only what the page uses). */
interface PhoneSleep {
  asleep?: number;
  sleepStart?: string;
  sleepEnd?: string;
}

@Injectable({ providedIn: 'root' })
export class SleepApi {
  private readonly http = inject(HttpClient);

  /** The night ending on `date`, null without data or on error. */
  night(date: string): Observable<Night | null> {
    return this.http.get<{ phone?: PhoneSleep | null }>('/api/sleep', { params: { date } }).pipe(
      map((r) => toNight(date, r?.phone)),
      catchError(() => of(null)),
    );
  }

  /** The `count` nights ending on `date`, oldest first, null where there is none (one request:
   *  GET /api/sleep?start=&end=; every night null on error). */
  nights(date: string, count: number): Observable<{ date: string; night: Night | null }[]> {
    const dates = Array.from({ length: count }, (_, i) => addDays(date, i - count + 1));
    const params = { start: dates[0], end: date };
    return this.http.get<{ nights?: { date: string; phone?: PhoneSleep | null }[] }>('/api/sleep', { params }).pipe(
      map((r) => new Map((r?.nights ?? []).map((n) => [n.date, n.phone]))),
      catchError(() => of(new Map<string, PhoneSleep | null | undefined>())),
      map((byDate) => dates.map((d) => ({ date: d, night: toNight(d, byDate.get(d)) }))),
    );
  }
}

function toNight(date: string, p: PhoneSleep | null | undefined): Night | null {
  if (!p || typeof p.asleep !== 'number' || !p.sleepStart || !p.sleepEnd) return null;
  return { date, asleep: p.asleep, from: clock(p.sleepStart), to: clock(p.sleepEnd) };
}

/** "2026-11-10T06:46+01:00" → "06:46" (fa-api sends local times). */
function clock(iso: string): string {
  return iso.slice(11, 16);
}
