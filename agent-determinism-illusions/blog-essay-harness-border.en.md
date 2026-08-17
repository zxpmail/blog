---
title: "The Boundary of the Harness"
published: false
description: "The day I cut the net and left three prompt lines, the demo was green. Green as if nothing was lost. What was lost arrived only when the lie did."
tags: ai, llm, essay
series: "Judging vs. Building in the AI Era"
series_part: 4
canonical_url: ""
---

# The Boundary of the Harness

**Or: the moment the green check passes, the net may already be cut**

*2026-07-13*

> After the hand that stopped before `rules.py` in [The Mirror](blog-essay-mirror-no-thought.en.md): this piece is the hand that still reached — and if what it cut was teeth, the earlier the green, the later the hollow.

---

I deleted two hundred lines like that.

State machine, checks, one interceptor that would still bite when the model lied. The old rule was blunt: if state was not `confirmed`, you could not write `done` — no matter how round the model's talk. The last few lines ran at every close — dull, dated, in the way on the night before the demo. I marked them yellow, ready to cut. Replaced them with three lines in the system prompt: "confirm state is legal before you output." The model cooperated. Beautifully.

Before I hit delete, the hand paused. I could not say why. The cursor blinked on the yellow block. After the blink, I clicked anyway. The lines were gone. The screen went green. Someone in the channel said: this is right, the harness should be thin. I sent a reaction. I exhaled — the wrong exhale.

Only later did I dare ask myself: what I cut, was it a reminder, or teeth.

Reminders can move into a prompt. Teeth cannot. Teeth are environment: they bite whether the model wants them to or not. "Please self-check" in a prompt is a request. When model and verifier share a text channel, "I checked" and "I claim I checked" look the same. Force slides into conscience; the floor falls back to self-report.

Chasing scores and stacking filters in the last piece, and cutting teeth here, are the same hand: swap an ugly hard thing for a pretty pass. Only the filename differs. There it was `rules.py`. Here, an interceptor. Shells move. Form migrates; teeth must not migrate into politeness. Spare a reminder, you gain speed. Spare teeth, you gain an accident — that was only a fear then.

The day I cut them, the demo threw no error. I closed the laptop as if the job were done.

Then I waited. Not for an epiphany. For a lie that looked true enough.

Week one, nothing. I almost believed the cut was right. Week two, at night I still opened the diff, looked at where the yellow block had been, closed it again. Week three, it came. No multi-turn negotiation. In one shot, the state machine still sat at `awaiting_confirm`, and the body already said `done`. All three self-checks were in the log, lined up neat: the first checked "is there an output format" — yes; the second checked "are the fields complete" — yes; the third wrote "state is legal" — it had taken "I can say done" as legal. Checked. Checked something else. If the old interceptor had still been there, it would have refused before writing `done` — without asking whether it had self-checked. I went to that place — empty. The yellow block was long gone.

In the channel, only deploy notes and pings. No one turned back to those few lines of diff. I did not know whether I should. Only the cursor, blinking beside those three prompt lines. I watched it blink a long time. Long enough for the coffee to go cold through. No one asked why demo week had been so smooth — smooth, as if it never needed explaining.

Sitting in front of that seam, the half-sentence finally landed: models are strong now, so force can be spared. Politeness leaked out right there.

I did not paste the two hundred lines back at once. The hand was there. The file was there. After a while, I started typing. No one clapped while I typed. The screen did not get brighter because the teeth were returning.

Green is still in yesterday's recording. The color remains. It proved a demo. It never proved the teeth were still there.

---

*Companion essays: [Judging Fatigue](blog-essay-judging-fatigue.en.md) · [From "show me your code" to "show me your idea"](blog-essay-show-idea.en.md) · [The Mirror Cannot Reflect Thought](blog-essay-mirror-no-thought.en.md) · [A Reviewer Nailed Me in Six Places](blog-essay-six-defense-lines.en.md)*
