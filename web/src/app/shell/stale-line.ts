import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Freshness } from '../api/types';
import { ago } from '../ui/format';
import { Icon } from '../ui/icon';

/**
 * One warning line when the synced data is stale, nothing otherwise. Also
 * shows a failed refresh (`refreshError`), since that is the same worry.
 *
 *   <app-stale-line [freshness]="view.freshness" [refreshError]="res.refreshError()" />
 */
@Component({
  selector: 'app-stale-line',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (text(); as t) {
      <div class="stale" role="status"><app-icon name="alert" [stroke]="2" /><span>{{ t }}</span></div>
    }
  `,
  styles: `
    .stale { display: flex; align-items: center; gap: 8px; color: var(--warning); font-weight: 500; font-size: 13px;
      margin: -6px 2px 12px; --icon: 16px; }
  `,
})
export class StaleLine {
  readonly freshness = input<Freshness | null | undefined>(null);
  readonly refreshError = input<string | null>(null);

  protected readonly text = computed(() => {
    const err = this.refreshError();
    if (err) return `Sync failed: ${err}`;
    const f = this.freshness();
    if (!f || !f.stale) return '';
    return f.age_hours == null ? 'Not synced yet' : `Last synced ${ago(f.age_hours)} ago`;
  });
}
