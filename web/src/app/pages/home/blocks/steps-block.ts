import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { fmt, signed } from '../../../ui/format';
import { Meter } from '../../../ui/meter';
import { HomeView } from '../home.types';

/**
 * Home's steps block (as in the ticket 01 prototype): steps big against the
 * goal, the step kcal so far on the right (green when it adds), one bar
 * (green once the goal is reached), then the steps to go. A day under the
 * not-tracked limit says "Not tracked" with an empty bar, never a deficit.
 */
@Component({
  selector: 'app-steps-block',
  imports: [Card, Meter],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (steps(); as s) {
      <app-card label="Steps" link="/home/steps" [queryParams]="dayQuery()">
        @if (s.tracked) {
          <div class="top">
            <div><span class="big num">{{ fmt(s.steps) }}</span><span class="t2 num"> / {{ fmt(s.goal) }}</span></div>
            @if (s.kcal != null) {
              <div class="num m" [class.ok]="s.kcal > 0" [class.t2]="s.kcal <= 0">{{ signed(s.kcal) }} kcal</div>
            }
          </div>
          <app-meter [value]="s.steps" [max]="s.goal" [tone]="reached() ? 'ok' : 'neutral'" label="Steps of goal" />
          <div class="foot">
            @if (reached()) { <span class="ok m">Goal reached</span> }
            @else { <span class="t2 num">{{ fmt(s.to_go) }} to go</span> }
          </div>
        } @else {
          <div class="top"><div class="mid t2">Not tracked</div></div>
          <app-meter [value]="0" [max]="s.goal" label="Steps not tracked" />
          <div class="foot t3 num">Goal {{ fmt(s.goal) }}</div>
        }
      </app-card>
    }
  `,
  styles: `
    .top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 10px; min-height: 36px; }
    .top .mid { align-self: flex-end; }
    .foot { margin-top: 8px; font-size: 13px; }
  `,
})
export class StepsBlock {
  readonly view = input.required<HomeView>();
  readonly dayQuery = input<Record<string, string | null>>({});

  protected readonly fmt = fmt;
  protected readonly signed = signed;
  protected readonly steps = computed(() => this.view().steps ?? null);
  protected readonly reached = computed(() => this.steps()?.to_go === 0);
}
