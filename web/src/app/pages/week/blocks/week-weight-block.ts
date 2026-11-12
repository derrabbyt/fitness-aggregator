import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { fmt, signed } from '../../../ui/format';
import { WeightChart } from '../../home/weight-chart';
import { rateText, rateTone, toneClass } from '../../home/weight-format';
import { WeekView } from '../week.types';

/**
 * Week's weight: the average at the week's end big (the week's average once
 * it's judged, the last 7 days while it runs), the weekly rate coloured
 * against the goal beside it with the goal under it, and the week's chart
 * (axes, hover values, the goal corridor, each weigh-in a dot). The weigh-in
 * count lives in the "So far" card.
 */
@Component({
  selector: 'app-week-weight-block',
  imports: [Card, WeightChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (weight(); as w) {
      <app-card label="Weight">
        <div class="top">
          <div>
            <div class="big num">{{ fmt(w.trend_kg, 1) }}<span class="unit"> kg</span></div>
            <div class="t2 small">{{ w.rate_window === 'week' ? 'week avg' : '7-day avg' }}</div>
          </div>
          <div class="right">
            <div class="rate num m" [class]="toneClass(tone())">{{ rateText(w.weekly_rate_kg) }}</div>
            @if (w.band; as b) { <div class="t2 small num">goal {{ signed(b.low, 2) }} to {{ signed(b.high, 2) }}</div> }
          </div>
        </div>
        <app-weight-chart class="chart" [days]="w.series" [tone]="tone()" [height]="140"
                          label="Weight this week: average, goal and weigh-ins" />
      </app-card>
    }
  `,
  styles: `
    .top { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
    .right { text-align: right; }
    .unit { font-size: 16px; font-weight: 400; color: var(--text-2); letter-spacing: 0; }
    .rate { font-size: 15px; white-space: nowrap; }
    .rate:not(.ok):not(.bad):not(.warn) { color: var(--text-2); }
    .chart { margin-top: 14px; }
  `,
})
export class WeekWeightBlock {
  readonly view = input.required<WeekView>();

  protected readonly fmt = fmt;
  protected readonly signed = signed;
  protected readonly rateText = rateText;
  protected readonly toneClass = toneClass;
  protected readonly weight = computed(() => this.view().weight ?? null);
  protected readonly tone = computed(() => rateTone(this.weight()?.vs_band ?? null));
}
