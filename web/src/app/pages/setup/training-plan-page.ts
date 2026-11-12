import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CoachApi } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Card } from '../../ui/card';
import { dayLabel } from '../../ui/format';
import { SectionHeader } from '../../ui/section-header';
import { State } from '../../ui/state';
import { EditRow, EditState } from './edit-row';
import { ThisWeekCard } from './this-week-card';
import { DayChange, PlanSession, PlanWeekday, SessionType, TrainingPlanView, TYPE_NAMES } from './training-plan.types';

interface DraftSession {
  time: string;
  name: string;
  type: SessionType;
  optional: boolean;
}

const TYPES: readonly SessionType[] = ['lift', 'run', 'wrestling', 'other'];

/**
 * Setup › Training plan: the saved week, and this week's reports (ThisWeekCard).
 * Changing a weekday is a lasting change (`setup/training-plan/day`, chat's
 * update_training_plan): it replaces that day's sessions from the chosen day
 * on (today by default); past weeks keep their plan.
 */
@Component({
  selector: 'app-training-plan-page',
  imports: [PageHeader, Card, State, EditRow, SectionHeader, ThisWeekCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './setup-forms.css',
  template: `
    <div class="page">
      <app-page-header title="Training plan" back="/setup" />
      @if (view.data(); as v) {
        @if (!v.editable) {
          <app-state kind="empty" message="No training plan is saved yet. It is read from the plan file when the coach starts." />
        } @else {
          <div class="cols">
            <div class="stack">
              <app-section-header title="Saved week" [aside]="savedAside(v)" />
              <app-card>
                @for (d of v.days; track d.weekday) {
                  <app-edit-row [label]="name(d.weekday)" [hint]="line(d.sessions)" [value]="count(d.sessions)"
                                [editable]="true" editLabel="Change"
                                [editing]="edit.open() === d.weekday" [busy]="edit.busy() === d.weekday"
                                [error]="edit.errorFor(d.weekday)" [notice]="edit.noticeFor(d.weekday)"
                                (edit)="start(d.weekday, d.sessions, v)" (cancel)="edit.cancel()" (save)="save(d.weekday)">
                    <div class="sessions">
                      @for (s of draft(); track $index; let i = $index) {
                        <div class="sess">
                          <input class="t" type="text" maxlength="9" placeholder="06:30 / evening" aria-label="Time"
                                 [value]="s.time" (input)="patch(i, 'time', value($event))" />
                          <input class="n" type="text" maxlength="40" placeholder="Name" aria-label="Name"
                                 [value]="s.name" (input)="patch(i, 'name', value($event))" />
                          <select aria-label="Type" (change)="patch(i, 'type', asType(value($event)))">
                            @for (t of types; track t) { <option [value]="t" [selected]="t === s.type">{{ typeName(t) }}</option> }
                          </select>
                          <div class="row2">
                            <label class="opt small"><input type="checkbox" [checked]="s.optional"
                                   (change)="patch(i, 'optional', checked($event))" /> Optional</label>
                            <button type="button" class="rm" (click)="remove(i)" [attr.aria-label]="'Remove ' + (s.name || 'session')">Remove</button>
                          </div>
                        </div>
                      } @empty {
                        <p class="t2 small none">Rest day.</p>
                      }
                      <div class="foot">
                        <button type="button" class="more" (click)="add()" [disabled]="draft().length >= 6">+ Session</button>
                        <label class="from small t2">From
                          <input type="date" aria-label="First day it applies" [min]="v.this_week[0]?.date ?? ''"
                                 [value]="from()" (input)="from.set(value($event))" />
                        </label>
                      </div>
                    </div>
                  </app-edit-row>
                }
              </app-card>
            </div>
            <div class="stack">
              <app-section-header title="This week" aside="For this week only" />
              <app-this-week-card [view]="v" (changed)="view.data.set($event)" />
            </div>
          </div>
        }
      } @else if (view.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="view.load()" />
      } @else {
        <app-state kind="loading" [blocks]="3" />
      }
    </div>
  `,
  styles: `
    .cols { display: grid; gap: 12px; align-items: start; }
    @media (min-width: 900px) { .cols { grid-template-columns: 1fr 1fr; gap: 24px; } }
    .sessions { display: grid; gap: 8px; width: 100%; }
    .sess { display: grid; grid-template-columns: 132px 1fr; gap: 8px; align-items: center;
      padding-bottom: 8px; border-bottom: 1px solid var(--divider); }
    .sess .t { width: 132px; }
    .sess .n { width: 100%; }
    .row2 { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .opt { display: inline-flex; align-items: center; gap: 6px; color: var(--text-2); }
    .opt input { height: auto; box-shadow: none; padding: 0; }
    .rm, .more { padding: 6px 8px; border-radius: var(--radius-inner); font-weight: 500; justify-self: end; }
    .more { padding-left: 0; }
    @media (hover: hover) { .rm:hover, .more:hover { background: var(--inset); } }
    @media (pointer: coarse) { .rm, .more { min-height: 44px; } }
    .more[disabled] { opacity: .5; cursor: default; }
    .foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
    .from { display: inline-flex; align-items: center; gap: 8px; }
    .from input { width: 160px; }
    .none { margin: 0; }
  `,
})
export class TrainingPlanPage {
  private readonly api = inject(CoachApi);
  protected readonly view = viewResource<TrainingPlanView>('setup/training-plan');
  protected readonly edit = new EditState();
  protected readonly types = TYPES;
  protected readonly draft = signal<DraftSession[]>([]);
  protected readonly from = signal('');
  protected readonly label = (day: string) => dayLabel(day);
  protected readonly typeName = (t: SessionType) => TYPE_NAMES[t];

  constructor() {
    this.view.load();
  }

  protected value(e: Event): string {
    return (e.target as HTMLInputElement | HTMLSelectElement).value;
  }

  protected checked(e: Event): boolean {
    return (e.target as HTMLInputElement).checked;
  }

  protected name(day: PlanWeekday): string {
    return day.charAt(0).toUpperCase() + day.slice(1);
  }

  protected asType(v: string): SessionType {
    return TYPES.find((t) => t === v) ?? 'other';
  }

  /** "Since 9 Nov", plus when a saved change starts ("· changes 16 Nov"); the rows show the plan in force today. */
  protected savedAside(v: TrainingPlanView): string {
    const since = v.valid_from ? `Since ${dayLabel(v.valid_from, false)}` : '';
    const next = v.upcoming.length ? `changes ${dayLabel(v.upcoming[0].valid_from, false)}` : '';
    return [since, next].filter(Boolean).join(' · ');
  }

  protected line(sessions: PlanSession[]): string {
    if (!sessions.length) return 'Rest day';
    return sessions.map((s) => `${s.time ? s.time + ' ' : ''}${s.name}${s.optional ? ' (optional)' : ''}`).join(' · ');
  }

  protected count(sessions: PlanSession[]): string {
    const n = sessions.filter((s) => !s.optional).length;
    return n === 0 ? 'Rest' : `${n} session${n === 1 ? '' : 's'}`;
  }

  protected start(day: PlanWeekday, sessions: PlanSession[], v: TrainingPlanView): void {
    this.draft.set(sessions.map((s) => ({ time: s.time ?? '', name: s.name, type: s.type, optional: s.optional })));
    this.from.set(v.this_week.find((d) => d.today)?.date ?? '');
    this.edit.start(day);
  }

  protected patch<K extends keyof DraftSession>(i: number, key: K, v: DraftSession[K]): void {
    this.draft.update((list) => list.map((s, n) => (n === i ? { ...s, [key]: v } : s)));
  }

  protected add(): void {
    this.draft.update((list) => [...list, { time: '', name: '', type: 'lift', optional: false }]);
  }

  protected remove(i: number): void {
    this.draft.update((list) => list.filter((_, n) => n !== i));
  }

  protected save(day: PlanWeekday): void {
    const body: DayChange = {
      weekday: day,
      sessions: this.draft().map((s) => ({
        name: s.name.trim(), type: s.type, time: s.time.trim().toLowerCase() || null, optional: s.optional,
      })),
    };
    if (this.from()) body.from = this.from();
    const starts = this.from();
    this.edit.save(day, this.api.command<TrainingPlanView>('setup/training-plan/day', body), (v) => {
      this.view.data.set(v);
      return starts ? `Saved. Applies from ${dayLabel(starts)}.` : 'Saved.';
    });
  }
}
