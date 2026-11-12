import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Icon, IconName } from '../ui/icon';

/** The four tabs; each owns the URL prefix `/<path>` (its detail views live under it). */
export const TABS: readonly { path: string; label: string; icon: IconName }[] = [
  { path: 'home', label: 'Home', icon: 'home' },
  { path: 'week', label: 'Week', icon: 'week' },
  { path: 'training', label: 'Training', icon: 'dumbbell' },
  { path: 'setup', label: 'Setup', icon: 'sliders' },
];

/**
 * The tab navigation: a bottom bar on the phone (safe-area aware) or a
 * segmented control in the page header on desktop (`variant="segments"`).
 */
@Component({
  selector: 'app-tabs',
  imports: [RouterLink, RouterLinkActive, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class]': 'variant()' },
  template: `
    <nav [attr.aria-label]="'Sections'">
      @for (t of tabs; track t.path) {
        <a [routerLink]="'/' + t.path" routerLinkActive="on" #rla="routerLinkActive"
           [attr.aria-current]="rla.isActive ? 'page' : null">
          @if (variant() === 'bar') { <span class="ic"><app-icon [name]="t.icon" /></span> }
          <span class="txt">{{ t.label }}</span>
        </a>
      }
    </nav>
  `,
  styles: `
    /* phone: bottom bar */
    :host(.bar) {
      position: fixed; left: 0; right: 0; bottom: 0; z-index: 10;
      background: var(--surface); border-top: 1px solid var(--divider);
      padding: 6px 8px calc(6px + env(safe-area-inset-bottom));
    }
    :host(.bar) nav { display: flex; justify-content: space-around; max-width: var(--page-max); margin: 0 auto; }
    :host(.bar) a {
      position: relative; display: flex; flex-direction: column; align-items: center; gap: 2px;
      min-width: 64px; min-height: 44px; padding-top: 4px; font-size: 11px; font-weight: 500; color: var(--text-2);
    }
    :host(.bar) .ic { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 8px; }
    :host(.bar) a.on { color: var(--text); }
    :host(.bar) a.on .ic { background: var(--container); box-shadow: var(--ring); }
    :host(.bar) a.on::before {
      content: ""; position: absolute; top: -7px; width: 16px; height: 4px;
      border-radius: 0 0 4px 4px; background: var(--indicator);
    }
    @media (min-width: 900px) { :host(.bar) { display: none; } }

    /* desktop: segmented control */
    :host(.segments) { display: none; }
    @media (min-width: 900px) {
      :host(.segments) { display: block; }
      :host(.segments) nav { display: flex; gap: 2px; background: var(--inset); padding: 4px; border-radius: 10px; }
      :host(.segments) a { padding: 5px 12px; border-radius: 7px; font-weight: 500; color: var(--text-2); }
      :host(.segments) a:hover { color: var(--text); }
      :host(.segments) a.on { background: var(--container); color: var(--text); box-shadow: var(--ring); }
    }
  `,
})
export class Tabs {
  readonly variant = input<'bar' | 'segments'>('bar');
  protected readonly tabs = TABS;
}
