import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { StrengthTrendChart } from '../../../ui/strength-trend';
import { HomeView } from '../home.types';
import { SessionLine } from './session-line';

/**
 * Home's Gym block (ticket 05): the day's lifting sessions, one line each
 * (name, time of day, duration), then the lift trend line in plain words with
 * the 4-week strength trend as one small graph beside it. Taps open Training.
 */
@Component({
  selector: 'app-gym-block',
  imports: [Card, SessionLine, StrengthTrendChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (gym(); as g) {
      <app-card label="Gym" link="/training">
        @for (s of g.sessions; track $index) {
          <app-session-line [session]="s" />
        } @empty {
          <div class="none t2">No gym session {{ view().is_today ? 'yet today' : 'this day' }}</div>
        }
        @if (trendParts().length || g.strength_trend.change_pct != null) {
          <div class="trend">
            <span class="small t2 words">@for (part of trendParts(); track $index) {@if ($index) { · }<span class="part">{{ part }}</span>}</span>
            <app-strength-trend [trend]="g.strength_trend" size="small" />
          </div>
        }
      </app-card>
    }
  `,
  styles: `
    .none { padding: 2px 0 4px; }
    .part { white-space: nowrap; }
    .trend { display: flex; align-items: center; justify-content: space-between; gap: 12px;
      margin-top: 10px; padding-top: 12px; border-top: 1px solid var(--divider); }
  `,
})
export class GymBlock {
  readonly view = input.required<HomeView>();
  readonly dayQuery = input<Record<string, string | null>>({});

  protected readonly gym = computed(() => this.view().training?.gym ?? null);

  /** "5 of 7 lifts progressing · 1 stall · 2 PRs this week"; zeros left out. */
  protected readonly trendParts = computed(() => {
    const t = this.gym()?.trend;
    if (!t) return [];
    const parts: string[] = [];
    if (t.counted) parts.push(`${t.progressing} of ${t.counted} ${t.counted === 1 ? 'lift' : 'lifts'} progressing`);
    if (t.stalls) parts.push(`${t.stalls} ${t.stalls === 1 ? 'stall' : 'stalls'}`);
    if (t.prs) parts.push(`${t.prs} ${t.prs === 1 ? 'PR' : 'PRs'} this week`);
    return parts;
  });
}
