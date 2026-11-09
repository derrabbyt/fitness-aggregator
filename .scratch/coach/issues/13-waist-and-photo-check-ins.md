# 13: Waist and photo check-ins

**What to build:** Every two weeks the coach asks for the waist measurement and, when photos are on, a photo set, with the photo protocol reminder. What the user sends is stored with its date and acknowledged. Photo review (body-fat estimates) comes later; this ticket makes sure the first sets aren't lost.

**Blocked by:** 05 (Phase start: reverse)

**Status:** ready-for-agent

- [ ] Waist and photo due dates are computed in code from the measurement params and the phase start; reminders are sent once when due (photos only when photos are enabled)
- [ ] The photo prompt includes the protocol: same spot and light, camera at hip height, morning, fasted, unpumped, same poses
- [ ] Photos sent to the coach chat are stored as a dated photo set in the coach's state directory; waist values are stored with their date
- [ ] The weekly report's "due next week" includes waist and photos per the due dates
- [ ] Switching photos off (in chat) stops photo reminders and nothing else changes
- [ ] Tests cover due dates, a reminder sent once, storing a photo set and a waist value, and photos off
