# Handball Rules — Reference

Authoritative rule documents for verifying scorebug behaviour against the official
rules of indoor handball.

## Sources

| File | Document | Edition | Origin |
|------|----------|---------|--------|
| `rules-en-ihf-2024.pdf` | IHF Rules of the Game for Indoor Handball | 1 July 2024 | ihf.info |
| `rules-de-dhb-2025.pdf` | Internationale Handballregeln (Deutsche IHF-Fassung) | 1. Juli 2025 | dhb.de |
| `_fulltext.json` | Machine-extracted full text of both PDFs (`en`, `de`) | — | extracted with pypdf |
| `_extract.py` | Extraction script (rerun after replacing PDFs) | — | — |

Download URLs (checked 2026-10-27):

- EN: https://www.ihf.info/sites/default/files/2024-07/09A%20-%20Rules%20of%20the%20Game_Indoor%20Handball_E_0.pdf
- DE: https://www.dhb.de/sites/default/files/2025-07/Internationale%20Handballregeln%202025%20(Deutsche%20IHF-Fassung).pdf

## Scorebug-relevant rule digest

Citations are rule numbers from both editions (numbering identical). German edition is
1. Juli 2025 and contains later clarifications; where they differ this is noted.

### Playing time (Regel 2 / Rule 2)

- **2:1** Normal playing time, age 16+: **2 × 30 min**, half-time break normally 10 min
  (max 15 min). Youth: **2 × 25 min** (age 12–16), **2 × 20 min** (age 8–12), break 10 min.
- **2:2** Overtime if tied and a winner is required: after a **5-minute break**, one
  overtime period = **2 × 5 min with 1-min break**; if still tied, a **second** overtime
  period after another **5-minute break** (again 2 × 5 min, 1-min break). If still tied →
  competition-specific; commonly 7-metre throwing.
  - ⚠️ The repo `todo` ("2×5' OT mit 1' Pause dann 7m", issue #2 text) and issue #7
    simplify this; full structure is: HT → 5' break → OT1-h1 (5') → 1' break → OT1-h2 (5')
    → 5' break → OT2-h1 (5') → 1' break → OT2-h2 (5') → 7m.
- **2:3** Playing time starts with throw-off whistle, ends with **automatic final signal**
  of the public clock/timekeeper (= the scorebug's buzzer duty).
- **2:8** Mandatory time-out (game clock stopped) when: a 2-minute suspension or
  disqualification is given; a team time-out is granted; timekeeper/delegate whistle;
  referee consultation. The clock stops **only for the announcement**, NOT for the whole
  duration of a suspension — suspensions run on the game clock.

### Team time-out (Regel 2:4 Comment / Rule 2:4 Comment)

- National federations may allow **three 1-minute team time-outs per match (overtime
  excluded), maximum two per half** of regular playing time. (This matches the "green
  card" system; issue #1 refers to this.)
- Overtime normally has **no** team time-outs (TO excluded in OT under this provision).
- Timekeeper runs a separate clock for the 1-minute TO; at **50 s** an acoustic signal
  announces resumption in 10 s.
- A buzzer button on the official scoreboard may replace green cards; pushing it stops
  the game time directly.

### 7-metre throwing / shootout (Rule 2:2 Comment)

- Only non-suspended, non-disqualified players may participate.
- Each team nominates **5 throwers**; alternating throws; starting team changes after
  each completed sequence of five if still tied.
- Continuation: **new nomination of 5 per round**; winner decided as soon as there is a
  goal difference **after both teams had the same number of throws** (sudden death within
  equal-count rounds — NOT per-throw sudden death).
- Goalkeepers freely chosen/substituted among eligible players; a player may be both
  thrower and GK.

### Punishments (Regel 16 / Rule 16)

- **16:3** 2-minute suspension (Hinausstellung). Timekeeper/scoreboard records them.
- **16:5 + 16:6d** A **third suspension of the same player → disqualification** (red card).
- **16:9/16:8** A player entering the court while serving a suspension gets an additional
  suspension; if it is the third, disqualification; overlapping suspensions reduce the
  team by more than one player.
- Suspensions run on the game clock and carry over across breaks (they are not reset at
  half time or before overtime).

### Passive play (Regel 7 / Rule 7)

- **7:4** Forewarning signal (hand signal 17) shown on passive tendency; attack may still
  change tack. If it doesn't, referees can whistle at any time.
- **Key number: max 4 passes after the forewarning; on receiving the 5th pass without a
  shot on goal → free throw** against the attacking team (Clarification No. 4 details
  exceptions, e.g. 7m/2m situations).
- ⚠️ The repo `todo` item 3 says "6-pass counter" — that is the **pre-2016** rule;
  current IHF (2024/2025) is the 4-pass limit. A passive-play feature should count
  passes **only after the forewarning signal** and cap at 4.

### Scoreboard / timekeeper (Regel 18 / Rule 18)

- Timekeeper duties include: timing playing time and interruptions, running suspension
  clocks, running team time-out clocks, signalling end of periods. A modern scoreboard
  displays: game clock, score, current period, suspended players' numbers with
  remaining time, team time-outs taken, and 7m score during a shootout.

## Notes for audits

- Rule text, comments, hand signals, clarifications and substitution-area regulations are
  all integral parts of the rules (foreword).
- "Guidelines for Playing Courts and Goals" is NOT part of the rules.
- The DE 2025 edition carries yellow (27 Feb 2025 IHF Council) and green (4 Jun 2025)
  highlighted changes effective 1 Jul 2025; e.g. squad size 14 → **16 players** per team.
