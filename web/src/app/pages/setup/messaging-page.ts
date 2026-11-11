import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CoachApi } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Card } from '../../ui/card';
import { State } from '../../ui/state';
import { EditRow, EditState } from './edit-row';
import { MessagingField, MessagingView, Weekday } from './setup.types';

const DAYS: readonly { id: Weekday; name: string }[] = [
  { id: 'mon', name: 'Monday' }, { id: 'tue', name: 'Tuesday' }, { id: 'wed', name: 'Wednesday' },
  { id: 'thu', name: 'Thursday' }, { id: 'fri', name: 'Friday' }, { id: 'sat', name: 'Saturday' },
  { id: 'sun', name: 'Sunday' },
];

/**
 * Setup › Messaging: when the coach writes. Each value saves directly
 * (`setup/messaging` {field, value}, chat's record_setup_value); an empty
 * value turns it off.
 */
@Component({
  selector: 'app-messaging-page',
  imports: [PageHeader, Card, State, EditRow],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './setup-forms.css',
  template: `
    <div class="page">
      <app-page-header title="Messaging" back="/setup" />
      @if (view.data(); as v) {
        <div class="stack">
          <app-card>
            <app-edit-row label="Weekly check-in" hint="The day and time the coach reviews your week."
                          [value]="checkIn(v)" [editable]="v.editable"
                          [editing]="edit.open() === 'weekly_checkin'" [busy]="edit.busy() === 'weekly_checkin'"
                          [error]="edit.errorFor('weekly_checkin')" [notice]="edit.noticeFor('weekly_checkin')"
                          (edit)="start('weekly_checkin', v)" (cancel)="edit.cancel()" (save)="saveCheckIn()">
              <select aria-label="Check-in day" [value]="day()" (change)="day.set(value($event))">
                @for (d of days; track d.id) { <option [value]="d.id" [selected]="d.id === day()">{{ d.name }}</option> }
              </select>
              <input type="time" aria-label="Check-in time" [value]="draft()" (input)="draft.set(value($event))" />
            </app-edit-row>

            <app-edit-row label="Evening reminder" hint="When the coach reminds you to log, if needed."
                          [value]="v.evening_reminder_time ?? ''" [editable]="v.editable"
                          [editing]="edit.open() === 'evening_reminder_time'" [busy]="edit.busy() === 'evening_reminder_time'"
                          [error]="edit.errorFor('evening_reminder_time')" [notice]="edit.noticeFor('evening_reminder_time')"
                          (edit)="start('evening_reminder_time', v)" (cancel)="edit.cancel()" (save)="save('evening_reminder_time', 'time')">
              <input type="time" aria-label="Evening reminder time" [value]="draft()" (input)="draft.set(value($event))" />
              <span class="unit">empty: off</span>
            </app-edit-row>

            <app-edit-row label="Messages a day" hint="Most messages the coach starts on its own each day."
                          [value]="count(v.max_unprompted_messages_per_day, 'message')" [editable]="v.editable"
                          [editing]="edit.open() === 'max_unprompted_messages_per_day'"
                          [busy]="edit.busy() === 'max_unprompted_messages_per_day'"
                          [error]="edit.errorFor('max_unprompted_messages_per_day')"
                          [notice]="edit.noticeFor('max_unprompted_messages_per_day')"
                          (edit)="start('max_unprompted_messages_per_day', v)" (cancel)="edit.cancel()"
                          (save)="save('max_unprompted_messages_per_day', 'int')">
              <input type="number" inputmode="numeric" min="1" step="1" aria-label="Messages a day"
                     [value]="draft()" (input)="draft.set(value($event))" />
              <span class="unit">a day</span>
            </app-edit-row>

            <app-edit-row label="Step-floor window" hint="Days under the step floor before the coach mentions it."
                          [value]="count(v.soft_floor_min_days, 'day')" [editable]="v.editable"
                          [editing]="edit.open() === 'soft_floor_min_days'" [busy]="edit.busy() === 'soft_floor_min_days'"
                          [error]="edit.errorFor('soft_floor_min_days')" [notice]="edit.noticeFor('soft_floor_min_days')"
                          (edit)="start('soft_floor_min_days', v)" (cancel)="edit.cancel()"
                          (save)="save('soft_floor_min_days', 'int')">
              <input type="number" inputmode="numeric" min="1" step="1" aria-label="Step-floor window in days"
                     [value]="draft()" (input)="draft.set(value($event))" />
              <span class="unit">days</span>
            </app-edit-row>
          </app-card>
          @if (!v.editable) { <p class="note">These can be changed while a phase is active and no phase setup is open in Telegram.</p> }
        </div>
      } @else if (view.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="view.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `@media (min-width: 900px) { .stack { max-width: 640px; } }`,
})
export class MessagingPage {
  private readonly api = inject(CoachApi);
  protected readonly view = viewResource<MessagingView>('setup/messaging');
  protected readonly edit = new EditState();
  protected readonly days = DAYS;
  protected readonly draft = signal('');
  protected readonly day = signal<string>('sun');

  constructor() {
    this.view.load();
  }

  protected value(e: Event): string {
    return (e.target as HTMLInputElement | HTMLSelectElement).value;
  }

  protected checkIn(v: MessagingView): string {
    const c = v.weekly_checkin;
    return c ? `${DAYS.find((d) => d.id === c.day)?.name ?? c.day} ${c.time}` : '';
  }

  protected count(n: number | null, unit: string): string {
    return n == null ? '' : `${n} ${unit}${n === 1 ? '' : 's'}`;
  }

  protected start(field: MessagingField, v: MessagingView): void {
    if (field === 'weekly_checkin') {
      this.day.set(v.weekly_checkin?.day ?? 'sun');
      this.draft.set(v.weekly_checkin?.time ?? '18:00');
    } else {
      const current = v[field];
      this.draft.set(current == null ? '' : String(current));
    }
    this.edit.start(field);
  }

  protected saveCheckIn(): void {
    const time = this.draft().trim();
    this.send('weekly_checkin', time ? `${this.day()} ${time}` : null);
  }

  protected save(field: MessagingField, kind: 'time' | 'int'): void {
    const raw = this.draft().trim();
    this.send(field, raw === '' ? null : kind === 'int' ? Number(raw) : raw);
  }

  private send(field: MessagingField, value: string | number | null): void {
    this.edit.save(field, this.api.command<MessagingView>('setup/messaging', { field, value }), (v) => {
      this.view.data.set(v);
      return 'Saved.';
    });
  }
}
