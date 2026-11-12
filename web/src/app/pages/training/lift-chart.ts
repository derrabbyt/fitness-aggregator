import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { dayLabel, parseIso } from '../../ui/format';
import { Tone, toneColor } from '../../ui/tone';
import { kg } from './lift-format';
import { LiftChartPoint } from './lift.types';

let nextId = 0;

/**
 * A lift's history: estimated 1RM of each session's heaviest working set,
 * placed by date. The app's chart grammar (ui/line-chart): one 2px line in
 * the lift's verdict tone with a light wash, no axis, no legend. PRs are
 * small dots in the line colour; each baseline reset is a dashed vertical
 * line where the line restarts. First and last session dates sit underneath.
 */
@Component({
  selector: 'app-lift-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (geometry(); as g) {
      <div class="plot" [style.height.px]="H">
        <svg [attr.viewBox]="'0 0 ' + W + ' ' + H" preserveAspectRatio="none" role="img" [attr.aria-label]="label()">
          <defs>
            <linearGradient [attr.id]="gradientId" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" [attr.stop-color]="color()" stop-opacity=".12" />
              <stop offset="1" [attr.stop-color]="color()" stop-opacity="0" />
            </linearGradient>
          </defs>
          @for (seg of g.segments; track $index) {
            <path [attr.d]="seg.area" [attr.fill]="'url(#' + gradientId + ')'" />
            <path [attr.d]="seg.line" fill="none" [attr.stroke]="color()" stroke-width="2"
                  stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
          }
        </svg>
        @for (r of g.resets; track $index) {
          <span class="reset" [style.left.%]="r"></span>
        }
        @for (p of g.prs; track $index) {
          <i [style.left.%]="p.x" [style.top.px]="p.y" [style.background]="color()" [attr.title]="p.title"></i>
        }
      </div>
      <div class="ends num"><span>{{ g.start }}</span><span>{{ g.end }}</span></div>
    } @else {
      <div class="empty" [style.height.px]="H">{{ points().length ? 'One session so far' : 'No sessions yet' }}</div>
    }
  `,
  styles: `
    :host { display: block; }
    .plot { position: relative; }
    svg { display: block; width: 100%; height: 100%; overflow: visible; }
    i { position: absolute; width: 6px; height: 6px; margin: -3px 0 0 -3px; border-radius: 99px; }
    .reset { position: absolute; top: 0; bottom: 0; width: 0; border-left: 1px dashed var(--text-3); }
    .ends { display: flex; justify-content: space-between; margin-top: 6px; font-size: 11px; color: var(--text-2); }
    .empty { display: grid; place-items: center; color: var(--text-2); font-size: 13px; }
  `,
})
export class LiftChart {
  readonly points = input.required<readonly LiftChartPoint[]>();
  readonly tone = input<Tone>('muted');
  readonly label = input('Estimated 1RM history');

  protected readonly W = 300;
  protected readonly H = 160;
  protected readonly gradientId = `lift${nextId++}`;
  protected readonly color = computed(() => toneColor(this.tone()));

  protected readonly geometry = computed(() => {
    const pts = this.points();
    if (pts.length < 2) return null;
    const W = this.W, H = this.H, pad = 6;
    const t = pts.map((p) => parseIso(p.date).getTime());
    const t0 = t[0], span = t[t.length - 1] - t0 || 1;
    const values = pts.map((p) => p.e1rm_kg);
    const lo = Math.min(...values), hi = Math.max(...values);
    const x = (i: number) => ((t[i] - t0) / span) * W;
    const y = (v: number) => pad + (hi === lo ? 0.5 : 1 - (v - lo) / (hi - lo)) * (H - 2 * pad);

    // A reset starts a new history: the line breaks before it.
    const runs: number[][] = [];
    pts.forEach((p, i) => {
      if (i === 0 || p.baseline_reset) runs.push([]);
      runs[runs.length - 1].push(i);
    });
    const segments = runs.filter((r) => r.length > 1).map((r) => {
      const line = r.map((i, k) => `${k ? 'L' : 'M'}${x(i).toFixed(1)},${y(values[i]).toFixed(1)}`).join(' ');
      const area = `${line} L${x(r[r.length - 1]).toFixed(1)},${H} L${x(r[0]).toFixed(1)},${H} Z`;
      return { line, area };
    });
    return {
      segments,
      prs: pts.flatMap((p, i) => (p.pr ? [{
        x: (x(i) / W) * 100, y: y(values[i]), title: `${dayLabel(p.date)}: ${kg(p.e1rm_kg)} kg · PR`,
      }] : [])),
      resets: pts.map((p, i) => (p.baseline_reset ? (x(i) / W) * 100 : null)).filter((v): v is number => v != null),
      start: dayLabel(pts[0].date, false),
      end: dayLabel(pts[pts.length - 1].date, false),
    };
  });
}
