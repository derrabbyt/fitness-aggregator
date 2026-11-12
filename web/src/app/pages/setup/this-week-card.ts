import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { CoachApi } from '../../api/coach-api';
import { Card } from '../../ui/card';
import { dayLabel, fmt } from '../../ui/format';
import { EditState } from './edit-row';
import {
  ExtraSession, SessionReport, SessionResult, SessionType, TrainingPlanView, TYPE_NAMES, WeekDay, WeekSession,
} from './training-plan.types';

/** Draft of the report editor (a planned session marked done, or an extra session). */
interface ReportDraft {
  type: SessionType;
  name: string;
  kcal: string;
  activity: string;
  minutes: string;
}

/**
 * Setup › Training plan, this week: each day's planned sessions with what was
 * reported, and the reports themselves (chat's set_session_status through
 * `setup/training-plan/session`): skip, done (kcal, or activity + duration so
 * code estimates them), an extra session, undo. The saved plan doesn't change.
 * Each session row is one tap target that opens its actions; "+ Extra session"
 * sits once under the week, for today or an earlier day. Keys of `edit` start
 * with the day (or are `extra`), so a confirmation or refusal shows where it
 * was made.
 */
@Component({
  selector: 'app-this-week-card',
  imports: [Card, NgTemplateOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './setup-forms.css',
  template: `
    <app-card>
      @for (d of view().this_week; track d.date) {
        <div class="day" [class.today]="d.today">
          <div class="dh">
            <span class="m">{{ label(d.date) }}</span>
            @if (d.today) { <span class="tag">Today</span> }
            @if (!d.sessions.length && !d.extras.length) { <span class="t2 small">Rest day</span> }
          </div>

          @for (s of d.sessions; track s.id) {
            <ng-container *ngTemplateOutlet="row; context: { key: d.date + '|s|' + s.id, time: s.time ?? '',
              name: s.name, status: status(s), tone: tone(s), muted: s.status === 'skipped' }" />
            @if (view().editable && openRow() === d.date + '|s|' + s.id) {
              <div class="acts">
                @if (s.status) {
                  <button type="button" class="act" [disabled]="!!edit.busy()"
                          (click)="send(d.date + '|act', { date: d.date, status: 'clear', session_id: s.id })">Undo</button>
                } @else {
                  <button type="button" class="act" [disabled]="!!edit.busy()"
                          (click)="send(d.date + '|act', { date: d.date, status: 'skipped', session_id: s.id })">Skip</button>
                  @if (started(d)) {
                    <button type="button" class="act" [disabled]="!!edit.busy()" (click)="startDone(d, s)">Done</button>
                  }
                }
              </div>
            }
            @if (edit.open() === d.date + '|done|' + s.id) {
              <ng-container *ngTemplateOutlet="editor; context: { d, s }" />
            }
          }

          @for (x of d.extras; track x.extra_id) {
            <ng-container *ngTemplateOutlet="row; context: { key: d.date + '|x|' + x.extra_id, time: 'extra',
              name: x.name || typeName(x.type), status: extraText(x), tone: 'ok', muted: false }" />
            @if (view().editable && openRow() === d.date + '|x|' + x.extra_id) {
              <div class="acts">
                <button type="button" class="act" [disabled]="!!edit.busy()"
                        (click)="send(d.date + '|act', { date: d.date, status: 'clear', extra_id: x.extra_id })">Remove</button>
              </div>
            }
          }
          @if (message(d.date); as m) {
            <p class="msg small" [class.bad]="m.bad" [class.ok]="!m.bad" [attr.role]="m.bad ? 'alert' : 'status'">{{ m.text }}</p>
          }
        </div>
      }

      @if (view().editable && startedDays().length) {
        <div class="extra">
          @if (edit.open() === 'extra') {
            <ng-container *ngTemplateOutlet="editor; context: { d: null, s: null }" />
          } @else {
            <button type="button" class="add" (click)="startExtra()" [disabled]="!!edit.busy()">+ Extra session</button>
          }
          @if (message('extra'); as m) {
            <p class="msg small" [class.bad]="m.bad" [class.ok]="!m.bad" [attr.role]="m.bad ? 'alert' : 'status'">{{ m.text }}</p>
          }
        </div>
      }
    </app-card>

    <ng-template #row let-key="key" let-time="time" let-name="name" let-status="status" let-tone="tone" let-muted="muted">
      @if (view().editable) {
        <button type="button" class="srow tap" (click)="toggle(key)" [attr.aria-expanded]="openRow() === key"
                [attr.aria-label]="name + (status ? ', ' + status : '')">
          <ng-container *ngTemplateOutlet="cells; context: { time, name, status, tone, muted }" />
        </button>
      } @else {
        <div class="srow"><ng-container *ngTemplateOutlet="cells; context: { time, name, status, tone, muted }" /></div>
      }
    </ng-template>

    <ng-template #cells let-time="time" let-name="name" let-status="status" let-tone="tone" let-muted="muted">
      <span class="time t2 small num">{{ time }}</span>
      <span class="what">
        <span [class.t2]="muted">{{ name }}</span>
        @if (status) { <span class="small" [class]="tone">{{ status }}</span> }
      </span>
    </ng-template>

    <ng-template #editor let-d="d" let-s="s">
      <form class="editor" (submit)="$event.preventDefault(); saveReport(d, s)">
        @if (!s) {
          <div class="fields">
            <select aria-label="Day" (change)="extraDay.set(value($event))">
              @for (x of startedDays(); track x.date) {
                <option [value]="x.date" [selected]="x.date === extraDay()">{{ label(x.date) }}</option>
              }
            </select>
            <select aria-label="Type" (change)="set('type', value($event))">
              @for (t of types; track t) { <option [value]="t" [selected]="t === draft().type">{{ typeName(t) }}</option> }
            </select>
            <input class="grow" type="text" maxlength="40" placeholder="Name, e.g. Football" aria-label="Name"
                   [value]="draft().name" (input)="set('name', value($event))" />
          </div>
        }
        <div class="fields">
          <input type="number" inputmode="numeric" min="0" step="1" placeholder="kcal" aria-label="kcal"
                 [value]="draft().kcal" (input)="set('kcal', value($event))" />
          <span class="unit">kcal</span>
        </div>
        @if (estimable()) {
          <div class="fields">
            <span class="unit">or</span>
            <select aria-label="Activity" (change)="set('activity', value($event))">
              <option value="" [selected]="!draft().activity">Activity…</option>
              @for (a of view().activities; track a) { <option [value]="a" [selected]="a === draft().activity">{{ words(a) }}</option> }
            </select>
            <input type="number" inputmode="numeric" min="1" step="1" placeholder="min" aria-label="Duration in minutes"
                   [value]="draft().minutes" (input)="set('minutes', value($event))" />
            <span class="unit">min</span>
          </div>
        }
        <div class="btns">
          <button type="button" class="btn" (click)="edit.cancel()" [disabled]="!!edit.busy()">Cancel</button>
          <button type="submit" class="btn primary" [disabled]="!!edit.busy()">{{ edit.busy() ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
    </ng-template>
  `,
  styles: `
    .day { padding: 12px 0; }
    .day + .day { border-top: 1px solid var(--divider); }
    .day:first-of-type { padding-top: 0; }
    .dh { display: flex; align-items: baseline; gap: 8px; margin-bottom: 4px; }
    .tag { font-size: 12px; font-weight: 500; color: var(--text-2); text-transform: uppercase; letter-spacing: .02em; }
    .srow { display: flex; align-items: center; gap: 10px; min-height: 40px; width: 100%; text-align: left; }
    .tap { margin: 0 -8px; padding: 4px 8px; width: calc(100% + 16px); border-radius: var(--radius-inner); }
    .tap[aria-expanded="true"] { background: var(--inset); }
    @media (hover: hover) { .tap:hover { background: var(--inset); } }
    @media (pointer: coarse) { .srow { min-height: 44px; } }
    .time { width: 56px; flex: none; }
    .what { flex: 1; min-width: 0; display: flex; flex-direction: column; }
    .ok { color: var(--success); }
    .bad { color: var(--destructive); }
    .acts { display: flex; gap: 6px; margin: 6px 0 4px 66px; }
    @media (max-width: 480px) { .acts { margin-left: 0; } }
    .act, .add { padding: 6px 12px; border-radius: var(--radius-inner); font-weight: 500; }
    .act { background: var(--inset); }
    @media (hover: hover) { .add:hover { background: var(--inset); } }
    .act[disabled], .add[disabled] { opacity: .5; cursor: default; }
    @media (pointer: coarse) { .act, .add { min-height: 44px; padding: 0 14px; } }
    .extra { margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--divider); }
    .add { margin-left: -12px; }
    .editor { margin: 6px 0 4px 66px; display: grid; gap: 8px; }
    .extra .editor { margin-left: 0; }
    @media (max-width: 480px) { .editor { margin-left: 0; } }
    .fields { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .grow { flex: 1; min-width: 140px; }
    input[type="number"] { width: 104px; }
    .btns { display: flex; justify-content: flex-end; gap: 8px; }
    .btn { height: 36px; padding: 0 14px; border-radius: var(--radius-inner); font-weight: 500;
      background: var(--inset); color: var(--text); }
    .btn.primary { background: var(--fill); color: var(--container); }
    .btn[disabled] { opacity: .5; cursor: default; }
    @media (pointer: coarse) { .btn { height: 44px; } }
    .msg { margin: 6px 0 0 66px; }
    .extra .msg { margin-left: 0; }
    @media (max-width: 480px) { .msg { margin-left: 0; } }
  `,
})
export class ThisWeekCard {
  private readonly api = inject(CoachApi);
  readonly view = input.required<TrainingPlanView>();
  readonly changed = output<TrainingPlanView>();
  protected readonly edit = new EditState();
  protected readonly types: readonly SessionType[] = ['other', 'run', 'wrestling', 'lift'];
  protected readonly draft = signal<ReportDraft>({ type: 'other', name: '', kcal: '', activity: '', minutes: '' });
  /** The row whose actions are open (one at a time). */
  protected readonly openRow = signal<string | null>(null);
  /** The day an extra session is added to. */
  protected readonly extraDay = signal('');
  /** Today and the days before it: sessions can be marked done and extras added there. */
  protected readonly startedDays = computed(() => this.view().this_week.filter((d) => this.started(d)));
  protected readonly label = (day: string) => dayLabel(day);
  protected readonly typeName = (t: SessionType) => TYPE_NAMES[t];

  protected value(e: Event): string {
    return (e.target as HTMLInputElement | HTMLSelectElement).value;
  }

  protected words(key: string): string {
    const s = key.replace(/_/g, ' ');
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  /** Today or earlier (skipping works ahead too). */
  protected started(d: WeekDay): boolean {
    const today = this.view().this_week.find((x) => x.today)?.date;
    return !today || d.date <= today;
  }

  protected set(key: keyof ReportDraft, v: string): void {
    this.draft.update((d) => ({ ...d, [key]: v }));
  }

  protected toggle(key: string): void {
    this.openRow.update((k) => (k === key ? null : key));
    if (this.edit.open()?.includes('|done|')) this.edit.cancel();
  }

  protected status(s: WeekSession): string {
    if (s.status === 'skipped') return 'Skipped';
    if (s.status === 'done') return s.kcal == null ? 'Done' : `Done · ${fmt(s.kcal)} kcal${source(s.kcal_source)}`;
    return s.optional ? 'Optional' : '';
  }

  protected tone(s: WeekSession): string {
    return s.status === 'done' ? 'ok' : 't2';
  }

  protected extraText(x: ExtraSession): string {
    const kind = x.name ? `${TYPE_NAMES[x.type]} · ` : '';
    return x.kcal == null ? `${kind}setup value` : `${kind}${fmt(x.kcal)} kcal${source(x.kcal_source)}`;
  }

  /** Code estimates kcal from an activity and a duration, except wrestling and lifting (their setup values count). */
  protected estimable(): boolean {
    const t = this.draft().type;
    return t !== 'wrestling' && t !== 'lift';
  }

  protected startDone(d: WeekDay, s: WeekSession): void {
    this.draft.set({ type: s.type, name: s.name, kcal: '', activity: s.type === 'run' ? 'running' : '', minutes: '' });
    this.edit.start(`${d.date}|done|${s.id}`);
  }

  protected startExtra(): void {
    const days = this.startedDays();
    this.draft.set({ type: 'other', name: '', kcal: '', activity: '', minutes: '' });
    this.extraDay.set((days.find((d) => d.today) ?? days[days.length - 1])?.date ?? '');
    this.openRow.set(null);
    this.edit.start('extra');
  }

  protected saveReport(d: WeekDay | null, s: WeekSession | null): void {
    const f = this.draft();
    const body: SessionReport = d && s
      ? { date: d.date, status: 'done', session_id: s.id }
      : { date: this.extraDay(), status: 'extra', type: f.type, ...(f.name.trim() ? { name: f.name.trim() } : {}) };
    if (f.kcal.trim()) body.kcal = Number(f.kcal);
    else if (this.estimable()) {
      if (f.activity) body.activity = f.activity;
      if (f.minutes.trim()) body.duration_min = Number(f.minutes);
    }
    this.send(d && s ? `${d.date}|done|${s.id}` : 'extra', body);
  }

  protected send(key: string, body: SessionReport): void {
    this.edit.save(key, this.api.command<SessionResult>('setup/training-plan/session', body), (r) => {
      this.openRow.set(null);
      this.changed.emit(r.section);
      return confirmation(body, r);
    });
  }

  /** The latest confirmation or refusal made under a day (or under `extra`). */
  protected message(date: string): { text: string; bad: boolean } | null {
    const e = this.edit.error();
    if (e && e.key.startsWith(date)) return { text: e.text, bad: true };
    const n = this.edit.notice();
    if (n && n.key.startsWith(date)) return { text: n.text, bad: false };
    return null;
  }
}

function source(s: string | null): string {
  return s === 'estimated' ? ' (estimated)' : s === 'model_estimate' ? ' (coach’s estimate)' : '';
}

/** The one-line confirmation, as chat would give it: the kcal counted and whether they were estimated. */
function confirmation(body: SessionReport, r: SessionResult): string {
  if (body.status === 'clear') return body.extra_id ? 'Removed.' : 'Undone.';
  if (body.status === 'skipped') return 'Skipped for this week.';
  const rep = r.reported;
  if (!rep) return 'Saved.';
  if (rep.kcal == null) {
    return rep.kcal_counted == null ? 'Saved. It counts once it syncs.' : `Saved. Counts ${fmt(rep.kcal_counted)} kcal from setup.`;
  }
  const est = rep.estimate
    ? `, estimated from ${rep.estimate.activity.replace(/_/g, ' ')}, ${fmt(rep.estimate.duration_min)} min at ${fmt(rep.estimate.trend_weight_kg, 1)} kg`
    : '';
  const counted = rep.kcal_counted != null && rep.kcal_counted !== rep.kcal ? ` (${fmt(rep.kcal_counted)} counted)` : '';
  return `Saved: ${fmt(rep.kcal)} kcal${counted}${est}.`;
}
