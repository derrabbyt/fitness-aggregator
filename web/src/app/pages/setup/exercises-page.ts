import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { CoachApi } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Card } from '../../ui/card';
import { dayLabel } from '../../ui/format';
import { State } from '../../ui/state';
import { EditState } from './edit-row';
import { ExerciseRow, ExercisesView } from './setup-records.types';

/**
 * Setup › Exercises: every exercise from Hevy (16 weeks) as counting or not
 * counted for weekly progression, with a switch (chat's classify_exercises),
 * and pause / resume (chat's set_exercise_paused, with an optional reason).
 */
@Component({
  selector: 'app-exercises-page',
  imports: [PageHeader, Card, State],
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
                  <p class="t3 small empty">{{ group.empty }}</p>
                }
                <ul class="rows">
                  @for (e of group.rows; track e.exercise_id) {
                    <li>
                      <div class="row">
                        <div class="txt">
                          <div class="m">{{ e.title }}</div>
                          <div class="t2 small">{{ detail(e) }}</div>
                          @if (e.paused) {
                            <div class="small warn">Paused{{ e.paused_reason ? ': ' + e.paused_reason : '' }}</div>
                          }
                        </div>
                        <button type="button" class="link small" (click)="togglePause(e)"
                                [disabled]="!!edit.busy()" [attr.aria-label]="(e.paused ? 'Resume ' : 'Pause ') + e.title">
                          {{ e.paused ? 'Resume' : 'Pause' }}
                        </button>
                        <button type="button" role="switch" class="switch" [attr.aria-checked]="e.counts"
                                [attr.aria-label]="'Counts for progression: ' + e.title"
                                [disabled]="!!edit.busy()" (click)="setCounts(e, !e.counts)">
                          <span class="knob"></span>
                        </button>
                      </div>
                      @if (edit.open() === 'pause:' + e.exercise_id) {
                        <form class="editor" (submit)="$event.preventDefault(); pause(e)">
                          <input type="text" maxlength="80" placeholder="Reason (optional), e.g. left knee"
                                 aria-label="Reason for the pause" [value]="reason()" (input)="reason.set(value($event))" />
                          <div class="btns">
                            <button type="button" class="btn" (click)="edit.cancel()" [disabled]="!!edit.busy()">Cancel</button>
                            <button type="submit" class="btn primary" [disabled]="!!edit.busy()">
                              {{ edit.busy() === 'pause:' + e.exercise_id ? 'Saving…' : 'Pause' }}
                            </button>
                          </div>
                        </form>
                      }
                      @for (k of keys(e); track k) {
                        @if (edit.errorFor(k)) { <p class="msg bad small" role="alert">{{ edit.errorFor(k) }}</p> }
                        @if (edit.noticeFor(k)) { <p class="msg ok small" role="status">{{ edit.noticeFor(k) }}</p> }
                      }
                    </li>
                  }
                </ul>
              </app-card>
            }
          }
          <p class="note">Counting exercises decide whether your lifts progressed each week. Not counted ones are
            still logged. A paused exercise isn't judged until you resume it.</p>
        </div>
      } @else if (view.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="view.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `
    .rows > li:first-child { padding-top: 4px; }
    .row { display: flex; align-items: center; gap: 8px; }
    .txt { flex: 1; min-width: 0; display: grid; gap: 2px; }
    .switch { position: relative; flex: none; width: 44px; height: 26px; border-radius: 13px; background: var(--track);
      transition: background-color .15s ease; }
    .switch[aria-checked="true"] { background: var(--fill); }
    .switch .knob { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%;
      background: #fff; box-shadow: 0 1px 2px rgba(0, 0, 0, .2); transition: transform .15s ease; }
    .switch[aria-checked="true"] .knob { transform: translateX(18px); background: var(--container); }
    .switch[disabled] { opacity: .6; }
    .switch:focus-visible { outline: 2px solid var(--info); outline-offset: 2px; }
    .editor { margin-top: 10px; display: grid; gap: 10px; }
    .editor input { width: 100%; }
    @media (min-width: 900px) { .stack { max-width: 640px; } }
  `,
})
export class ExercisesPage {
  private readonly api = inject(CoachApi);
  protected readonly view = viewResource<ExercisesView>('setup/exercises');
  protected readonly edit = new EditState();
  protected readonly reason = signal('');

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

  protected value(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }

  protected keys(e: ExerciseRow): string[] {
    return [`class:${e.exercise_id}`, `pause:${e.exercise_id}`];
  }

  protected detail(e: ExerciseRow): string {
    const parts = [`${e.sessions} session${e.sessions === 1 ? '' : 's'}`, `last ${dayLabel(e.last_date, false)}`];
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

  protected togglePause(e: ExerciseRow): void {
    if (e.paused) {
      this.send(e, false);
    } else {
      this.reason.set('');
      this.edit.start(`pause:${e.exercise_id}`);
    }
  }

  protected pause(e: ExerciseRow): void {
    this.send(e, true);
  }

  private send(e: ExerciseRow, paused: boolean): void {
    const body = { exercise_id: e.exercise_id, paused, reason: paused ? this.reason().trim() || null : null };
    this.edit.save(`pause:${e.exercise_id}`, this.api.command<ExercisesView>('setup/exercises/pause', body), (v) => {
      this.view.data.set(v);
      return paused ? 'Paused.' : 'Resumed.';
    });
  }
}
