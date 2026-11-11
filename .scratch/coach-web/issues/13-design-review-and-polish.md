# 13: Design review and polish

**What to build:** A finished-build pass: screenshots of every page and detail at phone and desktop width, light and dark, reviewed by a design agent against `docs/design/sure-reference.md` and the direction from 01; the material fixes applied. Also a last check that nothing links to `/legacy` and that the page has no explanatory clutter.

**Blocked by:** 03, 04, 05, 06, 07, 08, 09, 10, 11, 12

**Status:** ready-for-agent

- [ ] Design review (impeccable finish reviewer or equivalent) run on screenshots of all pages; its ordered fix list is recorded in Comments
- [ ] Material fixes applied; final screenshots attached; build and `docker compose run --rm test` green
- [ ] Deployed once with the user's go-ahead and checked by hand on the phone (noted in Comments)

## Notes from earlier tickets

- Ticket 02: `fa-api` logs every proxied `/api/coach/` request at INFO via httpx; quiet the httpx logger in the api (warnings only).
- Ticket 02: freshness is measured as of now, not as of the shown day; fiber target is a range and Home shows its low end — check these read sensibly in the review.
- Ticket 05: skipped planned sessions currently show with a "skipped" flag on Home; hide them instead (they did not happen, and the user wants no status tags).
- Ticket 05: sync re-checks only the last 7 days, so a Hevy session added more than 7 days after its date is never picked up (pre-existing; consider a periodic deeper re-check).
- Ticket 10: the run-discount refusal names the 0–1 share ("run_kcal_discount = 1.5 is outside 0–1") while the web takes a percentage; reword for the web.
