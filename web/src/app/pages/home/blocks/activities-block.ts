import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { HomeView } from '../home.types';
import { SessionLine } from './session-line';

/**
 * Home's Other activities block (ticket 05): runs (distance, duration, pace),
 * wrestling and extra sessions, one line each; no "planned" tag. Shown only
 * when the day has any. Taps open Training.
 */
@Component({
  selector: 'app-activities-block',
  imports: [Card, SessionLine],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (sessions().length) {
      <app-card label="Other activities" link="/training">
        @for (s of sessions(); track $index) {
          <app-session-line [session]="s" />
        }
      </app-card>
    }
  `,
})
export class ActivitiesBlock {
  readonly view = input.required<HomeView>();
  readonly dayQuery = input<Record<string, string | null>>({});

  protected readonly sessions = computed(() => this.view().training?.other.sessions ?? []);
}
