import { ChangeDetectionStrategy, Component, computed, effect, inject, untracked } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { viewResource } from '../../api/view-resource';
import { DayNav } from '../../shell/day-nav';
import { injectDay } from '../../shell/day-param';
import { RefreshButton } from '../../shell/refresh-button';
import { Card } from '../../ui/card';
import { dayLabel, fmt, signed } from '../../ui/format';
import { SectionHeader } from '../../ui/section-header';
import { State } from '../../ui/state';
import { toneColor } from '../../ui/tone';
import { WeightChart } from './weight-chart';
import { rateText, rateTone, toneClass } from './weight-format';
import { WeightDetail } from './weight.types';

const RANGES = [{ weeks: '4', label: '4 weeks' }, { weeks: '12', label: '12 weeks' }];

/**
 * Weight detail: the weigh-in, the 7-day trend and the weekly rate against the
 * band (in words here, unlike Home), a 4- or 12-week chart (`?weeks=12`) with
 * the band shaded, this week's predicted vs actual trend, recent weigh-ins
 * with outliers marked, and waist values. All as of the day shown.
 */
@Component({
  selector: 'app-weight-detail-page',
  imports: [DayNav, RefreshButton, Card, SectionHeader, State, WeightChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-day-nav heading="Weight" [day]="day.value()" back="/home" [backQuery]="day.query()"
                   (dayChange)="day.go($event)">
        <app-refresh-button actions [busy]="detail.refreshing()" (refresh)="detail.refresh()" />
      </app-day-nav>
      @if (detail.refreshError(); as err) { <p class="warn small m">Sync failed: {{ err }}</p> }
      @if (detail.data(); as d) {
        <div class="cols">
          <div class="stack">
            <app-card>
              <div class="top">
                <div>
                  <div class="label">{{ weighedToday() ? 'Weigh-in' : 'Last weigh-in' }}</div>
                  <div class="big num" [class.t2]="!d.weigh_in">{{ fmt(d.weigh_in?.kg, 1) }}<span class="unit"> kg</span></div>
                  @if (d.weigh_in; as wi) {
                    <div class="t2 small">
                      @if (!weighedToday()) { {{ dayLabel(wi.date) }} }
                      @if (wi.outlier) { {{ weighedToday() ? '' : '· ' }}Outlier, not in the trend }
                    </div>
                  }
                </div>
                <div class="right">
                  <div class="label">7-day trend</div>
                  <div class="mid num">{{ fmt(d.trend_kg, 2) }}<span class="unit sm"> kg</span></div>
                </div>
              </div>
              <div class="rate-row">
                <span class="num m" [class]="toneClass(tone())">{{ rateText(d.weekly_rate_kg) }}</span>
                <span class="t2">{{ bandText() }}</span>
              </div>
            </app-card>

            <app-card>
              <div class="chart-head">
                <div class="seg" role="tablist" aria-label="Range">
                  @for (r of ranges; track r.weeks) {
                    <button role="tab" [attr.aria-selected]="r.weeks === weeks()" [class.on]="r.weeks === weeks()"
                            (click)="setWeeks(r.weeks)">{{ r.label }}</button>
                  }
                </div>
              </div>
              <app-weight-chart [days]="d.series" [tone]="tone()" [startLabel]="startLabel()"
                                [endLabel]="day.isToday() ? 'today' : dayLabel(d.date, false)"
                                [label]="'Weight, last ' + d.weeks + ' weeks'" />
              <div class="legend t2">
                <span><i class="k line" [style.background]="lineColor()"></i>7-day trend</span>
                <span><i class="k dot"></i>Weigh-in</span>
                @if (hasBand()) { <span><i class="k band"></i>Target band</span> }
                @if (hasOutlier()) { <span><i class="k out"></i>Outlier</span> }
              </div>
            </app-card>

            @if (d.prediction; as p) {
              <app-card label="This week">
                <div class="pred">
                  <div>
                    <div class="t2 small">Predicted</div>
                    <div class="mid num">{{ fmt(p.predicted_kg, 2) }}<span class="unit sm"> kg</span></div>
                  </div>
                  <div>
                    <div class="t2 small">{{ p.complete ? 'Actual' : 'So far' }}</div>
                    <div class="mid num">{{ fmt(p.actual_kg, 2) }}<span class="unit sm"> kg</span></div>
                  </div>
                  <div class="right">
                    <div class="t2 small">Difference</div>
                    <div class="mid num">{{ signed(p.difference_kg, 2) }}</div>
                  </div>
                </div>
                <div class="t2 small foot">7-day trend · {{ dayLabel(p.start, false) }} – {{ dayLabel(p.end, false) }}</div>
              </app-card>
            }
          </div>

          <div class="stack">
            <app-section-header title="Weigh-ins" [aside]="d.recent.length ? 'last ' + d.recent.length : ''" />
            <app-card>
              @if (d.recent.length) {
                <ul class="rows">
                  @for (w of d.recent; track w.date) {
                    <li [class.outlier]="w.outlier">
                      <span>{{ dayLabel(w.date) }}</span>
                      <span class="num">
                        @if (w.outlier) { <span class="tag">Outlier</span> }
                        <span class="m">{{ fmt(w.kg, 1) }}</span><span class="t2"> kg</span>
                      </span>
                    </li>
                  }
                </ul>
              } @else {
                <p class="none t2">No weigh-ins yet</p>
              }
            </app-card>

            <app-section-header title="Waist" />
            <app-card>
              @if (d.waist.length) {
                <ul class="rows">
                  @for (w of d.waist; track w.date) {
                    <li>
                      <span>{{ dayLabel(w.date) }}</span>
                      <span class="num"><span class="m">{{ fmt(w.cm, 1) }}</span><span class="t2"> cm</span></span>
                    </li>
                  }
                </ul>
              } @else {
                <p class="none t2">No waist values yet</p>
              }
            </app-card>
          </div>
        </div>
      } @else if (detail.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="detail.load()" />
      } @else {
        <app-state kind="loading" [blocks]="3" />
      }
    </div>
  `,
  styles: `
    .cols { display: grid; gap: 12px; }
    @media (min-width: 900px) { .cols { grid-template-columns: 3fr 2fr; gap: 16px; align-items: start; } }
    .top { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; }
    .top .label { margin-bottom: 4px; }
    .right { text-align: right; }
    .unit { font-size: 16px; font-weight: 400; color: var(--text-2); letter-spacing: 0; }
    .unit.sm { font-size: 13px; }
    .rate-row { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; margin-top: 14px;
                padding-top: 12px; border-top: 1px solid var(--divider); }
    .rate-row .m:not(.ok):not(.bad):not(.warn) { color: var(--text); }
    .chart-head { display: flex; justify-content: flex-end; margin-bottom: 14px; }
    .seg { display: inline-flex; background: var(--inset); padding: 3px; border-radius: 9px; gap: 2px; }
    .seg button { font-size: 13px; font-weight: 500; padding: 4px 12px; border-radius: 7px; color: var(--text-2); }
    .seg button.on { background: var(--container); color: var(--text); box-shadow: var(--ring); }
    .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; margin-top: 10px; }
    .legend span { display: inline-flex; align-items: center; gap: 6px; }
    .k { display: inline-block; flex: none; }
    .k.line { width: 12px; height: 2px; border-radius: 2px; }
    .k.dot { width: 5px; height: 5px; border-radius: 99px; background: var(--text-3); }
    .k.band { width: 12px; height: 8px; border-radius: 2px; background: var(--text); opacity: .1; }
    .k.out { width: 8px; height: 8px; border-radius: 99px; box-shadow: inset 0 0 0 1.5px var(--destructive); }
    .pred { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
    .foot { margin-top: 10px; }
    .rows { list-style: none; margin: 0; padding: 0; }
    .rows li { display: flex; justify-content: space-between; align-items: baseline; padding: 9px 0;
               border-top: 1px solid var(--divider); }
    .rows li:first-child { border-top: 0; padding-top: 0; }
    .rows li:last-child { padding-bottom: 0; }
    .rows li.outlier .m { color: var(--text-2); text-decoration: line-through; }
    .tag { font-size: 11px; font-weight: 500; color: var(--destructive); margin-right: 8px; }
    .none { margin: 0; font-size: 13px; }
    p.warn { margin: -6px 2px 12px; }
  `,
})
export class WeightDetailPage {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  protected readonly day = injectDay();
  protected readonly detail = viewResource<WeightDetail>('home/weight');
  protected readonly ranges = RANGES;
  protected readonly fmt = fmt;
  protected readonly signed = signed;
  protected readonly dayLabel = dayLabel;
  protected readonly rateText = rateText;
  protected readonly toneClass = toneClass;

  private readonly params = toSignal(this.route.queryParamMap, { initialValue: this.route.snapshot.queryParamMap });
  protected readonly weeks = computed(() => (this.params().get('weeks') === '12' ? '12' : '4'));
  protected readonly tone = computed(() => rateTone(this.detail.data()?.vs_band ?? null));
  protected readonly lineColor = computed(() => toneColor(this.tone()));
  protected readonly weighedToday = computed(() => {
    const d = this.detail.data();
    return !!d?.weigh_in && d.weigh_in.date === d.date;
  });
  protected readonly hasBand = computed(() => !!this.detail.data()?.series.some((x) => x.band_low_kg != null));
  protected readonly hasOutlier = computed(() => !!this.detail.data()?.series.some((x) => x.outlier && x.kg != null));
  protected readonly startLabel = computed(() => {
    const d = this.detail.data();
    return d?.series.length ? dayLabel(d.series[0].date, false) : '';
  });
  /** The band in words, with the verdict ("in the band 0.10–0.30 kg/wk"). */
  protected readonly bandText = computed(() => {
    const d = this.detail.data();
    if (!d) return '';
    if (!d.band) return 'No target band';
    const band = `${signed(d.band.low, 2)} to ${signed(d.band.high, 2)} kg/wk`;
    switch (d.vs_band) {
      case 'in_band': return `in the band, ${band}`;
      case 'below_band': return `below the band, ${band}`;
      case 'above_band': return `above the band, ${band}`;
      case 'below_limit': return `below the limit of ${signed(d.band.lower_limit, 2)} kg/wk`;
      case 'above_limit': return `above the limit of ${signed(d.band.upper_limit, 2)} kg/wk`;
      case 'not_evaluated': return `not judged yet (glycogen weeks) · band ${band}`;
      default: return `band ${band}`;
    }
  });

  constructor() {
    effect(() => {
      const day = this.day.query().day;
      const weeks = this.weeks();
      untracked(() => this.detail.load({ day, weeks: weeks === '4' ? null : weeks }));
    });
  }

  protected setWeeks(weeks: string): void {
    void this.router.navigate([], { relativeTo: this.route, queryParams: { weeks: weeks === '4' ? null : weeks },
      queryParamsHandling: 'merge', replaceUrl: true });
  }
}
