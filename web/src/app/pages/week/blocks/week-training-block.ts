import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { Column, ColumnChart } from '../../../ui/column-chart';
import { addDays, dayLabel, fmt, weekday } from '../../../ui/format';
import { WeekView } from '../week.types';

/**
 * Week's training: lifts progressing of those judged big (a stall or a
 * deload signal in amber), the stalls and PRs by name, the sessions done
 * against the week's plan, and the steps per day against the step goal
 * (green at the goal). Taps open the Training tab.
 */
@Component({
  selector: 'app-week-training-block',
  imports: [Card, ColumnChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (training(); as t) {
      <app-card label="Training" link="/training">
        <div class="top">
          <div>
            @if (t.lifts; as l) {
              <div class="big num">{{ l.progressing }}<span class="of"> of {{ l.counted }}</span></div>
              <div class="t2 small">lifts progressing</div>
            } @else {
              <div class="big num t3">–</div>
              <div class="t2 small">no lifts judged</div>
            }
          </div>
          <div class="right">
            <div class="mid num">{{ t.sessions.done }}<span class="of"> of {{ t.sessions.planned }}</span></div>
            <div class="t2 small">sessions{{ t.sessions.skipped ? ' · ' + t.sessions.skipped + ' skipped' : '' }}</div>
          </div>
        </div>

        @if (t.lifts; as l) {
          @if (l.stalls.length || l.prs.length || l.deload_signal) {
            <dl class="lifts small">
              @if (l.prs.length) {
                <div><dt class="t2">{{ l.prs.length === 1 ? 'PR' : l.prs.length + ' PRs' }}</dt><dd>{{ names(l.prs) }}</dd></div>
              }
              @if (l.stalls.length) {
                <div><dt class="warn">{{ l.stalls.length === 1 ? 'Stall' : l.stalls.length + ' stalls' }}</dt><dd>{{ names(l.stalls) }}</dd></div>
              }
              @if (l.deload_signal) {
                <div><dt class="warn">Deload</dt><dd>several lifts declining</dd></div>
              }
            </dl>
          }
        }

        <div class="steps">
          <div class="row small">
            <span class="label">Steps</span>
            <span class="t2 num">
              @if (t.steps.average != null) { avg {{ fmt(t.steps.average) }} · }
              {{ t.steps.days_at_goal }} {{ t.steps.days_at_goal === 1 ? 'day' : 'days' }} at goal
            </span>
          </div>
          <app-column-chart [columns]="columns()" [line]="t.steps.goal" [lineLabel]="fmt(t.steps.goal)" [height]="72"
                            [startLabel]="startLabel()" [endLabel]="endLabel()" label="Steps per day" />
        </div>
      </app-card>
    }
  `,
  styles: `
    .top { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
    .right { text-align: right; }
    .of { font-size: 15px; font-weight: 400; letter-spacing: 0; color: var(--text-2); }
    .lifts { margin: 14px 0 0; display: grid; gap: 4px; }
    .lifts div { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 8px; }
    .lifts dt { font-weight: 500; }
    .lifts dd { margin: 0; }
    .steps { margin-top: 18px; }
    .row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; gap: 12px; }
  `,
})
export class WeekTrainingBlock {
  readonly view = input.required<WeekView>();

  protected readonly fmt = fmt;
  protected readonly training = computed(() => this.view().training ?? null);
  protected readonly names = (items: { name: string }[]) => [...new Set(items.map((i) => i.name))].join(', ');

  /** All 7 days of the week; days still to come are empty stubs. */
  protected readonly columns = computed<Column[]>(() => {
    const t = this.training();
    const w = this.view();
    if (!t) return [];
    const byDate = new Map(t.steps.days.map((d) => [d.date, d]));
    const out: Column[] = [];
    for (let n = 0; n < 7; n++) {
      const date = addDays(w.start, n);
      const d = byDate.get(date);
      const steps = d && d.tracked ? d.steps : null;
      out.push({
        value: steps,
        tone: steps != null && steps >= t.steps.goal ? 'ok' : 'muted',
        label: `${weekday(date)}: ${steps == null ? (d ? 'not tracked' : 'to come') : fmt(steps) + ' steps'}`,
      });
    }
    return out;
  });
  protected readonly startLabel = computed(() => dayLabel(this.view().start, false));
  protected readonly endLabel = computed(() => dayLabel(this.view().end, false));
}
