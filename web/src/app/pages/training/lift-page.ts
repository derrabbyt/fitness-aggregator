import { ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, signal, untracked } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { map, Subscription } from 'rxjs';
import { CoachApi, errorMessage } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { injectDay } from '../../shell/day-param';
import { PageHeader } from '../../shell/page-header';
import { RefreshButton } from '../../shell/refresh-button';
import { StaleLine } from '../../shell/stale-line';
import { Card } from '../../ui/card';
import { dayLabel } from '../../ui/format';
import { State } from '../../ui/state';
import { EditRow, EditState } from '../setup/edit-row';
import { LiftChart } from './lift-chart';
import { LIFT_STATUS, NOT_JUDGED, RESET_REASONS, kg, setText } from './lift-format';
import { LiftSession, LiftView } from './lift.types';

const MORE = 10; // sessions per "show more"

/**
 * Training › a lift, as of the day: its estimated-1RM history (PRs and
 * baseline resets marked; bodyweight lifts on bodyweight + added weight),
 * the last 3 sessions with "show more", and its controls. Each control runs
 * the chat tool behind it (Setup › Exercises' `setup/exercises/classify` and
 * `setup/exercises/pause`, and `lift/reset`) and shows the coach's
 * confirmation or reason inline.
 */
@Component({
  selector: 'app-lift-page',
  imports: [PageHeader, RefreshButton, StaleLine, Card, State, EditRow, LiftChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../setup/setup-forms.css',
  template: `
    <div class="page">
      <app-page-header [title]="lift.data()?.name ?? 'Lift'" [sub]="sub()" back="/training" [backQuery]="day.query()">
        <app-refresh-button actions [busy]="lift.refreshing()" (refresh)="lift.refresh()" />
      </app-page-header>
      <app-stale-line [freshness]="lift.data()?.freshness" [refreshError]="lift.refreshError()" />
      @if (lift.data(); as v) {
        <div class="cols">
          <div class="stack">
            <app-card label="Estimated 1RM">
              <div class="head">
                <div>
                  <span class="big num">{{ v.latest ? kg(v.latest.e1rm_kg) : '–' }}</span>
                  @if (v.latest) { <span class="t2"> kg</span> }
                  <div class="t2 small num">{{ v.latest ? 'Heaviest set ' + setText(v.latest, v.bodyweight_exercise) : 'No working set yet' }}</div>
                </div>
                <span class="status m small" [class]="'tone-' + status(v).tone">{{ status(v).text }}</span>
              </div>
              <app-lift-chart [points]="v.chart" [label]="v.name + ' estimated 1RM history'" />
              @if (v.bodyweight_exercise) { <p class="foot t2 small">On bodyweight plus added weight.</p> }
            </app-card>

            <app-card label="Sessions">
              <ul class="sessions">
                @for (s of sessions(); track s.session_id) {
                  <li>
                    <span class="when t2 small num">{{ dayLabel(s.date) }}</span>
                    <span class="set num">{{ setText(s.top_set, v.bodyweight_exercise) }}
                      @if (s.pr) { <span class="pr small m">PR</span> }
                    </span>
                    <span class="st small" [class]="'tone-' + sessionTone(s)">{{ sessionText(s) }}</span>
                  </li>
                } @empty {
                  <li class="t2">No sessions yet.</li>
                }
              </ul>
              @if (next() != null) {
                <button type="button" class="more" (click)="showMore(v)" [disabled]="moreBusy()">
                  {{ moreBusy() ? 'Loading…' : 'Show more' }}
                </button>
              }
              @if (moreError()) { <p class="msg bad small" role="alert">{{ moreError() }}</p> }
            </app-card>
          </div>

          <div class="stack">
            <app-card label="Controls">
              <app-edit-row label="Counts for progress" hint="Whether it decides the weekly progress check."
                            [value]="v.counts ? 'Counts' : 'Not counted'" [editable]="true" editLabel="Change"
                            [editing]="edit.open() === 'counts'" [busy]="edit.busy() === 'counts'"
                            [error]="edit.errorFor('counts')" [notice]="edit.noticeFor('counts')"
                            (edit)="edit.start('counts')" (cancel)="edit.cancel()" (save)="saveCounts(v)"
                            [saveLabel]="v.counts ? 'Don’t count it' : 'Count it'">
                <span class="t2">{{ v.counts ? 'It will sit under Not counted and get no stall flags.' : 'It will decide the weekly progress check again.' }}</span>
              </app-edit-row>

              <app-edit-row label="Paused"
                            [hint]="v.paused && v.controls.paused_reason ? 'Reason: ' + v.controls.paused_reason + '.' : 'A paused lift is logged but not judged.'"
                            [value]="v.paused ? 'Paused' : 'No'"
                            [editable]="true" [editLabel]="v.paused ? 'Unpause' : 'Pause'"
                            [editing]="edit.open() === 'pause'" [busy]="edit.busy() === 'pause'"
                            [error]="edit.errorFor('pause')" [notice]="edit.noticeFor('pause')"
                            (edit)="startPause()" (cancel)="edit.cancel()" (save)="savePause(v)"
                            [saveLabel]="v.paused ? 'Unpause' : 'Pause'">
                @if (v.paused) {
                  <span class="t2">Judge it again from the next session.</span>
                } @else {
                  <input type="text" class="wide" aria-label="Reason for the pause" placeholder="Reason, e.g. left shoulder"
                         maxlength="80" [value]="pauseReason()" (input)="pauseReason.set(text($event))" />
                }
              </app-edit-row>

              <app-edit-row label="Baseline reset" [hint]="resetHint(v)"
                            [value]="resetWhen(v)" [editable]="true" editLabel="Mark reset"
                            [editing]="edit.open() === 'reset'" [busy]="edit.busy() === 'reset'"
                            [error]="edit.errorFor('reset')" [notice]="edit.noticeFor('reset')"
                            (edit)="startReset(v)" (cancel)="edit.cancel()" (save)="saveReset(v)" saveLabel="Mark reset">
                <select aria-label="Reason for the reset" (change)="resetReason.set(text($event))">
                  @for (r of v.controls.reset_reasons; track r) {
                    <option [value]="r" [selected]="r === resetReason()">{{ reasonText(r) }}</option>
                  }
                </select>
                <span class="t2">The next session starts a new history; older ones are no longer compared.</span>
              </app-edit-row>
            </app-card>
          </div>
        </div>
      } @else if (lift.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="lift.load()" />
      } @else {
        <app-state kind="loading" [blocks]="3" />
      }
    </div>
  `,
  styles: `
    .cols { display: grid; gap: 12px; }
    .head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
    .big { font-size: 28px; line-height: 32px; font-weight: 500; }
    .status { white-space: nowrap; padding-top: 6px; }
    .tone-ok { color: var(--success); }
    .tone-bad { color: var(--destructive); }
    .tone-warn { color: var(--warning); }
    .tone-muted, .tone-neutral { color: var(--text-2); }
    .foot { margin: 10px 0 0; }
    .sessions { list-style: none; margin: 0; padding: 0; }
    .sessions li { display: flex; align-items: baseline; gap: 12px; padding: 10px 0; border-top: 1px solid var(--divider); }
    .sessions li:first-child { border-top: 0; padding-top: 0; }
    .when { width: 84px; flex: none; }
    .set { flex: 1; min-width: 0; }
    .pr { margin-left: 6px; color: var(--success); }
    .st { flex: none; text-align: right; white-space: nowrap; }
    .more { margin-top: 8px; width: 100%; height: 40px; border-radius: var(--radius-inner); background: var(--inset);
      color: var(--text); font-weight: 500; }
    .more[disabled] { opacity: .5; }
    .msg { margin: 8px 0 0; }
    .bad { color: var(--destructive); }
    input.wide { width: 100%; flex: 1; }
    select { max-width: 100%; }
    @media (pointer: coarse) { .more { height: 44px; } }
    @media (min-width: 900px) {
      .cols { grid-template-columns: 3fr 2fr; gap: 16px; align-items: start; }
    }
  `,
})
export class LiftPage {
  private readonly api = inject(CoachApi);
  protected readonly day = injectDay();
  private readonly id = toSignal(inject(ActivatedRoute).paramMap.pipe(map((p) => p.get('id') ?? '')), {
    initialValue: '',
  });
  protected readonly lift = viewResource<LiftView>('lift');
  protected readonly edit = new EditState();
  protected readonly pauseReason = signal('');
  protected readonly resetReason = signal('technique_change');

  /** Pages loaded with "show more", appended to the view's first page. */
  private readonly extra = signal<LiftSession[]>([]);
  private readonly extraNext = signal<number | null | undefined>(undefined);
  protected readonly moreBusy = signal(false);
  protected readonly moreError = signal('');
  private moreSub?: Subscription;

  protected readonly sessions = computed(() => [...(this.lift.data()?.sessions.items ?? []), ...this.extra()]);
  protected readonly next = computed(() => {
    const more = this.extraNext();
    return more !== undefined ? more : this.lift.data()?.sessions.next_offset ?? null;
  });
  protected readonly sub = computed(() => {
    const v = this.lift.data();
    if (!v) return '';
    return [v.counts ? '' : 'Not counted', this.day.isToday() ? '' : 'As of ' + dayLabel(v.date)].filter(Boolean).join(' · ');
  });

  protected readonly kg = kg;
  protected readonly setText = setText;
  protected readonly dayLabel = dayLabel;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.moreSub?.unsubscribe());
    effect(() => {
      const query = { exercise_id: this.id(), ...this.day.query() };
      untracked(() => this.reload(query));
    });
  }

  private reload(query?: Record<string, string | null>): void {
    this.moreSub?.unsubscribe();
    this.moreBusy.set(false);
    this.moreError.set('');
    this.extra.set([]);
    this.extraNext.set(undefined);
    this.lift.load(query);
  }

  protected showMore(v: LiftView): void {
    const offset = this.next();
    if (offset == null || this.moreBusy()) return;
    this.moreBusy.set(true);
    this.moreError.set('');
    this.moreSub = this.api.view<LiftView>('lift', {
      exercise_id: v.exercise_id, ...this.day.query(), offset: String(offset), limit: String(MORE),
    }).subscribe({
      next: (page) => {
        this.extra.update((items) => [...items, ...page.sessions.items]);
        this.extraNext.set(page.sessions.next_offset);
        this.moreBusy.set(false);
      },
      error: (err: unknown) => {
        this.moreError.set(errorMessage(err));
        this.moreBusy.set(false);
      },
    });
  }

  protected status(v: LiftView) {
    return LIFT_STATUS[v.status];
  }

  protected sessionText(s: LiftSession): string {
    if (s.status === 'not_judged' && s.not_judged_reason) return NOT_JUDGED[s.not_judged_reason] ?? 'Not judged';
    return LIFT_STATUS[s.status].text;
  }

  protected sessionTone(s: LiftSession): string {
    return LIFT_STATUS[s.status].tone;
  }

  protected reasonText(r: string | null): string {
    return r ? RESET_REASONS[r] ?? r : 'Reset';
  }

  /** The latest reset's session ("9 Oct", "Next session") or "None". */
  protected resetWhen(v: LiftView): string {
    const last = v.resets[v.resets.length - 1];
    if (!last) return 'None';
    return last.session_date ? dayLabel(last.session_date, false) : 'Next session';
  }

  protected resetHint(v: LiftView): string {
    const last = v.resets[v.resets.length - 1];
    return last ? `Last: ${this.reasonText(last.reason).toLowerCase()}.`
      : 'After a technique change or swap, the next session starts a new history.';
  }

  protected text(e: Event): string {
    return (e.target as HTMLInputElement | HTMLSelectElement).value;
  }

  protected startPause(): void {
    this.pauseReason.set('');
    this.edit.start('pause');
  }

  protected startReset(v: LiftView): void {
    this.resetReason.set(v.controls.reset_reasons[0] ?? 'other');
    this.edit.start('reset');
  }

  protected saveCounts(v: LiftView): void {
    const counts = !v.counts;
    const body = { exercise_id: v.exercise_id, classification: counts ? 'counts' : 'excluded' };
    this.edit.save('counts', this.api.command('setup/exercises/classify', body), () => {
      this.reload();
      return counts ? 'Counts again.' : 'Moved to Not counted.';
    });
  }

  protected savePause(v: LiftView): void {
    const paused = !v.paused;
    const reason = this.pauseReason().trim();
    const body = paused && reason ? { exercise_id: v.exercise_id, paused, reason } : { exercise_id: v.exercise_id, paused };
    this.edit.save('pause', this.api.command('setup/exercises/pause', body), () => {
      this.reload();
      return paused ? 'Paused.' : 'Unpaused.';
    });
  }

  protected saveReset(v: LiftView): void {
    const body = { exercise_id: v.exercise_id, reason: this.resetReason() };
    this.edit.save('reset', this.api.command<{ say: string }>('lift/reset', body), (res) => {
      this.reload();
      return res.say;
    });
  }
}
