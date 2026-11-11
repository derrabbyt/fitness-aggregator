import { ChangeDetectionStrategy, Component, DestroyRef, effect, inject, input, signal, untracked } from '@angular/core';
import { Subscription } from 'rxjs';
import { Card } from '../../../ui/card';
import { hoursMinutes } from '../../../ui/format';
import { HomeView } from '../home.types';
import { Night, SleepApi } from '../sleep';

/**
 * Home's sleep block: the night ending on the day as hours asleep and
 * from–to ("7 h 36 · 23:10–06:46"), "–" without data. Read from fa-api's
 * /api/sleep, not the coach. No explanatory notes (spec, story 10).
 */
@Component({
  selector: 'app-sleep-block',
  imports: [Card],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-card label="Sleep" link="/home/sleep" [queryParams]="dayQuery()">
      @if (night(); as n) {
        <div class="line"><span class="big num">{{ hours(n.asleep) }}</span><span class="t2 num">· {{ n.from }}–{{ n.to }}</span></div>
      } @else {
        <div class="line"><span class="big t3" [class.pending]="loading()">–</span></div>
      }
    </app-card>
  `,
  styles: `
    .line { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
    .pending { visibility: hidden; }
  `,
})
export class SleepBlock {
  readonly view = input.required<HomeView>();
  readonly dayQuery = input<Record<string, string | null>>({});

  private readonly sleep = inject(SleepApi);
  protected readonly night = signal<Night | null>(null);
  protected readonly loading = signal(true);
  protected readonly hours = hoursMinutes;
  private sub?: Subscription;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.sub?.unsubscribe());
    effect(() => {
      const date = this.view().date;
      untracked(() => this.load(date));
    });
  }

  private load(date: string): void {
    // A new view (another day, or the same day after a refresh) reloads; the same day keeps its night meanwhile.
    this.sub?.unsubscribe();
    if (this.night()?.date !== date) {
      this.night.set(null);
      this.loading.set(true);
    }
    this.sub = this.sleep.night(date).subscribe((n) => {
      this.night.set(n);
      this.loading.set(false);
    });
  }
}
