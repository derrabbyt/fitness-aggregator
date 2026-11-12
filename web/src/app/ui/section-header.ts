import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * A quiet section header between cards: small uppercase label, optional
 * right-aligned aside (a count, a total).
 *
 *   <app-section-header title="This week" aside="4 of 7 days" />
 */
@Component({
  selector: 'app-section-header',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 class="label">{{ title() }}</h2>
    @if (aside()) { <span class="aside num">{{ aside() }}</span> }
    <ng-content />
  `,
  styles: `
    :host { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 12px 4px 4px; }
    h2 { margin: 0; }
    .aside { font-size: var(--type-small); color: var(--text-2); }
  `,
})
export class SectionHeader {
  readonly title = input.required<string>();
  readonly aside = input('');
}
