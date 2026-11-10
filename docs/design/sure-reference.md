# Design reference: a Sure-like calm UI for the fitness day view

Source: `ghcr.io/we-promise/sure:stable`, read offline (`/rails/...`). Rails 7 + Tailwind v4
(`@theme`, `@utility`), ViewComponents, Stimulus, D3. Borrow the *language*, never the brand:
no logomark (`logomark-color.svg`), no name, no copy, no icon-assistant glyph.

## 1. Colour tokens (`app/assets/tailwind/sure-design-system/_generated.css`)

Neutral-first: almost everything is gray + alpha black/white; colour is reserved for meaning.
Dark mode is `[data-theme=dark]` on `<html>` (`layouts/shared/_htmldoc.html.erb`, values light/dark/system).

| Role | Light | Dark |
|---|---|---|
| Page bg `surface` | gray-50 `#F7F7F7` | black `#0B0B0B` |
| Card bg `container` | white `#FFFFFF` | gray-900 `#171717` |
| Inset / track `container-inset` | gray-50 `#F7F7F7` | gray-800 `#242424` |
| `surface-inset` (tab track, bar track) | gray-100 `#F0F0F0` | gray-800 `#242424` |
| Text primary | gray-900 `#171717` | white |
| Text secondary (labels, muted) | gray-500 `#737373` | gray-300 `#CFCFCF` |
| Text subdued (placeholder, faint) | gray-400 `#9E9E9E` | gray-400 `#9E9E9E` |
| Border secondary | black @10% | white @20% |
| Divider `tertiary` / `divide-subdued` | black @8% / @5% | white @10% |
| `success` (positive) | green-700 `#078C52` | green-400 `#32D583` |
| `destructive` (negative) | red-500 `#F13636` | red-400 `#ED4E4E` |
| `warning` | yellow-600 `#DC6803` | yellow-400 `#FDB022` |
| `info` / link | blue-600 `#1570EF` | blue-500 `#2E90FA` |
| Primary button | gray-900 bg, white text | white bg, gray-900 text |
| Neutral chart line / "previous" | gray-400 `#9E9E9E` | same |
| Progress track `--budget-unused-fill` | gray-200 `#E7E7E7` | gray-500 `#737373` |

Gray ramp: 25 `#FAFAFA`, 100 `#F0F0F0`, 200 `#E7E7E7`, 300 `#CFCFCF`, 600 `#5C5C5C`, 700 `#363636`.
Black is `#0B0B0B`, not pure black.

**Positive / negative** (`app/models/trend.rb`, `views/shared/_trend_change.html.erb`): a trend has a
`favorable_direction` ("up" or "down"); colour = `var(--color-success)` when the move is favourable,
`var(--color-destructive)` when not, `var(--color-gray)` (#737373) when flat. Rendered as small
`text-sm` mono text: `+12.40 (↑3.1%)` coloured, then the comparison label ("vs. last month") in
`text-secondary`. Spending delta in `pages/dashboard/_spending_trend.html.erb`: negative delta is
`text-success`, zero `text-secondary`, else `text-destructive`. Only the number is coloured, never the tile.
Status badges (`components/DS/pill.rb`): soft pill = tone-50 bg, tone-200 border, tone-700 text mixed 30% black;
dark = tone at 10% alpha bg, tone-200 text.

## 2. Typography

- Family: **Geist** variable (`app/assets/tailwind/geist-font.css`), fallback system-ui; **Geist Mono**
  for figures in trends and weights. `antialiased` on body. Open-licensed (OFL), fine to reuse.
- Only two weights in use: **500 medium** (headings, numbers, list rows, labels) and 400 body. No bold.
- Big number: `text-3xl font-medium` (30px/36px), `-space-x-0.5` (slight negative tracking)
  (`pages/dashboard/_net_worth_chart.html.erb`). Secondary figure: `text-lg font-medium tabular-nums`.
- Page title: `text-xl` on phone, `text-3xl` ≥lg, medium; subtitle `text-sm text-secondary`.
- Card title: `text-base font-medium` (16px). Body / rows: `text-sm` (14px) medium.
- Labels / column headers: `text-xs uppercase font-medium text-secondary` (12px). Bottom-nav label 11px.
- Every number: `tabular-nums` (or `font-mono`) so digits don't jitter.

## 3. Cards: spacing, radii, borders, shadows

- Card (`components/DS/card.rb`): `bg-container rounded-xl shadow-border-xs p-5 flex flex-col`.
  Tailwind v4 defaults apply: `rounded-xl` 12px, `rounded-lg` 8px, `rounded-md` 6px, `rounded-full` pills
  (confirmed in the live compiled `/assets/tailwind-*.css`; the theme's `--border-radius-*` tokens are unused).
- **No real border**: `shadow-border-xs` = `0 1px 2px rgba(11,11,11,.06), 0 0 0 1px rgba(11,11,11,.05)`
  (a hairline ring plus a whisper of shadow). Dark: same with white @8% / @5%. Heavier shadows are
  only for popovers (`.chart-tooltip`: ring + `0 8px 24px rgba(11,11,11,.12)`, radius 10px, padding 10px 12px).
- Grouped list = two layers: an inset frame `bg-container-inset rounded-xl p-1` holding a small uppercase
  header and an inner `bg-container rounded-lg shadow-border-xs` with the rows (`entries/_entry_group.html.erb`).
- Rhythm: dashboard sections `gap-6`; card header `px-4 py-2`; content `px-4`, `space-y-4`;
  rows `p-3` phone / `p-4` desktop. Page gutter `px-3` phone, `lg:px-10`.

## 4. Components

- **Stat tile**: label `text-sm text-secondary`, value `text-3xl`/`text-lg font-medium tabular-nums`,
  delta line under it (§1). Comparison pairs use a `w-1 h-10 rounded-full` colour bar beside each
  figure (current = `bg-success`, previous = `bg-subdued`) instead of boxes (`_spending_trend.html.erb`).
- **Progress bar** (`views/budget_categories/_budget_category.html.erb`): track `h-1.5 bg-container-inset
  rounded-full overflow-hidden`, fill `h-full rounded-full transition-all duration-500`, colour by state:
  `bg-success` / `bg-warning` near limit / `bg-destructive` over. Below it: "Spent: **x**  Budgeted: **y**"
  as `text-secondary` label + `font-medium text-primary` value. Stacked splits use `flex gap-1` of
  `h-1.5 rounded-md` segments (`budgets/_budgeted_summary.html.erb`); 5 tick micro-meter in `_group_weight`.
- **Progress ring** (`components/DS/progress_ring.rb`): 64px, stroke 6, round caps, track gray-200,
  tones success/warning/destructive/neutral (gray-400), centre `%` at size×0.17 px, `role=progressbar`.
- **Line charts**: hand-written **D3 v7** (`config/importmap.rb`; `javascript/controllers/time_series_chart_controller.js`).
  Single 2px line, round joins, coloured by trend colour, fading to gray-400 after a split point; area fill
  is the trend colour at **6% → 0% opacity**; no gridlines, no y-axis; flat series drawn at 1px, 40% opacity;
  fewer than 2 points → dashed gray-300 vertical line + 4px dot (calm empty state). Height `min-h-52` (13rem).
  Tiny static sparkline: `components/DS/sparkline.rb` (336×84 SVG, 1.5px polyline at 70% opacity,
  r=3 dots, hollow for zero, 9px labels at 50% opacity, colour via `currentColor`).
- **Lists**: rows `flex items-center justify-between text-sm font-medium`, name left, amount right,
  meta line `text-xs text-secondary` underneath; group header `text-xs uppercase text-secondary`
  "DATE · count" with the day total right-aligned. Positive amounts `text-green-600`, others plain primary.
- **Tabs / segmented** (`components/DS/tabs.rb`, `segmented_control.rb`, `components.css`): pill track
  `bg-surface-inset p-1 rounded-lg`; segment `text-sm font-medium px-2 py-1 rounded-md`; active =
  white (dark gray-700) + `shadow-sm` + primary text; inactive `text-secondary`. Equal widths on phone.
- **Bottom navigation** (`views/layouts/application.html.erb`, `layouts/shared/_nav_item.html.erb`):
  `lg:hidden fixed bottom-0 inset-x-0 bg-surface border-t border-tertiary flex justify-around
  pb-[env(safe-area-inset-bottom)]`; up to 6 items; each = 32px icon square (active: `bg-container
  shadow-xs text-primary`), 11px medium label, plus a 16×4px black indicator bar on the top edge
  (`bg-nav-indicator`, white in dark). Main content reserves `pb-[calc(5rem+env(safe-area-inset-bottom))]`.
  Icons: Lucide outline, 1.5–2px strokes.
- **Empty state** (`components/DS/empty_state.rb`): centred `px-4 py-12`, icon (xl) `mb-4`, title
  `text-primary font-medium`, description `text-secondary text-sm max-w-md`, optional single action.
  Inside a chart area: just `text-secondary text-sm` centred in the same height (no layout jump).
- Loading: `bg-surface-inset animate-pulse` blocks (`bg-loader` utility); syncing values pulse.

## 5. Mobile behaviour

Mobile-first; `lg` (1024px) is the only real switch: top bar (menu, centred mark, actions) + bottom
nav on phone, left rail + sidebars on desktop. Safe-area insets on top bar, bottom nav and sheets.
Touch targets grow with `pointer-coarse:w-11 h-11` (44px). Primary "add" becomes a round icon button
on phone. Card grid is one column until `2xl`. Wide tables scroll inside `.table-scroll` with edge
shadows; columns hide below `md` and meta collapses to one secondary line. Sections can collapse.

## 6. Why it feels calm: rules

1. One accent per meaning: grays everywhere, green/red/amber only on the number or bar that carries the verdict.
2. Hairline ring + 6% shadow instead of borders; page bg one step darker than cards (gray-50 vs white).
3. Two weights only (400/500) and one big number per card; everything else is 12–14px.
4. Labels are quieter than values (`text-secondary`, often uppercase 12px); values medium and tabular.
5. Charts are a single thin line with a 6% wash: no grid, no axis lines, no legend boxes.
6. Thin, rounded meters (6px bars, round caps), tracks barely tinted.
7. Generous, uniform rhythm (p-4/p-5, gap-4/6) and consistent radii (12 card / 8 inner / full pills).
8. Empty and loading states keep the same footprint and say one short sentence.

## 7. Adapting to the fitness day view (Angular, plain CSS)

- Port tokens as CSS custom properties on `:root` + `[data-theme=dark]` (and a `prefers-color-scheme`
  fallback); write small classes (`.card`, `.label`, `.value`, `.meter`) instead of Tailwind.
- Day header: date + `text-xl` title, segmented control for Day / Week. Hero tile: calories eaten vs
  target as `text-3xl` value, `of 2,400 kcal` in secondary, 6px meter below.
- Macros: three rows (protein, carbs, fat) each with label/value and a 6px bar; colour by state against
  target (on track = success, near = warning, over = destructive) where "favourable" depends on the
  macro (protein under target is the warning, not fat over). Keep a `favorableDirection` per metric.
- Weight / sleep / volume trends: one D3 (or tiny hand-rolled SVG) line, 2px, 6% fill, no axes;
  trend line in secondary text below (`−0.4 kg (↓0.5%) vs. last week`).
- Meals and workout as grouped lists (inset frame, uppercase "BREAKFAST · 3" header with kcal total,
  rows name → kcal right). Hevy sets as `text-xs text-secondary` meta lines.
- Bottom nav with 3–5 items (Today, Trends, Coach, …), same indicator bar + safe-area padding.
- Use Geist (OFL) or system-ui; Lucide icons (ISC) are fine.

**Do not copy:** Sure's logos, name, colours of its brand mark, illustrations, copy text, the AI
assistant icon, privacy-mode blur, drag-to-reorder dashboard, sankey/donut finance widgets, desktop
three-pane sidebars, or its exact component markup. Don't use red for "ate less than target"
reflexively; judgement colour must follow the metric's goal.
