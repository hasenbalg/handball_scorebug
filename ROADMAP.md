# Roadmap

Status of feature ideas from the original `todo` list, mapped to GitHub
issues. Rule citations refer to the IHF *Rules of the Game* copies in
[`ref/`](ref/) — see [`ref/RULES.md`](ref/RULES.md) for the digest.

## Done

| Feature | Issue | Notes |
|---|---|---|
| 7-meter shootout mode | — | attempts, sudden death, official protocol + winner confirmation (#15) |
| Horn / buzzer | — | end-of-period signal + manual buzzer on the display |
| Goal animation | — | score pulse + last-scorer flash (#4) |
| Match configuration screen | #10 | match type, half length (2×30/25/20), overtime on/off |
| Automatic clock rules | #11 | referee whistle, auto-stop on suspension (2:8a) |
| Technical timeout | #6 | neutral time-out with 60 s countdown |
| Match log / event timeline | #5 | chronological log in the control panel, exported with the report |
| Player numbers for goals | #4 | optional scorer input, `Goal #23` flash, goals-per-player export |
| Export match report | #12 | CSV + JSON via `/export/report.*` |
| Automatic period transitions | #7 / #10 | OT structure with coin-toss side rules + break timers (10′/5′/1′) |
| Shot clock / passive play | #3 | forewarning toggle + 4-pass counter (7:4 + Clarification 4) |
| Team time-out dots | #1 | 3 per match, 2 per half, none in OT (2:4 Comment) |
| Suspensions on game clock | #13 | tick with the game clock, not wall time (2:8/16:3) |
| Punishment progression | #14 | 3rd suspension = disqualification marker, reduced-team display (16:5) |

## Open

| Feature | Issue | Notes |
|---|---|---|
| Team logos | #8 | upload PNG/SVG next to team names |
| Referee / table mobile mode | #9 | simplified single-purpose UI for phones |
| PDF export | — | PDF half of #12; CSV/JSON already available |
| Time-out quota enforcement options | #1 | currently warn-only flags per 2:4 Comment |

## Deliberately not on the roadmap

- Fully automatic clock operation: handball timing is referee-driven;
  the app computes, suggests, marks and warns, but the operator always
  drives state (see the operator-driven doctrine in the issue tracker).
