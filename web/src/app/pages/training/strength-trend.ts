import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { signed } from '../../ui/format';
import { LineChart } from '../../ui/line-chart';
import { Tone } from '../../ui/tone';
import { StrengthTrend } from './training.types';

/** Green when rising, red when falling, neutral when flat (the coach decides, within ±band). */
export function trendTone(t: StrengthTrend): Tone {
  return t.direction === 'rising' ? 'ok' : t.direction === 'falling' ? 'bad' : 'neutral';
}

/** "+3.2 %" */
export function trendNumber(t: StrengthTrend): string {
  return t.change_pct == null ? '–' : `${signed(t.change_pct, 1)} %`;
}

/**
 * The strength trend: one thin line and one number ("+3.2 % in 4 weeks").
 * `size="large"` is the Training tab's version; the default is small enough for
 * a card corner (Home's Gym block).
 */
@Component({
  selector: 'app-strength-trend',
  imports: [LineChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (trend().change_pct != null) {
      <div class="head" [class.large]="size() === 'large'">
        <span class="num value" [class.big]="size() === 'large'" [class.m]="size() !== 'large'"
              [class.ok]="tone() === 'ok'" [class.bad]="tone() === 'bad'">{{ number() }}</span>
        <span class="t2 small">in {{ weeks() }} weeks</span>
      </div>
      <app-line-chart [points]="points()" [tone]="tone()" [height]="size() === 'large' ? 72 : 32"
                      [label]="'Strength ' + number() + ' in ' + weeks() + ' weeks'" />
    } @else {
      <div class="t2 small">Not enough sessions yet</div>
    }
  `,
  styles: `
    :host { display: block; }
    .head { display: flex; align-items: baseline; gap: 6px; margin-bottom: 6px; }
    .head.large { margin-bottom: 12px; }
  `,
})
export class StrengthTrendChart {
  readonly trend = input.required<StrengthTrend>();
  readonly size = input<'small' | 'large'>('small');

  protected readonly tone = computed(() => trendTone(this.trend()));
  protected readonly number = computed(() => trendNumber(this.trend()));
  protected readonly weeks = computed(() => Math.round(this.trend().days / 7));
  protected readonly points = computed(() => this.trend().points.map((p) => p.change_pct));
}
