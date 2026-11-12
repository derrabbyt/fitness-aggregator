import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CoachApi } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Card } from '../../ui/card';
import { fmt } from '../../ui/format';
import { State } from '../../ui/state';
import { EditRow, EditState } from './edit-row';
import { ActivityKey, ActivityResult, ActivityView } from './setup.types';

const ROWS: readonly { key: ActivityKey; label: string; unit: string; step: string }[] = [
  { key: 'run_kcal_discount', label: 'Runs counted', unit: '%', step: '1' },
  { key: 'wrestling_kcal_per_session', label: 'Wrestling session', unit: 'kcal', step: '10' },
  { key: 'lifting_kcal_per_session', label: 'Lifting session', unit: 'kcal', step: '10' },
];

/**
 * Setup › Activity values: the calibration values. A change doesn't apply
 * here: it becomes a proposal whose card goes to Telegram, and nothing changes
 * until it is approved there.
 */
@Component({
  selector: 'app-activity-page',
  imports: [PageHeader, Card, State, EditRow],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './setup-forms.css',
  template: `
    <div class="page">
      <app-page-header title="Activity values" back="/setup" />
      @if (view.data(); as v) {
        <div class="stack">
          @if (v.pending.length) {
            <div class="info" role="status">
              <div class="m small">Waiting for your tap in Telegram</div>
              @for (p of v.pending; track p.id) { <div class="t2 small">{{ p.change }}</div> }
            </div>
          }
          <app-card>
            @for (r of rows; track r.key) {
              <app-edit-row [label]="r.label" [value]="shown(v, r.key)" [editable]="v.editable"
                            editLabel="Change" saveLabel="Propose"
                            [editing]="edit.open() === r.key" [busy]="edit.busy() === r.key"
                            [error]="edit.errorFor(r.key)" [notice]="edit.noticeFor(r.key)"
                            (edit)="start(r.key, v)" (cancel)="edit.cancel()" (save)="propose(r.key)">
                <input type="number" inputmode="decimal" [step]="r.step" [attr.aria-label]="r.label"
                       [value]="draft()" (input)="draft.set(value($event))" />
                <span class="unit">{{ r.unit }}</span>
              </app-edit-row>
            }
          </app-card>
        </div>
      } @else if (view.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="view.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `
    .info { display: grid; gap: 2px; }
    @media (min-width: 900px) { .stack { max-width: 640px; } }
  `,
})
export class ActivityPage {
  private readonly api = inject(CoachApi);
  protected readonly view = viewResource<ActivityView>('setup/activity');
  protected readonly edit = new EditState();
  protected readonly rows = ROWS;
  protected readonly draft = signal('');

  constructor() {
    this.view.load();
  }

  protected value(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }

  /** The run discount is a share (0.75); the page shows and takes it as a percentage. */
  protected shown(v: ActivityView, key: ActivityKey): string {
    const x = v.values[key].value;
    if (x == null) return '';
    return key === 'run_kcal_discount' ? `${fmt(x * 100)} %` : `${fmt(x)} kcal`;
  }

  protected start(key: ActivityKey, v: ActivityView): void {
    const x = v.values[key].value;
    this.draft.set(x == null ? '' : String(key === 'run_kcal_discount' ? Math.round(x * 100) : x));
    this.edit.start(key);
  }

  protected propose(key: ActivityKey): void {
    const raw = this.draft().trim();
    const n = raw === '' ? null : Number(raw);
    const value = n != null && key === 'run_kcal_discount' ? Math.round(n * 10) / 1000 : n;
    this.edit.save(key, this.api.command<ActivityResult>('setup/activity', { values: { [key]: value } }), (r) => {
      this.view.data.set(r.section);
      return r.proposal.referenced
        ? 'That change is already waiting for your tap in Telegram.'
        : 'Sent to Telegram. It applies once you approve it there.';
    });
  }
}
