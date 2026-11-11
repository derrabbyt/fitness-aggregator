import { ChangeDetectionStrategy, Component, DestroyRef, inject, input, output, signal } from '@angular/core';
import { Observable, Subscription } from 'rxjs';
import { errorMessage } from '../../api/coach-api';

/**
 * Which row of a Setup page is being edited, and how its last save went.
 * One per page; rows read it through `app-edit-row`'s inputs.
 *
 *   readonly edit = new EditState();
 *   this.edit.save('step', this.api.command(...), (v) => { this.view.data.set(v); return 'Saved.'; });
 */
export class EditState {
  readonly open = signal<string | null>(null);
  readonly busy = signal<string | null>(null);
  readonly error = signal<{ key: string; text: string } | null>(null);
  readonly notice = signal<{ key: string; text: string } | null>(null);
  private sub?: Subscription;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.sub?.unsubscribe());
  }

  start(key: string): void {
    this.open.set(key);
    this.error.set(null);
    this.notice.set(null);
  }

  cancel(): void {
    this.open.set(null);
    this.error.set(null);
  }

  /** Send once (the button is disabled while busy); on success close the row and show `ok`'s text. */
  save<T>(key: string, request: Observable<T>, ok: (value: T) => string): void {
    if (this.busy()) return;
    this.busy.set(key);
    this.error.set(null);
    this.notice.set(null);
    this.sub = request.subscribe({
      next: (value) => {
        this.busy.set(null);
        this.open.set(null);
        this.notice.set({ key, text: ok(value) });
      },
      error: (err: unknown) => {
        this.busy.set(null);
        this.error.set({ key, text: errorMessage(err) });
      },
    });
  }

  errorFor(key: string): string {
    const e = this.error();
    return e && e.key === key ? e.text : '';
  }

  noticeFor(key: string): string {
    const n = this.notice();
    return n && n.key === key ? n.text : '';
  }
}

/**
 * One editable value in a Setup card: label (+ hint) and the value, an edit
 * button, and when editing the projected editor with Cancel / Save. The
 * confirmation or the coach's reason for refusing shows inline underneath.
 *
 *   <app-edit-row label="Step goal" [value]="'10,000'" [editable]="true"
 *                 [editing]="edit.open() === 'step'" [busy]="edit.busy() === 'step'"
 *                 [error]="edit.errorFor('step')" [notice]="edit.noticeFor('step')"
 *                 (edit)="…" (cancel)="edit.cancel()" (save)="…">
 *     <input …/>
 *   </app-edit-row>
 */
@Component({
  selector: 'app-edit-row',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="row">
      <div class="txt">
        <div class="m">{{ label() }}</div>
        @if (hint()) { <div class="t2 small">{{ hint() }}</div> }
      </div>
      @if (!editing()) {
        <span class="val m num" [class.t3]="!value()">{{ value() || 'Not set' }}</span>
        @if (editable()) {
          <button type="button" class="edit" (click)="edit.emit()" [attr.aria-label]="'Change ' + label()">
            {{ editLabel() }}
          </button>
        }
      }
    </div>
    @if (editing()) {
      <form class="editor" (submit)="$event.preventDefault(); save.emit()">
        <div class="fields"><ng-content /></div>
        <div class="btns">
          <button type="button" class="btn" (click)="cancel.emit()" [disabled]="busy()">Cancel</button>
          <button type="submit" class="btn primary" [disabled]="busy()">{{ busy() ? 'Saving…' : saveLabel() }}</button>
        </div>
      </form>
    }
    @if (error()) { <p class="msg bad small" role="alert">{{ error() }}</p> }
    @if (notice()) { <p class="msg ok small" role="status">{{ notice() }}</p> }
  `,
  styles: `
    :host { display: block; padding: 12px 0; border-top: 1px solid var(--divider); }
    :host(:first-child) { border-top: 0; padding-top: 0; }
    :host(:last-child) { padding-bottom: 0; }
    .row { display: flex; align-items: center; gap: 12px; min-height: 32px; }
    .txt { flex: 1; min-width: 0; }
    .val { text-align: right; }
    .edit { padding: 6px 10px; margin-right: -6px; border-radius: var(--radius-inner); color: var(--info); font-weight: 500; }
    .edit:hover { background: var(--inset); }
    .editor { margin-top: 10px; display: grid; gap: 10px; }
    .fields { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .btns { display: flex; justify-content: flex-end; gap: 8px; }
    .msg { margin: 8px 0 0; }
  `,
})
export class EditRow {
  readonly label = input.required<string>();
  readonly hint = input('');
  readonly value = input('');
  readonly editable = input(false);
  readonly editing = input(false);
  readonly busy = input(false);
  readonly error = input('');
  readonly notice = input('');
  readonly editLabel = input('Edit');
  readonly saveLabel = input('Save');
  readonly edit = output<void>();
  readonly cancel = output<void>();
  readonly save = output<void>();
}
