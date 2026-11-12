import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { Icon } from '../ui/icon';

/**
 * The refresh control: asks the coach to sync MFP and Hevy now, then reload.
 * Spins while `busy`, then shows a check for a moment while `done`.
 *
 *   <app-refresh-button actions [busy]="res.refreshing()" [done]="res.refreshed()" (refresh)="res.refresh()" />
 */
@Component({
  selector: 'app-refresh-button',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="iconbtn" [class.busy]="busy()" [class.done]="done() && !busy()"
            [attr.aria-busy]="busy()" [disabled]="busy()" (click)="refresh.emit()"
            [attr.aria-label]="busy() ? 'Syncing…' : done() ? 'Synced' : 'Sync and refresh'">
      <app-icon [name]="done() && !busy() ? 'check' : 'refresh'" />
    </button>
  `,
  styles: `
    :host { display: inline-grid; }
    .busy { opacity: 1 !important; color: var(--text); }
    .busy app-icon { animation: spin 1s linear infinite; }
    .done { color: var(--success); }
    @keyframes spin { to { transform: rotate(360deg); } }
  `,
})
export class RefreshButton {
  readonly busy = input(false);
  readonly done = input(false);
  readonly refresh = output<void>();
}
