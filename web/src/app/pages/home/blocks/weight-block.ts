import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { dayLabel, fmt } from '../../../ui/format';
import { LineChart } from '../../../ui/line-chart';
import { HomeView } from '../home.types';
import { rateText, rateTone, toneClass } from '../weight-format';

/**
 * Home's weight block (direction from ticket 01): the day's weigh-in big, the
 * weekly rate coloured against the band beside it, and the 14-day trend line.
 * No trend value and no band text here; both live in the weight detail.
 */
@Component({
  selector: 'app-weight-block',
  imports: [Card, LineChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (weight(); as w) {
      <app-card label="Weight" link="/home/weight" [queryParams]="dayQuery()">
        <div class="top">
          <div>
            @if (today(); as wi) {
              <div class="big num">{{ fmt(wi.kg, 1) }}<span class="unit"> kg</span></div>
              @if (wi.outlier) { <div class="t2 small">Outlier · not in the trend</div> }
            } @else {
              <div class="big num t3">–<span class="unit"> kg</span></div>
              <div class="t2 small">
                @if (w.weigh_in; as last) { Last {{ fmt(last.kg, 1) }} kg · {{ dayLabel(last.date) }} }
                @else { No weigh-ins yet }
              </div>
            }
          </div>
          @if (w.weekly_rate_kg != null) {
            <div class="rate num m" [class]="toneClass(tone())">{{ rateText(w.weekly_rate_kg) }}</div>
          }
        </div>
        <app-line-chart class="spark" [points]="points()" [tone]="tone()" [height]="56"
                        startLabel="14 days" [endLabel]="view().is_today ? 'today' : ''"
                        label="7-day trend, last 14 days" />
      </app-card>
    }
  `,
  styles: `
    .top { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
    .unit { font-size: 16px; font-weight: 400; color: var(--text-2); letter-spacing: 0; }
    .rate { font-size: 15px; padding-bottom: 6px; white-space: nowrap; }
    .rate:not(.ok):not(.bad):not(.warn) { color: var(--text-2); }
    .spark { margin-top: 12px; }
  `,
})
export class WeightBlock {
  readonly view = input.required<HomeView>();
  readonly dayQuery = input<Record<string, string | null>>({});

  protected readonly fmt = fmt;
  protected readonly dayLabel = dayLabel;
  protected readonly rateText = rateText;
  protected readonly toneClass = toneClass;
  protected readonly weight = computed(() => this.view().weight ?? null);
  /** The weigh-in of the day shown, if there is one. */
  protected readonly today = computed(() => {
    const wi = this.weight()?.weigh_in;
    return wi && wi.date === this.view().date ? wi : null;
  });
  protected readonly tone = computed(() => rateTone(this.weight()?.vs_band ?? null));
  protected readonly points = computed(() => (this.weight()?.series ?? []).map((p) => p.trend_kg));
}
