import { ChangeDetectionStrategy, Component, computed, effect, untracked } from '@angular/core';
import { viewResource } from '../../api/view-resource';
import { DayNav } from '../../shell/day-nav';
import { injectDay } from '../../shell/day-param';
import { RefreshButton } from '../../shell/refresh-button';
import { Card } from '../../ui/card';
import { Column, ColumnChart } from '../../ui/column-chart';
import { dayLabel, fmt, signed, weekday } from '../../ui/format';
import { SectionHeader } from '../../ui/section-header';
import { State } from '../../ui/state';
import { StepsDetail } from './home.types';

/** Steps detail: the 14 days ending on the day against the step goal, newest first in the list. */
@Component({
  selector: 'app-steps-detail-page',
  imports: [DayNav, RefreshButton, Card, ColumnChart, SectionHeader, State],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-day-nav heading="Steps" [day]="day.value()" back="/home" [backQuery]="day.query()"
                   (dayChange)="day.go($event)">
        <app-refresh-button actions [busy]="detail.refreshing()" (refresh)="detail.refresh()" />
      </app-day-nav>
      @if (detail.refreshError(); as err) { <p class="warn small m">Sync failed: {{ err }}</p> }
      @if (detail.data(); as d) {
        <div class="stack">
          <app-card label="14 days">
            <div class="sum">
              <div>
                <span class="big num">{{ fmt(d.average_steps) }}</span>
                <span class="t2"> average</span>
              </div>
              <div class="t2 num small">{{ d.days_at_goal }} of {{ d.days_tracked }} days at goal</div>
            </div>
            <app-column-chart [columns]="columns()" [line]="d.goal" [lineLabel]="fmt(d.goal)" [height]="128"
                              [startLabel]="startLabel()" [endLabel]="endLabel()" label="Steps per day against the goal" />
          </app-card>

          <app-section-header title="Days" [aside]="'Goal ' + fmt(d.goal)" />
          <app-card>
            <ul class="days">
              @for (r of rows(); track r.date) {
                <li [attr.aria-current]="r.date === d.date ? 'date' : null">
                  <span class="m">{{ r.name }}</span>
                  @if (r.tracked) {
                    <span class="num">
                      <span class="m" [class.ok]="r.atGoal">{{ fmt(r.steps) }}</span>
                      @if (r.kcal != null) { <span class="t2 kcal">{{ signed(r.kcal) }} kcal</span> }
                    </span>
                  } @else {
                    <span class="t2">Not tracked</span>
                  }
                </li>
              }
            </ul>
          </app-card>
        </div>
      } @else if (detail.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="detail.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `
    .sum { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
    .days { list-style: none; margin: 0; padding: 0; }
    .days li { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 10px 0; border-top: 1px solid var(--divider); }
    .days li:first-child { border-top: 0; padding-top: 0; }
    .days li:last-child { padding-bottom: 0; }
    .kcal { display: inline-block; min-width: 76px; text-align: right; }
    p.warn { margin: -6px 2px 12px; }
  `,
})
export class StepsDetailPage {
  protected readonly day = injectDay();
  protected readonly detail = viewResource<StepsDetail>('home/steps');
  protected readonly fmt = fmt;
  protected readonly signed = signed;

  private readonly name = (date: string) => (date === this.day.today ? 'Today' : `${weekday(date)} ${dayLabel(date, false)}`);

  protected readonly columns = computed<Column[]>(() => {
    const d = this.detail.data();
    if (!d) return [];
    return d.days.map((x) => ({
      value: x.tracked ? x.steps : null,
      tone: x.tracked && x.steps! >= d.goal ? 'ok' : 'muted',
      label: `${this.name(x.date)}: ${x.tracked ? fmt(x.steps) + ' steps' : 'not tracked'}`,
    }));
  });
  protected readonly rows = computed(() => {
    const d = this.detail.data();
    if (!d) return [];
    return [...d.days].reverse().map((x) => ({
      ...x, name: this.name(x.date), atGoal: x.tracked && x.steps! >= d.goal,
    }));
  });
  protected readonly startLabel = computed(() => {
    const d = this.detail.data();
    return d?.days.length ? dayLabel(d.days[0].date, false) : '';
  });
  protected readonly endLabel = computed(() => {
    const d = this.detail.data();
    return d ? (d.date === this.day.today ? 'Today' : dayLabel(d.date, false)) : '';
  });

  constructor() {
    effect(() => {
      const day = this.day.query().day;
      untracked(() => this.detail.load({ day }));
    });
  }
}
