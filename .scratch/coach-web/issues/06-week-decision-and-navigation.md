# 06: Week: decision and navigation

**What to build:** The Week tab shows the check-in week (the 7 days the coach judges), the week in progress by default, with arrows to older weeks. The decision comes first in plain words (hold, +100, −200 and why); an open proposal is shown read-only with its reasoning, guardrail status and when it would apply (no approve / reject / counter on the web); an unusable or skipped week is explained in one line; a week in progress shows what's known without a decision. The coach's full weekly report is collapsed at the bottom.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Coach-core read model `week(iso_week)` with schema, built from the stored check-in (facts, verdict, report) or the facts so far; tests cover a finished check-in with and without a proposal, a blocked proposal, an unusable week, a sport-load week and a week in progress
- [ ] No web action on proposals; the page says decisions are made in Telegram only through layout, not clutter
- [ ] UI with week navigation and the collapsed report; build + screenshots in Comments; tests green
