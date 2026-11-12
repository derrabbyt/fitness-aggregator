import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CoachApi } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Card } from '../../ui/card';
import { State } from '../../ui/state';
import { EditState } from './edit-row';
import { ProfileView } from './setup-records.types';

/**
 * Setup › Profile: the short entries the coach knows about you (what
 * /profile shows in Telegram). Change, remove or add one; each save is chat's
 * update_coach_profile with a one-entry patch.
 */
@Component({
  selector: 'app-profile-page',
  imports: [PageHeader, Card, State],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./setup-forms.css', './setup-records.css'],
  template: `
    <div class="page">
      <app-page-header title="Profile" back="/setup" />
      @if (view.data(); as v) {
        <div class="stack">
          <app-card [label]="'Entries · ' + v.entries.length">
            @if (!v.entries.length) { <p class="t2 small empty">Empty.</p> }
            <ul class="rows">
              @for (e of v.entries; track e.key) {
                <li>
                  @if (edit.open() !== 'e:' + e.key) {
                    <div class="row">
                      <div class="grow txt">
                        <div class="label">{{ e.key }}</div>
                        <div class="val">{{ e.value }}</div>
                      </div>
                      <button type="button" class="link small" (click)="startEdit(e.key, e.value)" [disabled]="!!edit.busy()"
                              [attr.aria-label]="'Change ' + e.key">Edit</button>
                      <button type="button" class="link small" (click)="remove(e.key)" [disabled]="!!edit.busy()"
                              [attr.aria-label]="'Remove ' + e.key">
                        {{ edit.busy() === 'rm:' + e.key ? 'Removing…' : 'Remove' }}
                      </button>
                    </div>
                  } @else {
                    <form class="form" (submit)="$event.preventDefault(); save(e.key)">
                      <label class="field"><span class="label">{{ e.key }}</span>
                        <textarea rows="2" [attr.maxlength]="v.max_value" [value]="draftValue()"
                                  (input)="draftValue.set(value($event))"></textarea>
                      </label>
                      <div class="btns">
                        <button type="button" class="btn" (click)="edit.cancel()" [disabled]="!!edit.busy()">Cancel</button>
                        <button type="submit" class="btn primary" [disabled]="!!edit.busy()">
                          {{ edit.busy() === 'e:' + e.key ? 'Saving…' : 'Save' }}
                        </button>
                      </div>
                    </form>
                  }
                  @for (k of ['e:' + e.key, 'rm:' + e.key]; track k) {
                    @if (edit.errorFor(k)) { <p class="msg bad small" role="alert">{{ edit.errorFor(k) }}</p> }
                    @if (edit.noticeFor(k)) { <p class="msg ok small" role="status">{{ edit.noticeFor(k) }}</p> }
                  }
                </li>
              }
            </ul>
            @if (noticeAfter('rm:')) { <p class="msg ok small" role="status">{{ noticeAfter('rm:') }}</p> }
          </app-card>

          @if (edit.open() !== 'add') {
            <div class="add">
              <button type="button" class="btn" (click)="startAdd()"
                      [disabled]="v.entries.length >= v.max_entries">Add entry</button>
              @if (edit.noticeFor('add')) { <p class="msg ok small" role="status">{{ edit.noticeFor('add') }}</p> }
            </div>
          } @else {
            <app-card label="New entry">
              <form class="form" (submit)="$event.preventDefault(); add()">
                <label class="field"><span>Name (up to {{ v.max_key }} characters)</span>
                  <input type="text" [attr.maxlength]="v.max_key" [value]="draftKey()" (input)="draftKey.set(value($event))"
                         placeholder="e.g. quiet hours" />
                </label>
                <label class="field"><span>Value (up to {{ v.max_value }} characters)</span>
                  <textarea rows="2" [attr.maxlength]="v.max_value" [value]="draftValue()"
                            (input)="draftValue.set(value($event))" placeholder="e.g. no messages before 7:00"></textarea>
                </label>
                <div class="btns">
                  <button type="button" class="btn" (click)="edit.cancel()" [disabled]="!!edit.busy()">Cancel</button>
                  <button type="submit" class="btn primary" [disabled]="!!edit.busy() || !draftKey().trim() || !draftValue().trim()">
                    {{ edit.busy() === 'add' ? 'Saving…' : 'Save entry' }}
                  </button>
                </div>
                @if (edit.errorFor('add')) { <p class="msg bad small" role="alert">{{ edit.errorFor('add') }}</p> }
              </form>
            </app-card>
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
    .row { display: flex; align-items: center; gap: 4px; }
    .add { display: grid; justify-items: start; gap: 4px; }
    .grow { flex: 1; min-width: 0; }
    .txt { display: grid; gap: 2px; }
    .val { overflow-wrap: anywhere; }
    @media (min-width: 900px) { .stack { max-width: 640px; } }
  `,
})
export class ProfilePage {
  private readonly api = inject(CoachApi);
  protected readonly view = viewResource<ProfileView>('setup/profile');
  protected readonly edit = new EditState();
  protected readonly draftKey = signal('');
  protected readonly draftValue = signal('');

  constructor() {
    this.view.load();
  }

  /** The notice of a row that is gone after its save (a delete), by key prefix. */
  protected noticeAfter(prefix: string): string {
    const n = this.edit.notice();
    return n && n.key.startsWith(prefix) ? n.text : '';
  }

  protected value(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }

  protected startEdit(key: string, value: string): void {
    this.draftValue.set(value);
    this.edit.start(`e:${key}`);
  }

  protected startAdd(): void {
    this.draftKey.set('');
    this.draftValue.set('');
    this.edit.start('add');
  }

  protected save(key: string): void {
    this.patch(`e:${key}`, { [key]: this.draftValue().trim() }, 'Saved.');
  }

  protected remove(key: string): void {
    this.patch(`rm:${key}`, { [key]: null }, `Removed “${key}”.`);
  }

  protected add(): void {
    this.patch('add', { [this.draftKey().trim()]: this.draftValue().trim() }, 'Entry added.');
  }

  private patch(key: string, patch: Record<string, string | null>, ok: string): void {
    this.edit.save(key, this.api.command<ProfileView>('setup/profile', { patch }), (v) => {
      this.view.data.set(v);
      return ok;
    });
  }
}
