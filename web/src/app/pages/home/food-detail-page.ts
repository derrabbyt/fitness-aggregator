import { ChangeDetectionStrategy, Component, computed, effect, untracked } from '@angular/core';
import { viewResource } from '../../api/view-resource';
import { DayNav } from '../../shell/day-nav';
import { injectDay } from '../../shell/day-param';
import { RefreshButton } from '../../shell/refresh-button';
import { Card } from '../../ui/card';
import { addDays, dayLabel, fmt, signed, weekday } from '../../ui/format';
import { Meter } from '../../ui/meter';
import { SectionHeader } from '../../ui/section-header';
import { State } from '../../ui/state';
import { FoodDetail } from './home.types';

/** Food detail: the check-in week so far, each day eaten against its daily target (no verdict colours per day). */
@Component({
  selector: 'app-food-detail-page',
  imports: [DayNav, RefreshButton, Card, Meter, SectionHeader, State],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-day-nav heading="Food" [day]="day.value()" back="/home" [backQuery]="day.query()"
                   (dayChange)="day.go($event)">
        <app-refresh-button actions [busy]="detail.refreshing()" [done]="detail.refreshed()" (refresh)="detail.refresh()" />
      </app-day-nav>
      @if (detail.refreshError(); as err) { <p class="warn small m">Sync failed: {{ err }}</p> }
      @if (detail.data(); as d) {
        <div class="stack">
          <app-card [label]="'Week so far · ' + range()">
            <div class="sum">
              <div>
                <span class="big num">{{ fmt(d.so_far.eaten_kcal) }}</span>
                @if (d.so_far.target_kcal != null) { <span class="t2 num"> / {{ fmt(d.so_far.target_kcal) }} kcal</span> }
                @else { <span class="t2"> kcal</span> }
              </div>
              @if (d.so_far.deviation_pct != null) {
                <div class="mid num t2">{{ signed(d.so_far.deviation_pct, 1) }} %</div>
              }
            </div>
            <div class="t2 small">{{ d.so_far.days_logged }} of {{ rows().length }} days logged</div>
          </app-card>

          <app-section-header title="Days" />
          <app-card>
            <ul class="days">
              @for (r of rows(); track r.date) {
                <li [class.later]="r.later" [attr.aria-current]="r.date === d.date ? 'date' : null">
                  <div class="row">
                    <span class="m">{{ r.name }}</span>
                    <span class="num">
                      @if (r.later) { <span class="t2">–</span> }
                      @else {
                        <span class="m">{{ fmt(r.eaten) }}</span>
                        @if (r.target != null) { <span class="t2"> / {{ fmt(r.target) }}</span> }
                      }
                    </span>
                  </div>
                  @if (!r.later) {
                    @if (r.target != null) {
                      <app-meter size="thin" [value]="r.eaten" [max]="r.target" tone="muted"
                                 [label]="r.name + ' eaten of target'" />
                    }
                    @if (r.logged === 'partial') { <div class="note t2 small">Partly logged</div> }
                    @if (r.logged === 'missing' && !r.isDay) { <div class="note t2 small">Nothing logged</div> }
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
    .sum { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px; }
    .days { list-style: none; margin: 0; padding: 0; }
    .days li { padding: 10px 0; border-top: 1px solid var(--divider); }
    .days li:first-child { border-top: 0; padding-top: 0; }
    .days li:last-child { padding-bottom: 0; }
    .row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
    .later .row { margin-bottom: 0; color: var(--text-2); }
    .note { margin-top: 4px; }
    p.warn { margin: -6px 2px 12px; }
  `,
})
export class FoodDetailPage {
  protected readonly day = injectDay();
  protected readonly detail = viewResource<FoodDetail>('home/food');
  protected readonly fmt = fmt;
  protected readonly signed = signed;

  /** The whole check-in week: the days so far from the coach, the rest as faint rows. */
  protected readonly rows = computed(() => {
    const d = this.detail.data();
    if (!d) return [];
    const byDate = new Map(d.days.map((x) => [x.date, x]));
    const out = [];
    for (let date = d.start; date <= d.end; date = addDays(date, 1)) {
      const x = byDate.get(date);
      const name = date === this.day.today ? 'Today' : `${weekday(date)} ${dayLabel(date, false)}`;
      out.push({
        date, name, later: !x, isDay: date === d.date,
        eaten: x?.eaten_kcal ?? null, target: x?.target_kcal ?? null, logged: x?.logged ?? 'missing',
      });
    }
    return out;
  });
  protected readonly range = computed(() => {
    const d = this.detail.data();
    return d ? `${dayLabel(d.start, false)} – ${dayLabel(d.end, false)}` : '';
  });

  constructor() {
    effect(() => {
      const day = this.day.query().day;
      untracked(() => this.detail.load({ day }));
    });
  }
}
