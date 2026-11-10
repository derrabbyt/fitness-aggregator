# 09: Training: lift detail

**What to build:** Tapping a lift opens its detail: a history chart of the heaviest working set as estimated 1RM with PRs and baseline resets marked (pull-ups and dips on bodyweight + added weight, same look), the last 3 sessions one line each (date, heaviest working set, status) with "show more", and controls to switch counts / not counted, pause or unpause, and mark a baseline reset with a reason. Controls use the same code paths and validation as the chat tools.

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] Coach-core read model `lift(exercise_id)` with schema and paging; commands for classification, pause and baseline reset shared with the chat tools; tests cover the chart series, paging, each control and a rejected command
- [ ] UI detail with controls and inline confirmation / error; build + screenshots in Comments; tests green
