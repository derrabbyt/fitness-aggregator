import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../ui/card';
import { dayLabel, fmt, signed } from '../../ui/format';
import { Proposal, WeekDecision } from './week.types';

const STATUS: Record<Proposal['status'], string> = {
  open: 'Waiting in Telegram',
  approved: 'Approved',
  rejected: 'Rejected',
  superseded: 'Replaced',
  blocked_by_guardrail: 'Not possible yet',
};

/**
 * One proposal, read-only: what it changes, why, the new target and MFP goal,
 * and a guardrail's reason when it blocked it. No actions: approve, reject
 * and counter happen in Telegram. Given the week's `decision` (the proposal
 * that decision made), it is the Decision card: the decision as the headline
 * and its reason, so the two never say the same thing twice.
 */
@Component({
  selector: 'app-proposal-card',
  imports: [Card],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @let p = proposal();
    @let d = decision();
    <app-card [label]="label()">
      <div class="head">
        <span [class]="d ? 'big num' : 'mid num'" [class.t2]="!d && p.status !== 'open' && p.status !== 'approved'">{{ headline() }}</span>
        <span class="status small" [class.open]="p.status === 'open'">{{ status() }}</span>
      </div>
      @if (d?.skip; as skip) { <p class="why m">{{ skip.text }}</p> }
      <p class="why t2">{{ d ? d.why : p.reason }}</p>
      @if (p.agent_disagrees) { <p class="why t2">Coach: {{ p.agent_disagrees }}</p> }
      @if (p.user_reason) { <p class="why t2">Your reason: {{ p.user_reason }}</p> }

      <dl>
        @if (p.avg_daily_target_kcal; as t) {
          <div><dt>Average daily target</dt><dd class="num">{{ fmt(t.before) }} → {{ fmt(t.after) }} kcal</dd></div>
        }
        @if (p.status === 'open' && p.mfp_goal_after_kcal != null) {
          <div><dt>MyFitnessPal goal</dt><dd class="num">{{ fmt(p.mfp_goal_after_kcal) }} kcal</dd></div>
        }
        @if (p.applied_on) {
          <div><dt>Applied</dt><dd>{{ day(p.applied_on) }}</dd></div>
        }
      </dl>

      @if (!p.guardrail.passed) {
        <ul class="rails">
          @for (g of p.guardrail.details; track $index) { <li class="small">{{ g.text }}</li> }
        </ul>
      }
      @if (streak()) { <p class="meta t2 small">{{ streak() }}</p> }
    </app-card>
  `,
  styles: `
    .head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
    .status { color: var(--text-2); white-space: nowrap; }
    .status.open { display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 999px;
      background: var(--inset); color: var(--text); }
    .status.open::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--text-2); }
    .why { margin: 8px 0 0; }
    dl { margin: 12px 0 0; display: grid; gap: 0; }
    dl div { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-top: 1px solid var(--divider); }
    dt { color: var(--text-2); }
    dd { margin: 0; font-weight: 500; text-align: right; }
    dl:empty { display: none; }
    .rails { margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }
    .rails li { padding: 8px 10px; border-radius: var(--radius-inner); background: var(--inset); color: var(--text-2); }
    .meta { margin: 12px 0 0; }
  `,
})
export class ProposalCard {
  readonly proposal = input.required<Proposal>();
  /** The week's decision when this is the proposal it made (the merged Decision card). */
  readonly decision = input<WeekDecision | null>(null);
  /** "2 of 2 weeks pointing up", under the merged Decision card. */
  readonly streak = input('');
  protected readonly fmt = fmt;

  protected readonly label = computed(() => {
    const p = this.proposal();
    if (this.decision()) return 'Decision';
    if (p.source === 'user_counter') return 'Your counter';
    if (p.source === 'user_request') return 'Your request';
    return p.type === 'calibration_change' ? 'Calibration' : 'Proposal';
  });
  protected readonly headline = computed(() => {
    const p = this.proposal();
    return p.type === 'calorie_change' && p.delta_kcal != null ? `${signed(p.delta_kcal)} kcal a day` : p.change;
  });
  protected readonly status = computed(() => STATUS[this.proposal().status]);

  protected day(d: string): string {
    return dayLabel(d);
  }
}
