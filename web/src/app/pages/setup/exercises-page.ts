import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CoachApi } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Card } from '../../ui/card';
import { dayLabel } from '../../ui/format';
import { Icon } from '../../ui/icon';
import { State } from '../../ui/state';
import { Switch } from '../../ui/switch';
import { EditState } from './edit-row';
import { ExerciseRow, ExercisesView } from './setup-records.types';

/**
 * Setup › Exercises: every exercise from Hevy (16 weeks) as counting or not
 * counted for weekly progression, with a switch (chat's classify_exercises).
 * Each row opens the lift's detail (Training › lift), where it can also be
 * paused or reset; the same switch sits there.
 */
@Component({
  selector: 'app-exercises-page',
  imports: [PageHeader, Card, State, Switch, Icon, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./setup-forms.css', './setup-records.css'],
  template: `
    <div class="page">
      <app-page-header title="Exercises" back="/setup" />
      @if (view.data(); as v) {
        <div class="stack">
          @if (!v.exercises.length) {
            <app-state kind="empty" message="No exercises synced from Hevy yet." />
          } @else {
            @for (group of groups(); track group.title) {
              <app-card [label]="group.title + ' · ' + group.rows.length">
                @if (!group.rows.length) {
                  <p class="t2 small empty">{{ group.empty }}</p>
                } @else {
                  <div class="colhead label" aria-hidden="true">Counts</div>
                }
                <ul class="rows">
                  @for (e of group.rows; track e.exercise_id) {
                    <li>
                      <div class="row">
                        <a class="lift" [routerLink]="['/training/lift', e.exercise_id]">
                          <span class="txt">
                            <span class="m">{{ e.title }}</span>
                            <span class="t2 small">{{ detail(e) }}</span>
                          </span>
                          <app-icon name="right" class="chev" />
                        </a>
                        <app-switch [on]="e.counts" [label]="'Counts for progression: ' + e.title"
                                    [disabled]="!!edit.busy()" (toggle)="setCounts(e, !e.counts)" />
                      </div>
                      @if (edit.errorFor('class:' + e.exercise_id); as err) { <p class="msg bad small" role="alert">{{ err }}</p> }
                      @if (edit.noticeFor('class:' + e.exercise_id); as ok) { <p class="msg ok small" role="status">{{ ok }}</p> }
                    </li>
                  }
                </ul>
              </app-card>
            }
          }
        </div>
      } @else if (view.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="view.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `
    .colhead { text-align: right; margin: -4px 0 4px; }
    .rows > li:first-child { padding-top: 4px; }
    .row { display: flex; align-items: center; gap: 12px; }
    .lift { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; min-height: 44px;
      margin: -6px 0; padding: 6px 0; border-radius: var(--radius-inner); }
    .txt { flex: 1; min-width: 0; display: grid; gap: 2px; }
    .chev { --icon: 14px; color: var(--text-3); }
    @media (min-width: 900px) { .stack { max-width: 640px; } }
  `,
})
export class ExercisesPage {
  private readonly api = inject(CoachApi);
  protected readonly view = viewResource<ExercisesView>('setup/exercises');
  protected readonly edit = new EditState();

  protected readonly groups = computed(() => {
    const all = this.view.data()?.exercises ?? [];
    return [
      { title: 'Counting', rows: all.filter((e) => e.counts), empty: 'No counting exercises.' },
      { title: 'Not counted', rows: all.filter((e) => !e.counts), empty: 'Every exercise counts.' },
    ];
  });

  constructor() {
    this.view.load();
  }

  protected detail(e: ExerciseRow): string {
    const parts = [`${e.sessions} session${e.sessions === 1 ? '' : 's'}`, `last ${dayLabel(e.last_date, false)}`];
    if (e.paused) parts.push('paused');
    if (!e.classified) parts.push('not classified yet');
    return parts.join(' · ');
  }

  protected setCounts(e: ExerciseRow, counts: boolean): void {
    const body = { exercise_id: e.exercise_id, classification: counts ? 'counts' : 'excluded' };
    this.edit.save(`class:${e.exercise_id}`, this.api.command<ExercisesView>('setup/exercises/classify', body),
      (v) => {
        this.view.data.set(v);
        return counts ? `${e.title} counts now.` : `${e.title} no longer counts.`;
      });
  }
}
