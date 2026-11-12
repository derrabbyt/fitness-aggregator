import { ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, signal, untracked } from '@angular/core';
import { Subscription } from 'rxjs';
import { DayNav } from '../../shell/day-nav';
import { injectDay } from '../../shell/day-param';
import { Card } from '../../ui/card';
import { Column, ColumnChart } from '../../ui/column-chart';
import { dayLabel, hoursMinutes, weekday } from '../../ui/format';
import { SectionHeader } from '../../ui/section-header';
import { State } from '../../ui/state';
import { Night, SleepApi } from './sleep';

const NIGHTS = 14;

/**
 * Sleep detail: the 14 nights ending on the day (fa-api's /api/sleep with
 * start and end, one request), hours asleep and from–to, "–" where there is none.
 * No verdict colours (sleep has no target) and no explanatory notes.
 */
@Component({
  selector: 'app-sleep-detail-page',
  imports: [DayNav, Card, ColumnChart, SectionHeader, State],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-day-nav heading="Sleep" [day]="day.value()" back="/home" [backQuery]="day.query()"
                   (dayChange)="day.go($event)" />
      @if (nights(); as list) {
        <div class="stack">
          <app-card label="14 nights">
            <div class="sum">
              <div>
                <span class="big num">{{ hours(average()) }}</span>
                @if (average() != null) { <span class="t2"> average</span> }
              </div>
              <div class="t2 num small">{{ withData() }} of {{ list.length }} nights</div>
            </div>
            <app-column-chart [columns]="columns()" [height]="112" [startLabel]="startLabel()" [endLabel]="endLabel()"
                              label="Hours asleep per night" />
          </app-card>

          <app-section-header title="Nights" />
          <app-card>
            <ul class="nights">
              @for (r of rows(); track r.date) {
                <li [attr.aria-current]="r.date === day.value() ? 'date' : null">
                  <span class="m">{{ r.name }}</span>
                  @if (r.night; as n) {
                    <span class="num"><span class="m">{{ hours(n.asleep) }}</span><span class="t2 span">{{ n.from }}–{{ n.to }}</span></span>
                  } @else {
                    <span class="t2">–</span>
                  }
                </li>
              }
            </ul>
          </app-card>
        </div>
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `
    .sum { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
    .nights { list-style: none; margin: 0; padding: 0; }
    .nights li { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 10px 0; border-top: 1px solid var(--divider); }
    .nights li:first-child { border-top: 0; padding-top: 0; }
    .nights li:last-child { padding-bottom: 0; }
    .span { display: inline-block; min-width: 96px; text-align: right; }
  `,
})
export class SleepDetailPage {
  protected readonly day = injectDay();
  private readonly sleep = inject(SleepApi);
  protected readonly nights = signal<{ date: string; night: Night | null }[] | null>(null);
  protected readonly hours = hoursMinutes;
  private sub?: Subscription;

  private readonly name = (date: string) => (date === this.day.today ? 'Today' : `${weekday(date)} ${dayLabel(date, false)}`);

  protected readonly withData = computed(() => (this.nights() ?? []).filter((n) => n.night).length);
  protected readonly average = computed(() => {
    const hrs = (this.nights() ?? []).flatMap((n) => (n.night ? [n.night.asleep] : []));
    return hrs.length ? hrs.reduce((a, b) => a + b, 0) / hrs.length : null;
  });
  protected readonly columns = computed<Column[]>(() =>
    (this.nights() ?? []).map((n) => ({
      value: n.night?.asleep ?? null,
      tone: 'muted',
      label: `${this.name(n.date)}: ${n.night ? hoursMinutes(n.night.asleep) : 'no data'}`,
    })),
  );
  protected readonly rows = computed(() => [...(this.nights() ?? [])].reverse().map((n) => ({ ...n, name: this.name(n.date) })));
  protected readonly startLabel = computed(() => {
    const list = this.nights();
    return list?.length ? dayLabel(list[0].date, false) : '';
  });
  protected readonly endLabel = computed(() => (this.day.isToday() ? 'Today' : dayLabel(this.day.value(), false)));

  constructor() {
    inject(DestroyRef).onDestroy(() => this.sub?.unsubscribe());
    effect(() => {
      const date = this.day.value();
      untracked(() => {
        this.sub?.unsubscribe();
        this.nights.set(null);
        this.sub = this.sleep.nights(date, NIGHTS).subscribe((list) => this.nights.set(list));
      });
    });
  }
}
