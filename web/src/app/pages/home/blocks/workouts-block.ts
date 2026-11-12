import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { LineChart } from '../../../ui/line-chart';
import { hasStrengthLine, strengthRate, strengthTone } from '../../../ui/strength-trend';
import { toneClass } from '../weight-format';
import { HomeView } from '../home.types';
import { SessionLine } from './session-line';

/**
 * Home's Workouts card: the day's lifting sessions, one line each with their
 * PRs and kcal ("No workout" without one), then the 14-day strength line with
 * its rate in % per week on it (coloured rising / flat / falling). Without a
 * line (no lift trained twice in 4 weeks) the chart and the rate are left
 * out. Taps open Training.
 */
@Component({
  selector: 'app-workouts-block',
  imports: [Card, SessionLine, LineChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (workouts(); as w) {
      <app-card label="Workouts" link="/training">
        <div class="sessions">
          @for (s of w.sessions; track $index) {
            <app-session-line [session]="s" />
          } @empty {
            <div class="none t2">No workout</div>
          }
        </div>
        @if (hasLine()) {
          <div class="trend">
            <div class="rate num m" [class]="toneClass(tone())">{{ rate() }}</div>
            <app-line-chart [points]="points()" [tone]="tone()" [height]="56"
                            startLabel="14 days" [endLabel]="view().is_today ? 'today' : ''"
                            [label]="'Strength, last 14 days, ' + rate()" />
          </div>
        }
      </app-card>
    }
  `,
  styles: `
    .none { padding: 9px 0; }
    .trend { position: relative; margin-top: 12px; padding-top: 22px; }
    .rate { position: absolute; top: 0; right: 0; font-size: 13px; white-space: nowrap; }
    .rate:not(.ok):not(.bad):not(.warn) { color: var(--text-2); }
  `,
})
export class WorkoutsBlock {
  readonly view = input.required<HomeView>();
  readonly dayQuery = input<Record<string, string | null>>({});

  protected readonly toneClass = toneClass;
  protected readonly workouts = computed(() => this.view().training?.workouts ?? null);
  protected readonly points = computed(() => (this.workouts()?.strength_trend.points ?? []).map((p) => p.pct));
  protected readonly hasLine = computed(() => hasStrengthLine(this.workouts()?.strength_trend));
  protected readonly rate = computed(() => strengthRate(this.workouts()?.strength_trend));
  protected readonly tone = computed(() => strengthTone(this.workouts()?.strength_trend));
}
