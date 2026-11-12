import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { Column, ColumnChart } from '../../../ui/column-chart';
import { addDays, dayLabel, fmt, weekday } from '../../../ui/format';
import { WeekView } from '../week.types';

/**
 * Week's steps: the average a day big, the days at the step goal beside it,
 * and a column per day against the goal line (green at the goal; days still
 * to come are empty stubs).
 */
@Component({
  selector: 'app-week-steps-block',
  imports: [Card, ColumnChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (steps(); as s) {
      <app-card label="Steps">
        <div class="top">
          <div>
            <div class="big num">{{ fmt(s.average) }}</div>
            <div class="t2 small">avg a day</div>
          </div>
          <div class="right">
            <div class="mid num">{{ s.days_at_goal }}</div>
            <div class="t2 small">{{ s.days_at_goal === 1 ? 'day' : 'days' }} at goal</div>
          </div>
        </div>
        <app-column-chart class="chart" [columns]="columns()" [line]="s.goal" [lineLabel]="fmt(s.goal)" [height]="72"
                          [startLabel]="startLabel()" [endLabel]="endLabel()" label="Steps per day" />
      </app-card>
    }
  `,
  styles: `
    .top { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
    .right { text-align: right; }
    .chart { display: block; margin-top: 18px; }
  `,
})
export class WeekStepsBlock {
  readonly view = input.required<WeekView>();

  protected readonly fmt = fmt;
  protected readonly steps = computed(() => this.view().training?.steps ?? null);

  /** All 7 days of the week; days still to come are empty stubs. */
  protected readonly columns = computed<Column[]>(() => {
    const s = this.steps();
    const w = this.view();
    if (!s) return [];
    const byDate = new Map(s.days.map((d) => [d.date, d]));
    const out: Column[] = [];
    for (let n = 0; n < 7; n++) {
      const date = addDays(w.start, n);
      const d = byDate.get(date);
      const steps = d && d.tracked ? d.steps : null;
      out.push({
        value: steps,
        tone: steps != null && steps >= s.goal ? 'ok' : 'muted',
        label: `${weekday(date)}: ${steps == null ? (d ? 'not tracked' : 'to come') : fmt(steps) + ' steps'}`,
      });
    }
    return out;
  });
  protected readonly startLabel = computed(() => dayLabel(this.view().start, false));
  protected readonly endLabel = computed(() => dayLabel(this.view().end, false));
}
