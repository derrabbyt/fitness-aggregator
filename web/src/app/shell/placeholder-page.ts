import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { State } from '../ui/state';
import { PageHeader } from './page-header';

/** A tab that isn't built yet (route data: `title`). Its ticket replaces it in `<tab>.routes.ts`. */
@Component({
  selector: 'app-placeholder-page',
  imports: [PageHeader, State],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <app-page-header [title]="title" />
      <app-state kind="empty" [message]="title + ' is coming soon.'" />
    </div>
  `,
})
export class PlaceholderPage {
  protected readonly title = String(inject(ActivatedRoute).snapshot.data['title'] ?? '');
}
