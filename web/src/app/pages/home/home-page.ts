import { ChangeDetectionStrategy, Component, effect, untracked } from '@angular/core';
import { NgComponentOutlet } from '@angular/common';
import { viewResource } from '../../api/view-resource';
import { DayNav } from '../../shell/day-nav';
import { injectDay } from '../../shell/day-param';
import { RefreshButton } from '../../shell/refresh-button';
import { StaleLine } from '../../shell/stale-line';
import { State } from '../../ui/state';
import { HomeBannerComponent } from './home-banner';
import { HOME_BLOCKS } from './home-blocks';
import { HomeView } from './home.types';

/**
 * Home: one day (today by default, `?day=` for past days), every value as it
 * stood that day. Blocks come from HOME_BLOCKS; above them sit the stale line
 * and (ticket 05) the banner.
 */
@Component({
  selector: 'app-home-page',
  imports: [DayNav, RefreshButton, StaleLine, State, NgComponentOutlet, HomeBannerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-day-nav [day]="day.value()" (dayChange)="day.go($event)">
        <app-refresh-button actions [busy]="home.refreshing()" (refresh)="home.refresh()" />
      </app-day-nav>
      <app-stale-line [freshness]="home.data()?.freshness" [refreshError]="home.refreshError()" />
      @if (home.data(); as view) {
        <app-home-banner [view]="view" />
        <main class="grid">
          @for (block of blocks; track $index) {
            <ng-container *ngComponentOutlet="block; inputs: { view, dayQuery: day.query() }" />
          }
        </main>
      } @else if (home.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="home.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
})
export class HomePage {
  protected readonly day = injectDay();
  protected readonly home = viewResource<HomeView>('home');
  protected readonly blocks = HOME_BLOCKS;

  constructor() {
    effect(() => {
      const day = this.day.query().day;
      untracked(() => this.home.load({ day }));
    });
  }
}
