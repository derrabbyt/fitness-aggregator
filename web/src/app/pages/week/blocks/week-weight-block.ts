import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { dayLabel, fmt, signed } from '../../../ui/format';
import { WeightChart } from '../../home/weight-chart';
import { rateText, rateTone, toneClass } from '../../home/weight-format';
import { WeekView } from '../week.types';

/**
 * Week's weight: the trend at the week's end big, the weekly rate coloured
 * against the band beside it, the band and the weigh-in count under them,
 * and the week's chart (the trend inside the band corridor from the day
 * before the week, each weigh-in a dot). A week in progress shows the rate of
 * the last 7 days, as Home does.
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
            <div class="t2 small">7-day trend</div>
          </div>
          <div class="right">
            <div class="rate num m" [class]="toneClass(tone())">{{ rateText(w.weekly_rate_kg) }}</div>
            <div class="t2 small">{{ w.rate_window === 'week' ? 'this week' : 'last 7 days' }}</div>
          </div>
        </div>
        <app-weight-chart class="chart" [days]="w.series" [tone]="tone()" [height]="120"
                          [startLabel]="startLabel()" [endLabel]="endLabel()"
                          label="Weight this week: trend, band and weigh-ins" />
        <div class="facts small t2 num">
          @if (w.band; as b) { <span class="part">Band {{ signed(b.low, 2) }} to {{ signed(b.high, 2) }} kg/wk</span> }
          <span class="part" [class.warn]="short()">{{ w.weigh_ins }} of {{ w.days }} {{ w.days === 1 ? 'day' : 'days' }} weighed</span>
        </div>
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
    .facts { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 10px; }
    .part { white-space: nowrap; }
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
  /** Fewer weigh-ins than a judged week needs, once that can't be made up any more. */
  protected readonly short = computed(() => {
    const w = this.weight();
    return !!w && w.weigh_ins + (7 - w.days) < w.weigh_ins_needed;
  });
  protected readonly startLabel = computed(() => {
    const s = this.weight()?.series ?? [];
    return s.length ? dayLabel(s[0].date, false) : '';
  });
  protected readonly endLabel = computed(() => {
    const s = this.weight()?.series ?? [];
    return s.length ? dayLabel(s[s.length - 1].date, false) : '';
  });
}
