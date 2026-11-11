import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CoachApi } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Card } from '../../ui/card';
import { dayLabel, todayIso } from '../../ui/format';
import { State } from '../../ui/state';
import { EditState } from './edit-row';
import { ContextNote, ContextNotesView, Unusable } from './setup-records.types';

const UNUSABLE: readonly { id: Unusable; name: string }[] = [
  { id: 'no', name: 'No' }, { id: 'maybe', name: 'Maybe' }, { id: 'yes', name: 'Yes' },
];

/** "salty_or_large_meal" → "salty or large meal" */
export function tagLabel(tag: string): string {
  return tag.replaceAll('_', ' ');
}

/**
 * Setup › Context notes: what the coach knows about your days (illness,
 * travel, a camp week …), newest first. Add one (chat's add_context_note,
 * your words unchanged) or delete one (delete_context_note, after a confirm).
 */
@Component({
  selector: 'app-context-notes-page',
  imports: [PageHeader, Card, State],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./setup-forms.css', './setup-records.css'],
  template: `
    <div class="page">
      <app-page-header title="Context notes" back="/setup" />
      @if (view.data(); as v) {
        <div class="stack">
          <app-card label="New note">
            @if (edit.open() !== 'add') {
              <div class="row">
                <p class="t2 small grow">Something the coach should know: illness, travel, a heavy week, pain.</p>
                <button type="button" class="btn primary" (click)="startAdd(v)">Add note</button>
              </div>
              @if (edit.noticeFor('add')) { <p class="msg ok small" role="status">{{ edit.noticeFor('add') }}</p> }
            } @else {
              <form class="form" (submit)="$event.preventDefault(); add()">
                <label class="field"><span>Note, in your words</span>
                  <textarea rows="3" [value]="text()" (input)="text.set(value($event))"
                            placeholder="e.g. Wrestling camp next week, two sessions a day"></textarea>
                </label>
                <div class="pair">
                  <label class="field"><span>From</span>
                    <input type="date" [value]="from()" (input)="from.set(value($event))" required />
                  </label>
                  <label class="field"><span>To (empty: ongoing)</span>
                    <input type="date" [value]="to()" [min]="from()" (input)="to.set(value($event))" />
                  </label>
                </div>
                <fieldset class="field">
                  <legend class="small t2">Tags</legend>
                  <div class="chips">
                    @for (t of v.tag_options; track t) {
                      <button type="button" class="chip" [attr.aria-pressed]="tags().includes(t)" (click)="toggleTag(t)">
                        {{ tagLabel(t) }}
                      </button>
                    }
                  </div>
                </fieldset>
                <label class="field"><span>Makes the week's weight unreliable</span>
                  <select [value]="unusable()" (change)="unusable.set($any(value($event)))">
                    @for (u of unusable_; track u.id) { <option [value]="u.id" [selected]="u.id === unusable()">{{ u.name }}</option> }
                  </select>
                </label>
                <div class="btns">
                  <button type="button" class="btn" (click)="edit.cancel()" [disabled]="edit.busy() === 'add'">Cancel</button>
                  <button type="submit" class="btn primary" [disabled]="edit.busy() === 'add' || !text().trim()">
                    {{ edit.busy() === 'add' ? 'Saving…' : 'Save note' }}
                  </button>
                </div>
                @if (edit.errorFor('add')) { <p class="msg bad small" role="alert">{{ edit.errorFor('add') }}</p> }
              </form>
            }
          </app-card>

          <app-card [label]="'Notes · ' + v.notes.length">
            @if (!v.notes.length) {
              <p class="t3 small empty">No notes yet.</p>
            }
            <ul class="rows">
              @for (n of v.notes; track n.id) {
                <li>
                  <div class="row top">
                    <div class="grow txt">
                      <div class="t2 small num">{{ when(n) }}@if (current(n, v.today)) { <span class="today"> · applies today</span> }</div>
                      <div class="note-text">{{ n.text }}</div>
                      @if (n.tags.length || n.suggest_unusable !== 'no') {
                        <div class="chips">
                          @for (t of n.tags; track t) { <span class="chip">{{ tagLabel(t) }}</span> }
                          @if (n.suggest_unusable !== 'no') {
                            <span class="chip">weight {{ n.suggest_unusable === 'yes' ? 'unreliable' : 'maybe unreliable' }}</span>
                          }
                        </div>
                      }
                    </div>
                    @if (edit.open() !== 'del:' + n.id) {
                      <button type="button" class="link danger small" (click)="edit.start('del:' + n.id)"
                              [disabled]="!!edit.busy()" aria-label="Delete this note">Delete</button>
                    }
                  </div>
                  @if (edit.open() === 'del:' + n.id) {
                    <div class="confirm">
                      <span class="small grow">Delete this note? The coach stops using it.</span>
                      <button type="button" class="btn" (click)="edit.cancel()" [disabled]="!!edit.busy()">Keep</button>
                      <button type="button" class="btn danger" (click)="remove(n)" [disabled]="!!edit.busy()">
                        {{ edit.busy() === 'del:' + n.id ? 'Deleting…' : 'Delete' }}
                      </button>
                    </div>
                  }
                  @if (edit.errorFor('del:' + n.id)) { <p class="msg bad small" role="alert">{{ edit.errorFor('del:' + n.id) }}</p> }
                </li>
              }
            </ul>
          </app-card>
          @if (noticeAfter('del:')) { <p class="msg ok small note" role="status">Note deleted.</p> }
        </div>
      } @else if (view.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="view.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `
    .row { display: flex; align-items: center; gap: 12px; }
    .row.top { align-items: flex-start; }
    .row p { margin: 0; }
    .grow { flex: 1; min-width: 0; }
    .txt { display: grid; gap: 6px; }
    .note-text { overflow-wrap: anywhere; }
    .today { color: var(--text); font-weight: 500; }
    fieldset { border: 0; margin: 0; padding: 0; }
    legend { padding: 0; margin-bottom: 6px; }
    .confirm { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 10px; padding: 10px 12px;
      border-radius: var(--radius-inner); background: var(--inset); }
    @media (min-width: 900px) { .stack { max-width: 640px; } }
  `,
})
export class ContextNotesPage {
  private readonly api = inject(CoachApi);
  protected readonly view = viewResource<ContextNotesView>('setup/context-notes');
  protected readonly edit = new EditState();
  protected readonly unusable_ = UNUSABLE;
  protected readonly tagLabel = tagLabel;
  protected readonly text = signal('');
  protected readonly from = signal('');
  protected readonly to = signal('');
  protected readonly tags = signal<string[]>([]);
  protected readonly unusable = signal<Unusable>('no');

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

  protected when(n: ContextNote): string {
    const from = dayLabel(n.applies_from);
    if (n.applies_to == null) return `From ${from}, ongoing`;
    if (n.applies_to === n.applies_from) return from;
    return `${from} – ${dayLabel(n.applies_to)}`;
  }

  protected current(n: ContextNote, today: string): boolean {
    return n.applies_from <= today && (n.applies_to == null || n.applies_to >= today);
  }

  protected startAdd(v: ContextNotesView): void {
    this.text.set('');
    this.from.set(v.today || todayIso());
    this.to.set('');
    this.tags.set([]);
    this.unusable.set('no');
    this.edit.start('add');
  }

  protected toggleTag(t: string): void {
    this.tags.update((tags) => (tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t]));
  }

  protected add(): void {
    const body = {
      text: this.text().trim(), applies_from: this.from(), applies_to: this.to() || null,
      tags: this.tags(), suggest_unusable: this.unusable(),
    };
    this.edit.save('add', this.api.command<ContextNotesView>('setup/context-notes/add', body), (v) => {
      this.view.data.set(v);
      return 'Note saved.';
    });
  }

  protected remove(n: ContextNote): void {
    this.edit.save(`del:${n.id}`, this.api.command<ContextNotesView>('setup/context-notes/delete', { id: n.id }),
      (v) => {
        this.view.data.set(v);
        return 'Note deleted.';
      });
  }
}
