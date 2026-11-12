import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { WeekView } from '../week.types';

/**
 * Week's lifting: the sessions done against the week's plan big, the counted
 * lifts that improved on their best recent session beside it, then PRs and
 * stalls by name (a deload signal in amber). Taps open the Training tab.
 * Steps have their own card (week-steps-block.ts).
 */
@Component({
  selector: 'app-week-training-block',
  imports: [Card],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (training(); as t) {
      <app-card label="Lifting" link="/training">
        <div class="top">
          <div>
            <div class="big num">{{ t.sessions.done }}<span class="of"> of {{ t.sessions.planned }}</span></div>
            <div class="t2 small">sessions{{ t.sessions.skipped ? ' · ' + t.sessions.skipped + ' skipped' : '' }}</div>
          </div>
          @if (t.lifts; as l) {
            <div class="right">
              <div class="mid num">{{ l.progressing }}<span class="of"> of {{ l.counted }}</span></div>
              <div class="t2 small">lifts improved</div>
            </div>
          }
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
  `,
})
export class WeekTrainingBlock {
  readonly view = input.required<WeekView>();

  protected readonly training = computed(() => this.view().training ?? null);
  protected readonly names = (items: { name: string }[]) => [...new Set(items.map((i) => i.name))].join(', ');
}
