import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { dayLabel, parseIso } from '../../ui/format';
import { kg } from './lift-format';
import { LiftChartPoint } from './lift.types';

/**
 * A lift's history: estimated 1RM of each session's heaviest working set,
 * placed by date. One thin line with a light wash, a small dot per session,
 * PRs as green dots and each baseline reset as a dashed vertical line (the
 * line restarts there). The highest and lowest values label the right edge.
 */
@Component({
  selector: 'app-lift-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (geometry(); as g) {
      <div class="plot" [style.height.px]="H">
        <svg [attr.viewBox]="'0 0 ' + W + ' ' + H" preserveAspectRatio="none" role="img" [attr.aria-label]="label()">
          @for (seg of g.segments; track $index) {
            <path [attr.d]="seg.area" class="wash" />
            <path [attr.d]="seg.line" class="line" vector-effect="non-scaling-stroke" />
          }
        </svg>
        @for (r of g.resets; track $index) {
          <span class="reset" [style.left.%]="r"></span>
        }
        @for (p of g.points; track $index) {
          <i [class.pr]="p.pr" [style.left.%]="p.x" [style.top.px]="p.y" [attr.title]="p.title"></i>
        }
        <span class="hi num">{{ g.hi }}</span>
        <span class="lo num">{{ g.lo }}</span>
      </div>
      <div class="ends num"><span>{{ g.start }}</span><span>{{ g.end }}</span></div>
      @if (g.hasPr || g.resets.length) {
        <div class="legend">
          @if (g.hasPr) { <span><i class="pr"></i>PR</span> }
          @if (g.resets.length) { <span><b></b>Baseline reset</span> }
        </div>
      }
    } @else {
      <div class="empty" [style.height.px]="H">{{ points().length ? 'One session so far' : 'No sessions yet' }}</div>
    }
  `,
  styles: `
    :host { display: block; }
    .plot { position: relative; margin-right: 44px; }
    svg { display: block; width: 100%; height: 100%; overflow: visible; }
    .wash { fill: var(--fill); opacity: .06; }
    .line { fill: none; stroke: var(--fill); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
    i { position: absolute; width: 6px; height: 6px; margin: -3px 0 0 -3px; border-radius: 99px; background: var(--fill); }
    i.pr { width: 9px; height: 9px; margin: -4.5px 0 0 -4.5px; background: var(--success);
      box-shadow: 0 0 0 2px var(--container); }
    .reset { position: absolute; top: 0; bottom: 0; width: 0; border-left: 1px dashed var(--text-3); }
    .hi, .lo { position: absolute; right: -44px; width: 40px; text-align: right; font-size: 11px; color: var(--text-3); }
    .hi { top: -2px; }
    .lo { bottom: -2px; }
    .ends { display: flex; justify-content: space-between; margin: 6px 44px 0 0; font-size: 11px; color: var(--text-3); }
    .legend { display: flex; gap: 16px; margin-top: 10px; font-size: 12px; color: var(--text-2); }
    .legend span { display: inline-flex; align-items: center; gap: 6px; }
    .legend i { position: static; margin: 0; box-shadow: none; }
    .legend b { display: inline-block; height: 12px; border-left: 1px dashed var(--text-3); }
    .empty { display: grid; place-items: center; color: var(--text-2); font-size: 13px; }
  `,
})
export class LiftChart {
  readonly points = input.required<readonly LiftChartPoint[]>();
  readonly label = input('Estimated 1RM history');

  protected readonly W = 300;
  protected readonly H = 176;

  protected readonly geometry = computed(() => {
    const pts = this.points();
    if (pts.length < 2) return null;
    const W = this.W, H = this.H, pad = 8;
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
      points: pts.map((p, i) => ({
        x: (x(i) / W) * 100, y: y(values[i]), pr: p.pr,
        title: `${dayLabel(p.date)}: ${kg(p.e1rm_kg)} kg${p.pr ? ' · PR' : ''}`,
      })),
      resets: pts.map((p, i) => (p.baseline_reset ? (x(i) / W) * 100 : null)).filter((v): v is number => v != null),
      hasPr: pts.some((p) => p.pr),
      hi: `${kg(Math.round(hi))} kg`,
      lo: `${kg(Math.round(lo))} kg`,
      start: dayLabel(pts[0].date, false),
      end: dayLabel(pts[pts.length - 1].date, false),
    };
  });
}
