import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { LineChart } from './line-chart';
import { signed } from './format';
import { Tone } from './tone';

/** web_strength_trend.schema.json: the 4-week strength trend (fa_coach/strength_trend.py). */
export interface StrengthTrend {
  days: number;
  start: string;
  end: string;
  weeks: { iso_week: string; change_pct: number | null }[];
  change_pct: number | null;
  direction: 'rising' | 'flat' | 'falling' | null;
  lifts: number;
}

/**
 * The strength trend as one graph: a thin line and its number, green when
 * rising, gray within the band, red when falling. `size="small"` (Home's Gym
 * block): the line and "+3.2 %" only, no axes, legend or text. `size="large"`
 * (Training tab): the number big with "in 4 weeks", the line below.
 * Renders nothing without a value.
 */
@Component({
  selector: 'app-strength-trend',
  imports: [LineChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (trend(); as t) {
      @if (t.change_pct != null) {
        @if (size() === 'small') {
          <div class="small" role="img" [attr.aria-label]="'Strength ' + text() + ' in ' + weeks() + ' weeks'">
            <app-line-chart class="line" [points]="points()" [tone]="tone()" [height]="26" aria-hidden="true" />
            <span class="v num m" [class.ok]="tone() === 'ok'" [class.bad]="tone() === 'bad'">{{ text() }}</span>
          </div>
        } @else {
          <div class="large">
            <div><span class="big num" [class.ok]="tone() === 'ok'" [class.bad]="tone() === 'bad'">{{ text() }}</span>
              <span class="t2"> in {{ weeks() }} weeks</span></div>
            <app-line-chart [points]="points()" [tone]="tone()" [height]="64" [label]="'Strength ' + text()" />
          </div>
        }
      }
    }
  `,
  styles: `
    :host { display: block; }
    .small { display: flex; align-items: center; gap: 8px; }
    .line { width: 64px; flex: none; }
    .v { font-size: 13px; white-space: nowrap; }
    .large { display: grid; gap: 8px; }
  `,
})
export class StrengthTrendChart {
  readonly trend = input<StrengthTrend | null | undefined>(null);
  readonly size = input<'small' | 'large'>('small');

  protected readonly points = computed(() => (this.trend()?.weeks ?? []).map((w) => w.change_pct));
  protected readonly weeks = computed(() => Math.round((this.trend()?.days ?? 28) / 7));
  protected readonly text = computed(() => `${signed(this.trend()?.change_pct, 1)} %`);
  protected readonly tone = computed<Tone>(() => {
    const d = this.trend()?.direction;
    return d === 'rising' ? 'ok' : d === 'falling' ? 'bad' : 'muted';
  });
}
