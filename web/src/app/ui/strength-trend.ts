import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { LineChart } from './line-chart';
import { signed } from './format';
import { Tone } from './tone';

/**
 * web_strength_trend.schema.json (fa_coach/strength_trend.py): one point per
 * day, each the mean of the counting lifts' latest e1RM as % of their value
 * at the start of the 28 days before it; the rate in % per week, each lift
 * measured over its own span (at least 7 days) and averaged.
 */
export interface StrengthTrend {
  window_days: number;
  start: string;
  end: string;
  points: { date: string; pct: number | null }[];
  rate_pct_per_week: number | null;
  direction: 'rising' | 'flat' | 'falling' | null;
  lifts: number;
  /** Counting lifts with any session in the window ending on the day (2 not needed). */
  lifts_trained: number;
}

/** The text when the trend has no value: nothing trained, or lifts trained but none twice yet. */
export function strengthEmptyText(trend: StrengthTrend | null | undefined): string {
  return trend?.lifts_trained ? 'Not enough sessions yet' : 'No lifts in the last 4 weeks';
}

/** Rising green, within the ±1 % band neutral, falling red. */
export function strengthTone(trend: StrengthTrend | null | undefined): Tone {
  const d = trend?.direction;
  return d === 'rising' ? 'ok' : d === 'falling' ? 'bad' : 'muted';
}

/** 0.8 → "+0.8 %/wk". */
export function strengthRate(trend: StrengthTrend | null | undefined): string {
  return trend?.rate_pct_per_week == null ? '–' : `${signed(trend.rate_pct_per_week, 1)} %/wk`;
}

/**
 * The strength trend, large (the Training tab, ticket 08): the rate big, the
 * daily line below. Home's Workouts card draws the same data like the weight
 * card. Renders nothing without a value.
 */
@Component({
  selector: 'app-strength-trend',
  imports: [LineChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (trend(); as t) {
      @if (t.rate_pct_per_week != null) {
        <div class="large">
          <div><span class="big num" [class.ok]="tone() === 'ok'" [class.bad]="tone() === 'bad'">{{ rate() }}</span>
            <span class="t2"> over {{ t.window_days }} days</span></div>
          <app-line-chart [points]="points()" [tone]="tone()" [height]="64" [label]="'Strength ' + rate()" />
        </div>
      }
    }
  `,
  styles: `
    :host { display: block; }
    .large { display: grid; gap: 8px; }
  `,
})
export class StrengthTrendChart {
  readonly trend = input<StrengthTrend | null | undefined>(null);

  protected readonly points = computed(() => (this.trend()?.points ?? []).map((p) => p.pct));
  protected readonly rate = computed(() => strengthRate(this.trend()));
  protected readonly tone = computed(() => strengthTone(this.trend()));
}
