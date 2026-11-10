import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Tone, toneColor } from './tone';

/** A shaded horizontal range behind the line, in data units (e.g. a target band). */
export interface ChartBand {
  low: number;
  high: number;
}

let nextId = 0;

/**
 * A thin line chart drawn as SVG, no library: one 2px line with a 6 % wash
 * under it, no grid, no axes. `points` are evenly spaced; null leaves a gap.
 * Fewer than two values show a calm empty state at the same height.
 *
 *   <app-line-chart [points]="series" tone="ok" [height]="56" startLabel="14 days" endLabel="today" />
 *   <app-line-chart [points]="series" [band]="{ low: 81.9, high: 82.4 }" [height]="208" [dots]="true" />
 */
@Component({
  selector: 'app-line-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (geometry(); as g) {
      <svg [attr.viewBox]="'0 0 ' + W + ' ' + height()" preserveAspectRatio="none" [style.height.px]="height()"
           role="img" [attr.aria-label]="label() || null">
        <defs>
          <linearGradient [attr.id]="gradientId" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" [attr.stop-color]="color()" stop-opacity=".12" />
            <stop offset="1" [attr.stop-color]="color()" stop-opacity="0" />
          </linearGradient>
        </defs>
        @if (g.band; as b) {
          <rect x="0" [attr.y]="b.y" [attr.width]="W" [attr.height]="b.h" class="band" />
        }
        @for (seg of g.segments; track $index) {
          <path [attr.d]="seg.area" [attr.fill]="'url(#' + gradientId + ')'" />
          <path [attr.d]="seg.line" fill="none" [attr.stroke]="color()" stroke-width="2"
                stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
        }
      </svg>
      @if (dots()) {
        <div class="dots" [style.height.px]="height()">
          @for (p of g.points; track $index) {
            <i [style.left.%]="p.xPct" [style.top.px]="p.y" [style.background]="color()"></i>
          }
        </div>
      }
    } @else {
      <div class="empty" [style.height.px]="height()">{{ emptyText() }}</div>
    }
    @if (startLabel() || endLabel()) {
      <div class="ends"><span>{{ startLabel() }}</span><span>{{ endLabel() }}</span></div>
    }
  `,
  styles: `
    :host { display: block; position: relative; }
    svg { display: block; width: 100%; overflow: visible; }
    .band { fill: var(--text); opacity: .05; }
    .dots { position: absolute; inset: 0 0 auto 0; pointer-events: none; }
    .dots i { position: absolute; width: 6px; height: 6px; margin: -3px 0 0 -3px; border-radius: 99px; }
    .empty { display: grid; place-items: center; color: var(--text-2); font-size: 13px; }
    .ends { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-3); margin-top: 2px; }
  `,
})
export class LineChart {
  readonly points = input.required<readonly (number | null)[]>();
  readonly tone = input<Tone>('muted');
  readonly height = input(56);
  readonly band = input<ChartBand | null>(null);
  readonly dots = input(false);
  readonly startLabel = input('');
  readonly endLabel = input('');
  readonly label = input('');
  readonly emptyText = input('Not enough data yet');

  protected readonly W = 300;
  protected readonly gradientId = `lc${nextId++}`;
  protected readonly color = computed(() => toneColor(this.tone()));

  protected readonly geometry = computed(() => {
    const pts = this.points();
    const values = pts.filter((v): v is number => v != null);
    if (values.length < 2) return null;
    const band = this.band();
    let lo = Math.min(...values), hi = Math.max(...values);
    if (band) { lo = Math.min(lo, band.low); hi = Math.max(hi, band.high); }
    const H = this.height(), pad = 4, n = pts.length;
    const x = (i: number) => (n === 1 ? this.W / 2 : (i / (n - 1)) * this.W);
    const y = (v: number) => pad + (hi === lo ? 0.5 : 1 - (v - lo) / (hi - lo)) * (H - 2 * pad);

    // Split at gaps: each run of values is its own line.
    const runs: { i: number; v: number }[][] = [];
    let run: { i: number; v: number }[] = [];
    pts.forEach((v, i) => {
      if (v == null) { if (run.length) runs.push(run); run = []; } else run.push({ i, v });
    });
    if (run.length) runs.push(run);

    const segments = runs.filter((r) => r.length > 1).map((r) => {
      const line = r.map((p, k) => `${k ? 'L' : 'M'}${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ');
      const area = `${line} L${x(r[r.length - 1].i).toFixed(1)},${H} L${x(r[0].i).toFixed(1)},${H} Z`;
      return { line, area };
    });
    return {
      segments,
      points: runs.flat().map((p) => ({ xPct: (x(p.i) / this.W) * 100, y: y(p.v) })),
      band: band ? { y: y(band.high), h: Math.max(1, y(band.low) - y(band.high)) } : null,
    };
  });
}
