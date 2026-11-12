import { ChangeDetectionStrategy, Component, effect, untracked } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { viewResource } from '../../api/view-resource';
import { DayNav } from '../../shell/day-nav';
import { injectDay } from '../../shell/day-param';
import { RefreshButton } from '../../shell/refresh-button';
import { StaleLine } from '../../shell/stale-line';
import { Card } from '../../ui/card';
import { dayLabel, fmt } from '../../ui/format';
import { LineChart } from '../../ui/line-chart';
import { SectionHeader } from '../../ui/section-header';
import { State } from '../../ui/state';
import { Tone } from '../../ui/tone';
import { StrengthTrendChart } from '../../ui/strength-trend';
import { LiftStatus, TrainingActivity, TrainingLift, TrainingView } from './training.types';

const STATUS: Record<LiftStatus, { text: string; tone: Tone }> = {
  progressing: { text: 'Progressing', tone: 'ok' },
  same: { text: 'Same', tone: 'muted' },
  declining: { text: 'Declining', tone: 'bad' },
  stall: { text: 'Stall', tone: 'warn' },
  paused: { text: 'Paused', tone: 'muted' },
  new_baseline: { text: 'New baseline', tone: 'muted' },
  not_judged: { text: 'Building', tone: 'muted' },
  not_recent: { text: 'Not recent', tone: 'muted' },
};

const TYPES: Record<TrainingActivity['type'], string> = {
  run: 'Run', wrestling: 'Wrestling', lift: 'Lifting', other: 'Session',
};

/**
 * The Training tab, as of a day: the strength trend, every counting lift
 * alphabetically (status, latest heaviest set, a small chart), the lifts that
 * don't count in a collapsed section, then the recent runs and other sessions.
 */
@Component({
  selector: 'app-training-page',
  imports: [DayNav, RefreshButton, StaleLine, Card, LineChart, SectionHeader, State, StrengthTrendChart,
    NgTemplateOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-day-nav heading="Training" [day]="day.value()" (dayChange)="day.go($event)">
        <app-refresh-button actions [busy]="training.refreshing()" (refresh)="training.refresh()" />
      </app-day-nav>
      <app-stale-line [freshness]="training.data()?.freshness" [refreshError]="training.refreshError()" />
      @if (training.data(); as t) {
        <div class="cols">
          <div class="stack main">
            <app-card label="Strength">
              @if (t.strength_trend.rate_pct_per_week != null) {
                <app-strength-trend [trend]="t.strength_trend" />
              } @else {
                <div class="t2">Not enough sessions in the last {{ t.strength_trend.window_days }} days yet.</div>
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
                        @if (a.status === 'skipped') { <span class="t3 small">Skipped</span> }
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
        <div class="what">
          <div class="m name">{{ l.name }}</div>
          <div class="t2 small num">{{ topSet(l) }}</div>
        </div>
        <div class="spark">
          <app-line-chart [points]="spark(l)" [height]="28" tone="muted" emptyText="" [label]="l.name + ' history'" />
        </div>
        <div class="status small m" [class]="'tone-' + st(l).tone">{{ st(l).text }}</div>
      </li>
    </ng-template>
  `,
  styles: `
    .cols { display: grid; gap: 12px; }
    .list { list-style: none; margin: 0; padding: 0; }
    .list li { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-top: 1px solid var(--divider); }
    .list li:first-child { border-top: 0; padding-top: 0; }
    .list li:last-child { padding-bottom: 0; }
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
    .skipped .name { color: var(--text-3); font-weight: 400; }
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
  protected readonly day = injectDay();
  protected readonly training = viewResource<TrainingView>('training');
  protected readonly fmt = fmt;
  protected readonly dayLabel = dayLabel;
  protected readonly String = String;
  protected st(l: TrainingLift): { text: string; tone: Tone } {
    return STATUS[l.status];
  }
  protected readonly types = TYPES;

  constructor() {
    effect(() => {
      const day = this.day.query().day;
      untracked(() => this.training.load({ day }));
    });
  }

  /** "100 kg × 9"; bodyweight lifts show the effective load ("BW 80 kg × 8"). */
  protected topSet(l: TrainingLift): string {
    const s = l.latest;
    if (!s) return '–';
    const kg = (n: number) => fmt(n, Number.isInteger(n) ? 0 : 1);
    if (l.bodyweight_exercise) {
      const extra = s.load_kg ? `+${kg(s.load_kg)} kg` : 'bodyweight';
      return `${kg(s.effective_load_kg)} kg × ${s.reps} · ${extra}`;
    }
    return `${kg(s.load_kg)} kg × ${s.reps}`;
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
