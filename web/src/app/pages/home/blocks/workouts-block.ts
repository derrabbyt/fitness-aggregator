import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { LineChart } from '../../../ui/line-chart';
import { strengthRate, strengthTone } from '../../../ui/strength-trend';
import { toneClass } from '../weight-format';
import { HomeView } from '../home.types';
import { SessionLine } from './session-line';

/**
 * Home's Workouts card (tickets 05 and 14), always shown: the day's lifting
 * sessions, one line each with their PRs ("No workout" without one), then
 * the 14-day strength trend styled like the weight card (rate in % per week
 * top right, coloured rising / within the band / falling), and under it the
 * lift summary over the last 14 days. Taps open Training.
 */
@Component({
  selector: 'app-workouts-block',
  imports: [Card, SessionLine, LineChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (workouts(); as w) {
      <app-card label="Workouts" link="/training">
        <div class="top">
          <div class="sessions">
            @for (s of w.sessions; track $index) {
              <app-session-line [session]="s" />
            } @empty {
              <div class="none t2">No workout</div>
            }
          </div>
          @if (w.strength_trend.rate_pct_per_week != null) {
            <div class="rate num m" [class]="toneClass(tone())">{{ rate() }}</div>
          }
        </div>
        <app-line-chart class="spark" [points]="points()" [tone]="tone()" [height]="56"
                        startLabel="14 days" [endLabel]="view().is_today ? 'today' : ''"
                        emptyText="No lifts in the last 4 weeks"
                        [label]="'Strength trend, last 14 days, ' + rate()" />
        @if (summaryParts().length) {
          <div class="summary small t2">@for (part of summaryParts(); track $index) {@if ($index) { · }<span class="part">{{ part }}</span>}</div>
        }
      </app-card>
    }
  `,
  styles: `
    .top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
    .sessions { flex: 1; min-width: 0; }
    .none { padding: 9px 0; }
    .rate { font-size: 15px; padding-top: 9px; white-space: nowrap; }
    .rate:not(.ok):not(.bad):not(.warn) { color: var(--text-2); }
    .spark { margin-top: 12px; }
    .summary { margin-top: 10px; }
    .part { white-space: nowrap; }
  `,
})
export class WorkoutsBlock {
  readonly view = input.required<HomeView>();
  readonly dayQuery = input<Record<string, string | null>>({});

  protected readonly toneClass = toneClass;
  protected readonly workouts = computed(() => this.view().training?.workouts ?? null);
  protected readonly points = computed(() => (this.workouts()?.strength_trend.points ?? []).map((p) => p.pct));
  protected readonly rate = computed(() => strengthRate(this.workouts()?.strength_trend));
  protected readonly tone = computed(() => strengthTone(this.workouts()?.strength_trend));

  /** "5 of 7 lifts progressing · 1 stall · 2 PRs"; zeros left out. */
  protected readonly summaryParts = computed(() => {
    const t = this.workouts()?.summary;
    if (!t) return [];
    const parts: string[] = [];
    if (t.counted) parts.push(`${t.progressing} of ${t.counted} ${t.counted === 1 ? 'lift' : 'lifts'} progressing`);
    if (t.stalls) parts.push(`${t.stalls} ${t.stalls === 1 ? 'stall' : 'stalls'}`);
    if (t.prs) parts.push(`${t.prs} ${t.prs === 1 ? 'PR' : 'PRs'}`);
    return parts;
  });
}
