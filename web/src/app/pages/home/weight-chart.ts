import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { dayLabel, fmt } from '../../ui/format';
import { Tone, toneColor } from '../../ui/tone';
import { WeightDay } from './weight.types';

let nextId = 0;

/** Tick steps in kg, smallest first; the first giving at most 4 intervals wins. */
const STEPS = [0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10];

/**
 * The weight chart, hand-written SVG (no library): the 7-day average as one
 * continuous 2px line (days without one are bridged, flat and dashed to the
 * edges before the first and after the last), each weigh-in a small
 * dot, outliers hollow red rings clamped to the edge, the goal band as a
 * faint corridor. A kg axis on the left with faint grid lines, the dates
 * under it, and hover or touch shows the day's values.
 */
@Component({
  selector: 'app-weight-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (geometry(); as g) {
      <div class="chart">
        <div class="y" [style.height.px]="height()">
          @for (t of g.ticks; track t.v) { <span class="num" [style.top.px]="t.y">{{ t.label }}</span> }
        </div>
        <div class="plot" [style.height.px]="height()" (pointermove)="point($event, g.n)" (pointerdown)="point($event, g.n)"
             (pointerleave)="hover.set(null)">
          <svg [attr.viewBox]="'0 0 ' + W + ' ' + height()" preserveAspectRatio="none" [style.height.px]="height()"
               role="img" [attr.aria-label]="label()">
            <defs>
              <linearGradient [attr.id]="gradientId" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" [attr.stop-color]="color()" stop-opacity=".12" />
                <stop offset="1" [attr.stop-color]="color()" stop-opacity="0" />
              </linearGradient>
            </defs>
            @for (t of g.ticks; track t.v) {
              <line x1="0" [attr.x2]="W" [attr.y1]="t.y" [attr.y2]="t.y" class="grid" vector-effect="non-scaling-stroke" />
            }
            @if (g.band) { <path [attr.d]="g.band" class="band" /> }
            @if (g.line) {
              <path [attr.d]="g.area" [attr.fill]="'url(#' + gradientId + ')'" />
              <path [attr.d]="g.line" fill="none" [attr.stroke]="color()" stroke-width="2"
                    stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
            }
            @if (g.ends) {
              <path [attr.d]="g.ends" fill="none" [attr.stroke]="color()" stroke-width="1.5" stroke-dasharray="3 4"
                    opacity=".5" vector-effect="non-scaling-stroke" />
            }
          </svg>
          @for (p of g.dots; track $index) {
            <i [class.out]="p.outlier" [style.left.%]="p.xPct" [style.top.px]="p.y"></i>
          }
          @if (active(); as a) {
            <div class="guide" [style.left.%]="a.xPct"></div>
            @if (a.trendY != null) { <b class="hit" [style.left.%]="a.xPct" [style.top.px]="a.trendY" [style.background]="color()"></b> }
            <div class="tip" [class.flip]="a.xPct > 60" [style.left.%]="a.xPct">
              <div class="t2">{{ a.date }}</div>
              @if (a.kg != null) { <div class="num">{{ a.kg }} kg{{ a.outlier ? ' · outlier' : '' }}</div> }
              @if (a.trend != null) { <div class="num t2">avg {{ a.trend }} kg</div> }
            </div>
          }
        </div>
        <div></div>
        <div class="x"><span>{{ g.x[0] }}</span><span>{{ g.x[1] }}</span><span>{{ g.x[2] }}</span></div>
      </div>
    } @else {
      <div class="empty" [style.height.px]="height()">Not enough weigh-ins yet</div>
    }
  `,
  styles: `
    :host { display: block; }
    .chart { display: grid; grid-template-columns: auto minmax(0, 1fr); column-gap: 8px; }
    .y { position: relative; min-width: 28px; }
    .y span { position: absolute; right: 0; transform: translateY(-50%); font-size: 11px; color: var(--text-2); white-space: nowrap; }
    .plot { position: relative; touch-action: pan-y; cursor: crosshair; }
    svg { display: block; width: 100%; overflow: visible; }
    .grid { stroke: var(--divider); stroke-width: 1; }
    .band { fill: var(--text); opacity: .06; }
    i { position: absolute; width: 5px; height: 5px; margin: -2.5px 0 0 -2.5px; border-radius: 99px;
        background: var(--text-3); pointer-events: none; }
    i.out { width: 8px; height: 8px; margin: -4px 0 0 -4px; background: var(--container);
            box-shadow: inset 0 0 0 1.5px var(--destructive); }
    .guide { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--text-3); pointer-events: none; }
    .hit { position: absolute; width: 8px; height: 8px; margin: -4px 0 0 -4px; border-radius: 99px;
           box-shadow: 0 0 0 2px var(--container); pointer-events: none; }
    .tip { position: absolute; top: 0; transform: translateX(8px); background: var(--container); box-shadow: var(--ring);
           border-radius: 8px; padding: 6px 8px; font-size: 12px; line-height: 1.4; white-space: nowrap; pointer-events: none; }
    .tip.flip { transform: translateX(calc(-100% - 8px)); }
    .x { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-2); margin-top: 6px; }
    .empty { display: grid; place-items: center; color: var(--text-2); font-size: 13px; }
  `,
})
export class WeightChart {
  readonly days = input.required<readonly WeightDay[]>();
  readonly tone = input<Tone>('muted');
  readonly height = input(208);
  readonly label = input('Weight chart');

  protected readonly W = 300;
  protected readonly gradientId = `wc${nextId++}`;
  protected readonly color = computed(() => toneColor(this.tone()));
  protected readonly hover = signal<number | null>(null);

  protected readonly geometry = computed(() => {
    const days = this.days();
    const n = days.length;
    const scaled: number[] = [];
    for (const d of days) {
      if (d.trend_kg != null) scaled.push(d.trend_kg);
      if (d.kg != null && !d.outlier) scaled.push(d.kg);
      if (d.band_low_kg != null && d.band_high_kg != null) scaled.push(d.band_low_kg, d.band_high_kg);
    }
    if (n < 2 || scaled.length < 2) return null;
    let lo = Math.min(...scaled), hi = Math.max(...scaled);
    if (hi - lo < 0.6) { const mid = (hi + lo) / 2; lo = mid - 0.3; hi = mid + 0.3; }  // keep noise from looking dramatic
    const step = STEPS.find((s) => (Math.ceil(hi / s) - Math.floor(lo / s)) <= 4) ?? 20;
    lo = Math.floor(lo / step) * step;
    hi = Math.ceil(hi / step) * step;
    const H = this.height(), pad = 6;
    const x = (i: number) => (i / (n - 1)) * this.W;
    const y = (v: number) => pad + (1 - (Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * (H - 2 * pad);
    const decimals = step >= 1 ? 0 : step === 0.25 ? 2 : 1;

    const ticks = [];
    for (let v = lo; v <= hi + step / 2; v += step) {
      ticks.push({ v, y: y(v), label: fmt(v, decimals) });
    }

    // The 7-day average, bridged over days without one.
    const pts = days.map((d, i) => ({ i, v: d.trend_kg })).filter((p): p is { i: number; v: number } => p.v != null);
    const line = pts.length > 1 ? pts.map((p, k) => `${k ? 'L' : 'M'}${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ') : null;
    const area = line ? `${line} L${x(pts[pts.length - 1].i).toFixed(1)},${H} L${x(pts[0].i).toFixed(1)},${H} Z` : null;
    const first = pts[0], last = pts[pts.length - 1];
    const ends = !line ? null : [
      first.i > 0 ? `M0,${y(first.v).toFixed(1)} L${x(first.i).toFixed(1)},${y(first.v).toFixed(1)}` : '',
      last.i < n - 1 ? `M${x(last.i).toFixed(1)},${y(last.v).toFixed(1)} L${this.W},${y(last.v).toFixed(1)}` : '',
    ].join(' ').trim() || null;

    const banded = days.map((d, i) => ({ d, i })).filter(({ d }) => d.band_low_kg != null && d.band_high_kg != null);
    const band = banded.length > 1
      ? 'M' + banded.map(({ d, i }) => `${x(i).toFixed(1)},${y(d.band_high_kg!).toFixed(1)}`).join(' L')
        + ' L' + [...banded].reverse().map(({ d, i }) => `${x(i).toFixed(1)},${y(d.band_low_kg!).toFixed(1)}`).join(' L')
        + ' Z'
      : null;

    const dots = days.flatMap((d, i) => (d.kg == null ? [] : [{ xPct: (x(i) / this.W) * 100, y: y(d.kg), outlier: d.outlier }]));
    const xLabels = [days[0], days[Math.floor((n - 1) / 2)], days[n - 1]].map((d) => dayLabel(d.date, false));
    return { n, ticks, line, area, ends, band, dots, x: xLabels, y };
  });

  /** The hovered day's values, bridged average included. */
  protected readonly active = computed(() => {
    const i = this.hover();
    const g = this.geometry();
    if (i == null || !g) return null;
    const d = this.days()[i];
    return {
      xPct: (i / (g.n - 1)) * 100,
      date: dayLabel(d.date),
      kg: d.kg == null ? null : fmt(d.kg, 1),
      outlier: d.outlier,
      trend: d.trend_kg == null ? null : fmt(d.trend_kg, 1),
      trendY: d.trend_kg == null ? null : g.y(d.trend_kg),
    };
  });

  protected point(event: PointerEvent, n: number): void {
    const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const f = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
    this.hover.set(Math.round(f * (n - 1)));
  }
}
