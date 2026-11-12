import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { fmt } from '../../../ui/format';
import { LiftSession, TrainingSession } from '../home.types';

/** "06:32", "morning" → "Morning". */
export function timeOfDay(time: string | null): string | null {
  if (!time) return null;
  return /^\d/.test(time) ? time : time[0].toUpperCase() + time.slice(1);
}

/** Seconds per km as "5:23 /km". */
export function pace(seconds: number | null): string | null {
  if (seconds == null) return null;
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')} /km`;
}

/**
 * One session: the name, and under it on one line the time of day and what
 * was done (duration; for runs distance, duration and pace; the kcal it
 * adds). Skipped sessions aren't listed. No per-exercise detail.
 */
@Component({
  selector: 'app-session-line',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="name">{{ s().name }}@if (prs()) {<span class="prs"> ({{ prs() }} {{ prs() === 1 ? 'PR' : 'PRs' }})</span>}</span>
    <span class="meta num t2">{{ meta() }}</span>
  `,
  styles: `
    :host { display: grid; gap: 2px; padding: 9px 0; }
    :host + :host { border-top: 1px solid var(--divider); }
    .name { font-weight: 500; min-width: 0; }
    .prs { font-weight: 400; color: var(--text-2); }
    .meta { font-size: 13px; }
  `,
})
export class SessionLine {
  readonly s = input.required<TrainingSession | LiftSession>({ alias: 'session' });

  /** A lifting session's PRs ("Push (2 PRs)"); 0 or unknown shows nothing. */
  protected readonly prs = computed(() => {
    const s = this.s();
    return 'prs' in s ? s.prs : null;
  });

  protected readonly meta = computed(() => {
    const s = this.s();
    const parts = [timeOfDay(s.time)];
    if (s.distance_km != null) parts.push(`${fmt(s.distance_km, 1)} km`);
    if (s.minutes != null) parts.push(`${fmt(s.minutes)} min`);
    parts.push(pace(s.pace_s_per_km));
    if (s.kcal_counted) parts.push(`${fmt(s.kcal_counted)} kcal`);
    return parts.filter(Boolean).join(' · ');
  });
}
