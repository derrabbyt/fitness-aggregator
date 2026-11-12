import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter, map } from 'rxjs';
import { Tabs } from './shell/tabs';

/** The shell: the routed page plus the bottom tab bar (phone). /legacy stands alone. */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet, Tabs],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <router-outlet />
    @if (!legacy()) { <app-tabs variant="bar" /> }
  `,
})
export class App {
  private readonly router = inject(Router);
  protected readonly legacy = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      map(() => this.router.url.startsWith('/legacy')),
    ),
    { initialValue: location.pathname.startsWith('/legacy') },
  );
}
