import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { Icon } from '../ui/icon';

/**
 * The refresh control: asks the coach to sync MFP and Hevy now, then reload.
 * Spins while `busy`.
 *
 *   <app-refresh-button actions [busy]="res.refreshing()" (refresh)="res.refresh()" />
 */
@Component({
  selector: 'app-refresh-button',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="iconbtn" [class.busy]="busy()" [attr.aria-busy]="busy()"
            [attr.aria-label]="busy() ? 'Syncing…' : 'Sync and refresh'" [disabled]="busy()" (click)="refresh.emit()">
      <app-icon name="refresh" />
    </button>
  `,
  styles: `
    :host { display: inline-grid; }
    .busy { opacity: 1 !important; color: var(--text); }
    .busy app-icon { animation: spin 1s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
  `,
})
export class RefreshButton {
  readonly busy = input(false);
  readonly refresh = output<void>();
}
