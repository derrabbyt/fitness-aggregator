import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Icon } from '../ui/icon';
import { Tabs } from './tabs';

/**
 * Every page's header: title (+ sub line), the tab segments on desktop, and
 * slots for controls.
 *
 *   <app-page-header title="Check-in" sub="9–15 Nov">
 *     <button prev …/> <button next …/>     ← either side of the title (e.g. day or week arrows)
 *     <app-refresh-button actions …/>       ← right-hand actions
 *   </app-page-header>
 *
 * With `back` (a URL) a back arrow replaces the prev slot (detail views).
 */
@Component({
  selector: 'app-page-header',
  imports: [Tabs, Icon, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header>
      @if (back(); as to) {
        <a class="iconbtn" [routerLink]="to" [queryParams]="backQuery()" aria-label="Back"><app-icon name="back" /></a>
      }
      <ng-content select="[prev]" />
      <div class="title">
        <h1>{{ title() }}</h1>
        @if (sub()) { <div class="sub">{{ sub() }}</div> }
      </div>
      <ng-content select="[next]" />
      <app-tabs variant="segments" class="segments" />
      <div class="actions"><ng-content select="[actions]" /></div>
    </header>
  `,
  styles: `
    header { display: flex; align-items: center; gap: 4px; padding: 8px 0 16px; min-height: 64px; }
    .title { flex: 1; min-width: 0; text-align: center; }
    h1 { font-size: var(--type-title); line-height: 28px; font-weight: 500; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sub { font-size: var(--type-small); color: var(--text-2); }
    .actions { display: flex; align-items: center; gap: 4px; }
    .actions:empty { display: none; }
    @media (min-width: 900px) {
      header { padding-bottom: 24px; }
      .title { text-align: left; order: -1; }
      h1 { font-size: var(--type-title-wide); line-height: 32px; }
      .segments { margin: 0 16px; }
    }
  `,
})
export class PageHeader {
  readonly title = input.required<string>();
  readonly sub = input('');
  readonly back = input<string | null>(null);
  readonly backQuery = input<Record<string, string | null> | null>(null);
}
