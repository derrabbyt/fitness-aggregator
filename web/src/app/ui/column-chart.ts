import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Tone, toneColor } from './tone';

/** One column: null (no data) shows a faint stub. */
export interface Column {
  value: number | null;
  tone?: Tone;
  /** Read by screen readers, e.g. "Tue 10 Nov: 9,120 steps". */
  label: string;
}

/**
 * Thin columns for a short daily series (14 days of steps, 14 nights of
 * sleep), no axes: rounded tops, an optional dashed reference line (a goal),
 * start and end labels underneath.
 *
 *   <app-column-chart [columns]="cols" [line]="10000" [height]="120" startLabel="Fri 30 Oct" endLabel="Today" />
 */
@Component({
  selector: 'app-column-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="plot" [style.height.px]="height()" role="list" [attr.aria-label]="label() || null">
      @if (linePct(); as y) {
        <div class="ref" [style.bottom.%]="y" aria-hidden="true">
          @if (lineLabel()) { <span>{{ lineLabel() }}</span> }
        </div>
      }
      @for (c of bars(); track $index) {
        <div class="col" role="listitem" [attr.aria-label]="c.label">
          @if (c.pct == null) { <i class="stub"></i> }
          @else { <i [style.height.%]="c.pct" [style.background]="c.color"></i> }
        </div>
      }
    </div>
    @if (startLabel() || endLabel()) {
      <div class="ends"><span>{{ startLabel() }}</span><span>{{ endLabel() }}</span></div>
    }
  `,
  styles: `
    :host { display: block; }
    .plot { position: relative; display: flex; align-items: flex-end; gap: 4px; }
    .col { flex: 1 1 0; height: 100%; display: flex; align-items: flex-end; min-width: 0; }
    .col i { display: block; width: 100%; min-height: 2px; border-radius: 3px 3px 1px 1px; transition: height .4s ease; }
    .col i.stub { height: 2px; background: var(--track); }
    .ref { position: absolute; left: 0; right: 0; border-top: 1px dashed var(--text-3); opacity: .7; pointer-events: none; z-index: 1; }
    .ref span { position: absolute; right: 0; bottom: 2px; font-size: var(--type-caption); color: var(--text-2); background: var(--container); padding-left: 4px; }
    .ends { display: flex; justify-content: space-between; margin-top: 6px; font-size: var(--type-caption); color: var(--text-2); }
  `,
})
export class ColumnChart {
  readonly columns = input.required<Column[]>();
  /** A reference value drawn as a dashed line (e.g. the step goal). */
  readonly line = input<number | null>(null);
  readonly lineLabel = input('');
  readonly height = input(120);
  readonly startLabel = input('');
  readonly endLabel = input('');
  readonly label = input('');

  /** The top of the scale: the largest value or the line, with a little headroom. */
  private readonly top = computed(() => {
    const values = this.columns().map((c) => c.value ?? 0);
    return Math.max(...values, this.line() ?? 0, 1) * 1.08;
  });
  protected readonly linePct = computed(() => {
    const l = this.line();
    return l == null ? null : (l / this.top()) * 100;
  });
  protected readonly bars = computed(() =>
    this.columns().map((c) => ({
      label: c.label,
      pct: c.value == null ? null : Math.max(0, (c.value / this.top()) * 100),
      color: toneColor(c.tone ?? 'muted'),
    })),
  );
}
