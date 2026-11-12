import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
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
import { WeightChart } from './weight-chart';
import { rateText, rateTone, toneClass } from './weight-format';
import { WeightDetail } from './weight.types';

const RANGES = [
  { weeks: '1', label: '1 week' }, { weeks: '2', label: '2 weeks' }, { weeks: '4', label: '4 weeks' },
  { weeks: '12', label: '12 weeks' }, { weeks: '26', label: '6 months' }, { weeks: 'all', label: 'All time' },
];
const DEFAULT_WEEKS = '4';
const WEIGH_INS_SHOWN = 7;

/**
 * Weight detail: the weigh-in, the 7-day average and the weekly rate with
 * its goal, the chart for a range from a dropdown (`?weeks=`, 4 weeks by
 * default), this week's predicted vs actual average, the latest weigh-ins
 * (all of them on "Show all") with outliers marked, and waist values. All as
 * of the day shown.
 */
@Component({
  selector: 'app-weight-detail-page',
  imports: [DayNav, RefreshButton, Card, SectionHeader, State, WeightChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-day-nav heading="Weight" [day]="day.value()" back="/home" [backQuery]="day.query()"
                   (dayChange)="day.go($event)">
        <app-refresh-button actions [busy]="detail.refreshing()" [done]="detail.refreshed()" (refresh)="detail.refresh()" />
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
                  <div class="label">7-day avg</div>
                  <div class="mid num">{{ fmt(d.trend_kg, 2) }}<span class="unit sm"> kg</span></div>
                </div>
              </div>
              <div class="rate-row">
                <span class="num m" [class]="toneClass(tone())">{{ rateText(d.weekly_rate_kg) }}</span>
                @if (d.band; as b) { <span class="t2 num">goal {{ signed(b.low, 2) }} to {{ signed(b.high, 2) }} kg/wk</span> }
              </div>
            </app-card>

            <app-card>
              <div class="chart-head">
                <select aria-label="Range" [value]="weeks()" (change)="setWeeks($any($event.target).value)">
                  @for (r of ranges; track r.weeks) {
                    <option [value]="r.weeks" [selected]="r.weeks === weeks()">{{ r.label }}</option>
                  }
                </select>
              </div>
              <app-weight-chart [days]="d.series" [tone]="tone()" [label]="'Weight, ' + rangeLabel()" />
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
              </app-card>
            }
          </div>

          <div class="stack">
            <app-section-header title="Weigh-ins" />
            <app-card>
              @if (d.recent.length) {
                <ul class="rows">
                  @for (w of weighIns(); track w.date) {
                    <li [class.outlier]="w.outlier">
                      <span>{{ dayLabel(w.date) }}</span>
                      <span class="num">
                        @if (w.outlier) { <span class="tag">Outlier</span> }
                        <span class="m">{{ fmt(w.kg, 1) }}</span><span class="t2"> kg</span>
                      </span>
                    </li>
                  }
                </ul>
                @if (d.recent.length > shown) {
                  <button type="button" class="more" (click)="allWeighIns.set(!allWeighIns())">
                    {{ allWeighIns() ? 'Show fewer' : 'Show all ' + d.recent.length }}
                  </button>
                }
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
    select { font: inherit; font-size: 13px; font-weight: 500; color: var(--text); background: var(--inset);
             border: 0; border-radius: 8px; padding: 6px 10px; }
    .pred { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
    .more { display: block; width: 100%; margin-top: 12px; padding: 8px 0 0; border-top: 1px solid var(--divider);
            font-size: 13px; font-weight: 500; color: var(--text-2); text-align: center; }
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
  protected readonly weeks = computed(() => {
    const raw = this.params().get('weeks');
    return RANGES.some((r) => r.weeks === raw) ? raw! : DEFAULT_WEEKS;
  });
  protected readonly rangeLabel = computed(() => RANGES.find((r) => r.weeks === this.weeks())!.label.toLowerCase());
  protected readonly tone = computed(() => rateTone(this.detail.data()?.vs_band ?? null));
  protected readonly shown = WEIGH_INS_SHOWN;
  protected readonly allWeighIns = signal(false);
  protected readonly weighIns = computed(() => {
    const all = this.detail.data()?.recent ?? [];
    return this.allWeighIns() ? all : all.slice(0, WEIGH_INS_SHOWN);
  });
  protected readonly weighedToday = computed(() => {
    const d = this.detail.data();
    return !!d?.weigh_in && d.weigh_in.date === d.date;
  });
  constructor() {
    effect(() => {
      const day = this.day.query().day;
      const weeks = this.weeks();
      untracked(() => this.detail.load({ day, weeks: weeks === DEFAULT_WEEKS ? null : weeks }));
    });
  }

  protected setWeeks(weeks: string): void {
    void this.router.navigate([], { relativeTo: this.route, queryParams: { weeks: weeks === DEFAULT_WEEKS ? null : weeks },
      queryParamsHandling: 'merge', replaceUrl: true });
  }
}
