import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, forkJoin, map, of } from 'rxjs';
import { addDays } from '../../ui/format';

/**
 * Sleep is fa-api data, not the coach's (ADR 0001): GET /api/sleep?date= and
 * its `phone` field, the night ending on that date estimated from phone use
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

  /** The `count` nights ending on `date`, oldest first, null where there is none. */
  nights(date: string, count: number): Observable<{ date: string; night: Night | null }[]> {
    const dates = Array.from({ length: count }, (_, i) => addDays(date, i - count + 1));
    return forkJoin(dates.map((d) => this.night(d))).pipe(map((nights) => dates.map((d, i) => ({ date: d, night: nights[i] }))));
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
