# 15: Tweaks from the user's review

**What to build:** Two small changes the user asked for after reviewing tickets 02 and 13.

**Blocked by:** 02 (Sync history), 13 (Waist and photo check-ins)

**Status:** ready-for-agent

- [ ] Weigh-in outliers: only clear typos are dropped. `data.weight_outlier_kg` becomes 3.0 (was 1.5); normal spikes stay in the average (the user's scale records every weigh-in automatically). Params, schema/README assumption row and tests updated; the validator stays green.
- [ ] Waist and photo reminders go out the **evening before** the due date, at the user's evening reminder time (setup value), instead of 07:00 on the due date; the message says it's for tomorrow morning (photo protocol: morning, fasted, unpumped). Still once per due date, still counted toward the daily message limit; a missed evening is still reminded once (on the due day). The baseline photo set stays due on the phase start day.
- [ ] Tests cover the new outlier threshold (a 2.5 kg spike stays, a 3.5 kg typo is dropped) and the evening-before reminder.
