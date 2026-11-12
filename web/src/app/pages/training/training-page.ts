import { ChangeDetectionStrategy, Component, computed } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { RouterLink } from '@angular/router';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { RefreshButton } from '../../shell/refresh-button';
import { StaleLine } from '../../shell/stale-line';
import { Card } from '../../ui/card';
import { dayLabel, fmt } from '../../ui/format';
import { LineChart } from '../../ui/line-chart';
import { SectionHeader } from '../../ui/section-header';
import { State } from '../../ui/state';
import { Tone } from '../../ui/tone';
import { StrengthTrendChart, hasStrengthLine, strengthEmptyText } from '../../ui/strength-trend';
import { LIFT_STATUS, setText } from './lift-format';
import { LiftStatus, TrainingActivity, TrainingLift, TrainingView } from './training.types';

/** The status counts at the top, in this order; a count of 0 is left out. New covers building a baseline too. */
const COUNTS: { label: string; tone: Tone; statuses: LiftStatus[] }[] = [
  { label: 'Progressing', tone: 'ok', statuses: ['progressing'] },
  { label: 'Same', tone: 'muted', statuses: ['same'] },
  { label: 'Stalled', tone: 'warn', statuses: ['stall'] },
  { label: 'Declining', tone: 'bad', statuses: ['declining'] },
  { label: 'New', tone: 'muted', statuses: ['new_baseline', 'not_judged'] },
  { label: 'Not recent', tone: 'muted', statuses: ['not_recent'] },
  { label: 'Paused', tone: 'muted', statuses: ['paused'] },
];

const TYPES: Record<TrainingActivity['type'], string> = {
  run: 'Run', wrestling: 'Wrestling', lift: 'Lifting', other: 'Session',
};

/**
 * The Training tab, always as of today (lift charts carry the history): the
 * counting lifts per status and the strength trend, every counting lift
 * alphabetically (status, latest heaviest set, a small chart), the lifts that
 * don't count in a collapsed section, then the recent runs and other sessions.
 */
@Component({
  selector: 'app-training-page',
  imports: [PageHeader, RefreshButton, StaleLine, Card, LineChart, SectionHeader, State, StrengthTrendChart,
    NgTemplateOutlet, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-page-header title="Training">
        <app-refresh-button actions [busy]="training.refreshing()" [done]="training.refreshed()" (refresh)="training.refresh()" />
      </app-page-header>
      <app-stale-line [freshness]="training.data()?.freshness" [refreshError]="training.refreshError()" />
      @if (training.data(); as t) {
        <div class="cols">
          <div class="stack main">
            <app-card label="Strength">
              @if (counts().length) {
                <div class="counts">
                  @for (c of counts(); track c.label) {
                    <div><div class="mid num" [class]="'tone-' + c.tone">{{ c.n }}</div><div class="t2 small">{{ c.label }}</div></div>
                  }
                </div>
              }
              @if (hasStrengthLine(t.strength_trend)) {
                <app-strength-trend [trend]="t.strength_trend" />
              } @else {
                <div class="t2">{{ strengthEmptyText(t.strength_trend) }}</div>
              }
            </app-card>

            <app-section-header title="Lifts" [aside]="t.lifts.length ? String(t.lifts.length) : ''" />
            @if (t.lifts.length) {
              <app-card>
                <ul class="list">
                  @for (l of t.lifts; track l.exercise_id) {
                    <ng-container *ngTemplateOutlet="liftRow; context: { $implicit: l }" />
                  }
                </ul>
              </app-card>
            } @else {
              <app-state kind="empty" message="No lifts logged in Hevy yet." />
            }

            @if (t.not_counted.length) {
              <details class="more">
                <summary>
                  <span class="label">Not counted</span>
                  <span class="aside num t2 small">{{ t.not_counted.length }}</span>
                </summary>
                <app-card>
                  <ul class="list">
                    @for (l of t.not_counted; track l.exercise_id) {
                      <ng-container *ngTemplateOutlet="liftRow; context: { $implicit: l }" />
                    }
                  </ul>
                </app-card>
              </details>
            }
          </div>

          <div class="stack side">
            <app-section-header title="Runs & other" />
            @if (t.activities.length) {
              <app-card>
                <ul class="list">
                  @for (a of t.activities; track $index) {
                    <li class="act" [class.skipped]="a.status === 'skipped'">
                      <div class="when t2 small num">{{ dayLabel(a.date) }}</div>
                      <div class="what">
                        <div class="m name">{{ a.name || types[a.type] }}</div>
                        <div class="t2 small num">{{ details(a) }}</div>
                      </div>
                      <div class="kcal num">
                        @if (a.status === 'skipped') { <span class="t2 small">Skipped</span> }
                        @else if (a.kcal_counted != null) { <span class="m">{{ fmt(a.kcal_counted) }}</span><span class="t2 small"> kcal</span> }
                      </div>
                    </li>
                  }
                </ul>
              </app-card>
            } @else {
              <app-state kind="empty" message="No runs or other sessions in the last 4 weeks." />
            }
          </div>
        </div>
      } @else if (training.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="training.load()" />
      } @else {
        <app-state kind="loading" [blocks]="3" />
      }
    </div>

    <ng-template #liftRow let-l>
      <li class="lift">
        <a class="row" [routerLink]="['lift', l.exercise_id]">
        <div class="what">
          <div class="m name">{{ l.name }}</div>
          <div class="t2 small num">{{ topSet(l) }}</div>
        </div>
        <div class="spark">
          <app-line-chart [points]="spark(l)" [height]="28" tone="muted" emptyText="" [label]="l.name + ' history'" />
        </div>
        <div class="status small m" [class]="'tone-' + st(l).tone">{{ st(l).text }}</div>
        </a>
      </li>
    </ng-template>
  `,
  styles: `
    .cols { display: grid; gap: 12px; }
    .counts { display: flex; flex-wrap: wrap; gap: 12px 24px; margin-bottom: 16px; }
    .counts .tone-muted { color: var(--text); }
    .list { list-style: none; margin: 0; padding: 0; }
    .list li { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-top: 1px solid var(--divider); }
    .list li:first-child { border-top: 0; padding-top: 0; }
    .list li:last-child { padding-bottom: 0; }
    .list li.lift { display: block; }
    .row { display: flex; align-items: center; gap: 12px; color: inherit; text-decoration: none; border-radius: var(--radius-inner); }
    .row:hover .name { text-decoration: underline; text-underline-offset: 3px; }
    .row:focus-visible { outline: 2px solid var(--info); outline-offset: 4px; }
    .what { flex: 1; min-width: 0; }
    .name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .spark { width: 64px; flex: none; }
    .status { width: 92px; flex: none; text-align: right; white-space: nowrap; }
    .tone-ok { color: var(--success); }
    .tone-bad { color: var(--destructive); }
    .tone-warn { color: var(--warning); }
    .tone-muted, .tone-neutral { color: var(--text-2); }
    .when { width: 76px; flex: none; }
    .kcal { flex: none; text-align: right; white-space: nowrap; }
    .skipped .name { color: var(--text-2); font-weight: 400; }
    .more summary {
      display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
      padding: 12px 4px 4px; cursor: pointer; list-style: none;
    }
    .more summary::-webkit-details-marker { display: none; }
    .more summary .label::after { content: '›'; display: inline-block; margin-left: 6px; transition: transform .12s ease; }
    .more[open] summary .label::after { transform: rotate(90deg); }
    .more[open] summary { margin-bottom: 12px; }
    @media (min-width: 900px) {
      .cols { grid-template-columns: 3fr 2fr; gap: 16px; align-items: start; }
    }
  `,
})
export class TrainingPage {
  protected readonly training = viewResource<TrainingView>('training');
  protected readonly fmt = fmt;
  protected readonly dayLabel = dayLabel;
  protected readonly String = String;
  protected readonly strengthEmptyText = strengthEmptyText;
  protected readonly hasStrengthLine = hasStrengthLine;
  protected st(l: TrainingLift): { text: string; tone: Tone } {
    return LIFT_STATUS[l.status];
  }
  protected readonly types = TYPES;
  /** Counting lifts per status (the not-counted ones are left out), zeros dropped. */
  protected readonly counts = computed(() => {
    const lifts = this.training.data()?.lifts ?? [];
    return COUNTS.map((c) => ({ ...c, n: lifts.filter((l) => c.statuses.includes(l.status)).length }))
      .filter((c) => c.n > 0);
  });

  constructor() {
    this.training.load({});
  }

  protected topSet(l: TrainingLift): string {
    return setText(l.latest, l.bodyweight_exercise);
  }

  protected spark(l: TrainingLift): number[] {
    return l.series.map((p) => p.e1rm_kg);
  }

  /** "11.5 km · 62 min", "90 min", or the type when there is nothing else. */
  protected details(a: TrainingActivity): string {
    const parts: string[] = [];
    if (a.name && a.name.toLowerCase() !== TYPES[a.type].toLowerCase()) parts.push(TYPES[a.type]);
    if (a.distance_km != null) parts.push(`${fmt(a.distance_km, 1)} km`);
    if (a.minutes != null) parts.push(`${fmt(a.minutes)} min`);
    return parts.join(' · ');
  }
}
