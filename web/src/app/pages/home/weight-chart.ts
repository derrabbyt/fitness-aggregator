import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Tone, toneColor } from '../../ui/tone';
import { WeightDay } from './weight.types';

let nextId = 0;

/**
 * The weight detail's chart, hand-written SVG (no library): the band as a
 * shaded corridor, the 7-day trend as one 2px line with a 6 % wash, and each
 * weigh-in as a small dot. Outliers are hollow red rings, clamped to the
 * edge when they are off the scale (they don't stretch it). No grid, no axes.
 */
@Component({
  selector: 'app-weight-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (geometry(); as g) {
      <div class="plot" [style.height.px]="height()">
        <svg [attr.viewBox]="'0 0 ' + W + ' ' + height()" preserveAspectRatio="none" [style.height.px]="height()"
             role="img" [attr.aria-label]="label()">
          <defs>
            <linearGradient [attr.id]="gradientId" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" [attr.stop-color]="color()" stop-opacity=".12" />
              <stop offset="1" [attr.stop-color]="color()" stop-opacity="0" />
            </linearGradient>
          </defs>
          @if (g.band) { <path [attr.d]="g.band" class="band" /> }
          @for (seg of g.segments; track $index) {
            <path [attr.d]="seg.area" [attr.fill]="'url(#' + gradientId + ')'" />
            <path [attr.d]="seg.line" fill="none" [attr.stroke]="color()" stroke-width="2"
                  stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
          }
        </svg>
        @for (p of g.dots; track $index) {
          <i [class.out]="p.outlier" [style.left.%]="p.xPct" [style.top.px]="p.y"></i>
        }
      </div>
    } @else {
      <div class="empty" [style.height.px]="height()">Not enough weigh-ins yet</div>
    }
    <div class="ends"><span>{{ startLabel() }}</span><span>{{ endLabel() }}</span></div>
  `,
  styles: `
    :host { display: block; }
    .plot { position: relative; }
    svg { display: block; width: 100%; overflow: visible; }
    .band { fill: var(--text); opacity: .06; }
    i { position: absolute; width: 5px; height: 5px; margin: -2.5px 0 0 -2.5px; border-radius: 99px;
        background: var(--text-3); pointer-events: none; }
    i.out { width: 8px; height: 8px; margin: -4px 0 0 -4px; background: var(--container);
            box-shadow: inset 0 0 0 1.5px var(--destructive); }
    .empty { display: grid; place-items: center; color: var(--text-2); font-size: 13px; }
    .ends { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-2); margin-top: 4px; }
  `,
})
export class WeightChart {
  readonly days = input.required<readonly WeightDay[]>();
  readonly tone = input<Tone>('muted');
  readonly height = input(208);
  readonly startLabel = input('');
  readonly endLabel = input('');
  readonly label = input('Weight chart');

  protected readonly W = 300;
  protected readonly gradientId = `wc${nextId++}`;
  protected readonly color = computed(() => toneColor(this.tone()));

  protected readonly geometry = computed(() => {
    const days = this.days();
    const n = days.length;
    const trend = days.map((d) => d.trend_kg);
    const scaled: number[] = [];
    for (const d of days) {
      if (d.trend_kg != null) scaled.push(d.trend_kg);
      if (d.kg != null && !d.outlier) scaled.push(d.kg);
      if (d.band_low_kg != null && d.band_high_kg != null) scaled.push(d.band_low_kg, d.band_high_kg);
    }
    if (n < 2 || scaled.length < 2) return null;
    let lo = Math.min(...scaled), hi = Math.max(...scaled);
    if (hi - lo < 0.6) { const mid = (hi + lo) / 2; lo = mid - 0.3; hi = mid + 0.3; }  // keep noise from looking dramatic
    const H = this.height(), pad = 8;
    const x = (i: number) => (i / (n - 1)) * this.W;
    const y = (v: number) => pad + (1 - (Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * (H - 2 * pad);

    const runs: { i: number; v: number }[][] = [];
    let run: { i: number; v: number }[] = [];
    trend.forEach((v, i) => {
      if (v == null) { if (run.length) runs.push(run); run = []; } else run.push({ i, v });
    });
    if (run.length) runs.push(run);
    const segments = runs.filter((r) => r.length > 1).map((r) => {
      const line = r.map((p, k) => `${k ? 'L' : 'M'}${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ');
      const area = `${line} L${x(r[r.length - 1].i).toFixed(1)},${H} L${x(r[0].i).toFixed(1)},${H} Z`;
      return { line, area };
    });

    const banded = days.map((d, i) => ({ d, i })).filter(({ d }) => d.band_low_kg != null && d.band_high_kg != null);
    const band = banded.length > 1
      ? 'M' + banded.map(({ d, i }) => `${x(i).toFixed(1)},${y(d.band_high_kg!).toFixed(1)}`).join(' L')
        + ' L' + [...banded].reverse().map(({ d, i }) => `${x(i).toFixed(1)},${y(d.band_low_kg!).toFixed(1)}`).join(' L')
        + ' Z'
      : null;

    const dots = days.flatMap((d, i) => (d.kg == null ? [] : [{ xPct: (x(i) / this.W) * 100, y: y(d.kg), outlier: d.outlier }]));
    return { segments, band, dots };
  });
}
