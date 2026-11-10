import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { Icon } from './icon';

/**
 * Loading, error and empty states. They keep the footprint of what they stand
 * in for and say one short sentence.
 *
 *   <app-state kind="loading" [blocks]="2" />
 *   <app-state kind="error" [message]="err" (retry)="reload()" />
 *   <app-state kind="empty" message="Nothing logged yet." />
 */
@Component({
  selector: 'app-state',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @switch (kind()) {
      @case ('loading') {
        <div class="loading" aria-busy="true" aria-label="Loading">
          @for (b of blockList(); track $index) { <div class="block"></div> }
        </div>
      }
      @case ('error') {
        <div class="box error" role="alert">
          <app-icon name="alert" class="ic" />
          <div class="txt">
            <div class="m">{{ title() || "Couldn't load this." }}</div>
            @if (message()) { <div class="t2 small">{{ message() }}</div> }
          </div>
          <button type="button" class="retry m" (click)="retry.emit()">Try again</button>
        </div>
      }
      @default {
        <div class="box empty">
          @if (title()) { <div class="m">{{ title() }}</div> }
          <div class="t2">{{ message() }}</div>
        </div>
      }
    }
  `,
  styles: `
    :host { display: block; }
    .loading { display: grid; gap: 12px; }
    .block { height: 140px; border-radius: var(--radius); background: var(--inset); animation: pulse 1.6s ease-in-out infinite; }
    @keyframes pulse { 50% { opacity: .55; } }
    .box { display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: var(--radius);
      background: var(--container); box-shadow: var(--ring); }
    .error .ic { color: var(--destructive); --icon: 18px; }
    .txt { flex: 1; min-width: 0; }
    .retry { padding: 6px 10px; border-radius: var(--radius-inner); background: var(--inset); white-space: nowrap; }
    .retry:hover { color: var(--text); }
    .empty { flex-direction: column; justify-content: center; text-align: center; padding: 40px 16px; gap: 4px; }
  `,
})
export class State {
  readonly kind = input<'loading' | 'error' | 'empty'>('empty');
  readonly title = input('');
  readonly message = input('');
  readonly blocks = input(1);
  readonly retry = output<void>();

  protected blockList(): number[] {
    return Array.from({ length: this.blocks() }, (_, i) => i);
  }
}
