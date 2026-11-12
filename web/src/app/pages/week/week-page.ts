import { ChangeDetectionStrategy, Component, computed, effect, inject, untracked } from '@angular/core';
import { NgComponentOutlet } from '@angular/common';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { RefreshButton } from '../../shell/refresh-button';
import { StaleLine } from '../../shell/stale-line';
import { Card } from '../../ui/card';
import { dayLabel, signed } from '../../ui/format';
import { Icon } from '../../ui/icon';
import { State } from '../../ui/state';
import { ProposalCard } from './proposal-card';
import { WEEK_BLOCKS } from './week-blocks';
import { WeekView } from './week.types';

const ISO_WEEK = /^\d{4}-W\d{2}$/;

/**
 * Week: the check-in week (the 7 days the coach judges), the week in progress
 * by default, `?week=YYYY-Www` for older ones. The decision first, then the
 * proposals (read-only), the number blocks (WEEK_BLOCKS) and the report,
 * collapsed at the bottom.
 */
@Component({
  selector: 'app-week-page',
  imports: [PageHeader, RefreshButton, StaleLine, State, Card, Icon, ProposalCard, NgComponentOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-page-header [title]="title()" [sub]="sub()">
        <button prev type="button" class="iconbtn" aria-label="Previous week"
                [disabled]="!week.data()?.prev_week" (click)="go(week.data()?.prev_week)">
          <app-icon name="left" />
        </button>
        <button next type="button" class="iconbtn" aria-label="Next week"
                [disabled]="!week.data()?.next_week" (click)="go(week.data()?.next_week)">
          <app-icon name="right" />
        </button>
        <app-refresh-button actions [busy]="week.refreshing()" [done]="week.refreshed()" (refresh)="week.refresh()" />
      </app-page-header>
      <app-stale-line [freshness]="week.data()?.freshness" [refreshError]="week.refreshError()" />

      @if (week.data(); as w) {
        <main class="grid">
          @switch (w.state) {
            @case ('decided') {
              @let d = w.decision!;
              @if (decisionProposal(); as dp) {
                <app-proposal-card [proposal]="dp" [decision]="d" [streak]="streak()" />
              } @else {
              <app-card label="Decision">
                <div class="big">{{ headline() }}</div>
                @if (d.skip) { <p class="line m">{{ d.skip.text }}</p> }
                <p class="line t2">{{ d.why }}</p>
                @if (streak(); as s) { <p class="meta t2 small">{{ s }}</p> }
              </app-card>
              }
            }
            @case ('in_progress') {
              @let s = w.so_far!;
              <app-card label="So far">
                <div class="big num">Day {{ s.days }} <span class="t2 of">of 7</span></div>
                <p class="line t2 num">{{ s.weigh_ins }} {{ s.weigh_ins === 1 ? 'weigh-in' : 'weigh-ins' }}
                  · food logged on {{ s.food_days_logged }} {{ s.food_days_logged === 1 ? 'day' : 'days' }}</p>
                @if (checkin(); as c) { <p class="meta t2 small">Check-in {{ c }}</p> }
              </app-card>
            }
            @default {
              <app-card label="Decision">
                <p class="line note">{{ w.note }}</p>
              </app-card>
            }
          }

          @for (p of otherProposals(); track p.id) {
            <app-proposal-card [proposal]="p" />
          }

          @for (block of blocks; track $index) {
            <ng-container *ngComponentOutlet="block; inputs: { view: w }" />
          }

          @if (w.report) {
            <details class="report">
              <summary><span class="label">Weekly report</span><app-icon name="right" class="chev" /></summary>
              <div class="text">{{ w.report }}</div>
            </details>
          }
        </main>
      } @else if (week.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="week.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `
    .line { margin: 8px 0 0; }
    .line.note { margin: 0; }
    .meta { margin: 12px 0 0; }
    .of { font-size: 18px; font-weight: 400; letter-spacing: 0; }
    .report { grid-column: 1 / -1; background: var(--container); border-radius: var(--radius); box-shadow: var(--ring); }
    .report summary { display: flex; align-items: center; justify-content: space-between; padding: 16px;
      cursor: pointer; list-style: none; }
    .report summary::-webkit-details-marker { display: none; }
    .chev { --icon: 16px; color: var(--text-3); transition: transform .15s ease; }
    .report[open] .chev { transform: rotate(90deg); }
    .text { padding: 0 16px 16px; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text-2); }
    @media (min-width: 900px) {
      .report summary { padding: 20px; }
      .text { padding: 0 20px 20px; }
    }
  `,
})
export class WeekPage {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly params = toSignal(this.route.queryParamMap, { initialValue: this.route.snapshot.queryParamMap });
  /** `?week=` or null for the week in progress. */
  protected readonly param = computed(() => {
    const raw = this.params().get('week');
    return raw && ISO_WEEK.test(raw) ? raw : null;
  });
  protected readonly week = viewResource<WeekView>('week');
  protected readonly blocks = WEEK_BLOCKS;

  /** Tab name as the title, the week's range (and phase week) underneath, as on every tab. */
  protected readonly title = computed(() => 'Week');
  protected readonly sub = computed(() => {
    const w = this.week.data();
    if (!w) return '';
    const parts = [this.range(w)];
    if (w.phase_week != null && w.phase_week > 0) parts.push(`Phase week ${w.phase_week}`);
    return parts.join(' · ');
  });
  /** The proposal the week's decision made: shown as the Decision card, not twice. */
  protected readonly decisionProposal = computed(() => {
    const w = this.week.data();
    if (!w || w.state !== 'decided' || w.decision?.outcome !== 'change') return null;
    return w.proposals.find((p) => p.source === 'weekly_decision' && p.type === 'calorie_change'
      && p.based_on_week === w.iso_week) ?? null;
  });
  protected readonly otherProposals = computed(() => {
    const merged = this.decisionProposal();
    return (this.week.data()?.proposals ?? []).filter((p) => p !== merged);
  });
  protected readonly headline = computed(() => {
    const d = this.week.data()?.decision;
    if (!d) return '';
    return d.outcome === 'change' && d.change_kcal != null ? `${signed(d.change_kcal)} kcal a day` : 'Hold';
  });
  /** "1 of 2 weeks pointing up": only for a counted week whose data points somewhere. */
  protected readonly streak = computed(() => {
    const d = this.week.data()?.decision;
    if (!d || d.skip || d.direction === 'hold') return '';
    const way = d.direction === 'increase' ? 'up' : 'down';
    const c = d.confirmation;
    return `${c.weeks} of ${c.required} ${c.required === 1 ? 'week' : 'weeks'} pointing ${way}`;
  });
  protected readonly checkin = computed(() => {
    const at = this.week.data()?.checkin_at;
    if (!at) return '';
    const day = at.slice(0, 10);
    return `${dayLabel(day)}, ${at.slice(11, 16)}`;
  });

  constructor() {
    effect(() => {
      const week = this.param();
      untracked(() => this.week.load({ week }));
    });
  }

  protected go(week: string | null | undefined): void {
    if (!week) return;
    void this.router.navigate([], { relativeTo: this.route, queryParams: { week }, replaceUrl: true });
  }

  private range(w: WeekView): string {
    return `${dayLabel(w.start, false)} – ${dayLabel(w.end, false)}`;
  }
}
