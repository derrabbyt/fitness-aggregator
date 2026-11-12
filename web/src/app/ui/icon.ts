import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Lucide-style outline icons (ISC), drawn inline. Add a path here to add an icon. */
const PATHS = {
  left: 'm15 18-6-6 6-6',
  right: 'm9 18 6-6-6-6',
  back: 'm12 19-7-7 7-7M19 12H5',
  calendar: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z',
  refresh: 'M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M8 16H3v5',
  check: 'M20 6 9 17l-5-5',
  alert: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 8v4M12 16h.01',
  home: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
  week: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01',
  dumbbell: 'M6.5 6.5v11M17.5 6.5v11M6.5 12h11M3.5 9v6M20.5 9v6',
  sliders: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
} as const;

export type IconName = keyof typeof PATHS;

@Component({
  selector: 'app-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" [attr.stroke-width]="stroke()"
         stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path [attr.d]="d()" />
    </svg>
  `,
  styles: `
    :host { display: inline-grid; place-items: center; width: var(--icon, 20px); height: var(--icon, 20px); flex: none; }
    svg { width: 100%; height: 100%; }
  `,
})
export class Icon {
  readonly name = input.required<IconName>();
  readonly stroke = input(1.75);
  protected readonly d = computed(() => PATHS[this.name()]);
}
