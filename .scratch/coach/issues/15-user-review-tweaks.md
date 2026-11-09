# 15: Tweaks from the user's review

**What to build:** Two small changes the user asked for after reviewing tickets 02 and 13.

**Blocked by:** 02 (Sync history), 13 (Waist and photo check-ins)

**Status:** ready-for-agent

- [x] Weigh-in outliers: only clear typos are dropped. `data.weight_outlier_kg` becomes 3.0 (was 1.5); normal spikes stay in the average (the user's scale records every weigh-in automatically). Params, schema/README assumption row and tests updated; the validator stays green.
- [x] Waist and photo reminders go out the **evening before** the due date, at the user's evening reminder time (setup value), instead of 07:00 on the due date; the message says it's for tomorrow morning (photo protocol: morning, fasted, unpumped). Still once per due date, still counted toward the daily message limit; a missed evening is still reminded once (on the due day). The baseline photo set stays due on the phase start day.
- [x] Tests cover the new outlier threshold (a 2.5 kg spike stays, a 3.5 kg typo is dropped) and the evening-before reminder.

## Comments

- No evening reminder time in the setup (it may be null): the reminder goes out on the due day from 07:00, as before.
- A missed evening (coach down, or held back by the daily message limit) is reminded from 07:00 on the due day (not right after midnight), or later in the same period; still once per due date. Late reminders say "Check-in day", not "tomorrow".
- The baseline photo set is reminded on the start day from 07:00 (no evening before: the phase isn't active yet).
- A bare number counts as the waist only from the due day on (unchanged); a value sent the evening before is dated before the due date and wouldn't satisfy it anyway.
