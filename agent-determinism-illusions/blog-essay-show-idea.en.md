---
title: "From 'show me your code' to 'show me your idea'"
published: false
description: "Why vibecoding leaves programmers hollow. The work shifted from building to judging, and code lost its authority as the impartial judge. What's left for humans is the part that doesn't refuel them."
tags: ai, llm, essay
series: "AI 时代的判与造"
series_part: 2
canonical_url: ""
---

# From "show me your code" to "show me your idea"

### Why vibecoding leaves programmers hollow

A lot of programmers, in the era of AI writing code, feel a fatigue they can't quite name. It isn't that the workload got bigger — in some ways, writing code got faster. It's that the satisfaction is gone. Before, when you finished typing a section, ran it, watched it work, there was a clear sense of fullness; now, staring at the code AI spit out, judging whether it's right, whether it can be trusted, after a day you feel hollowed out.

This fatigue has a structural cause, and "haven't adapted yet" or "not trying hard enough" can't explain it. Simply put: the work shifted from **building** to **judging**.

## Building vs. judging

"Building" is craft: your hand leaves a mark on something, it goes from not-existing to existing, and at the moment it runs, the feedback is immediate, clear, and yours. Building tires the body but sustains the mind — the feedback it produces refuels you.

"Judging" is governance, and in another sense, "distillation": you aren't building things, you're judging whether things someone else (usually AI now) built can be trusted. Judging is pure consumption: you spend judgment but produce nothing new. There's no creation to refuel on, so the more you do it, the emptier you get.

Before AI wrote code, a programmer's work was a mix of building and judging, but the main body was building — you wrote it yourself, debugged it yourself, watched it run yourself. After AI, the bulk of building got taken over by the machine, and what was left for humans was mostly judging: verifying whether what AI wrote is right, distilling the trustworthy parts, building judgment processes. Judging is inherently boring, no matter how elegant the judging logic. Because it only calls on judgment, not creativity; it's consumption, not replenishment.

This isn't an individual problem, it's a change in the division of labor: AI split "building" and "judging" apart, gave building to itself, left judging to humans. Judging is the leftover work currently assigned to programmers — it needs humans (for now), but it doesn't sustain them.

## show me your code → show me your idea

This shift has a more precise core, hidden in the failure of an old saying.

Linus Torvalds' line "talk is cheap, show me the code" was, for a long time, the ultimate judge: code could kill talk, because code had a machine judge — the compiler, tests, exit codes. No matter how prettily you talked it up, if it didn't run, it didn't run. Code was both the implementation of an idea and the verification of an idea — two things fused into one. "Show me your code" in one phrase both captured your idea and verified your idea.

Vibecoding split this fusion apart. Code got cheap — anyone could get AI to spit code, and spit it more neatly than you. Code lost its function of "proving authorship" — AI could write code that looked right, even code that ran, but that didn't mean it expressed your idea. Code, sitting there, no longer carried trust by default. So judging what someone had made shifted from "what can you write" back to "what are you thinking" — show me your idea.

This is harder, and the hardness has three layers.

First, code has a machine judge, ideas don't. You can't "run" an idea; there's no exit code to tell you if it's right.

Second, ideas can only manifest through talk — written as specs, articles, comments, conversations. But talk happens to be fakeable: an empty idea can be packaged to look deep. This is exactly where "show me your idea" most easily gets swapped out for "show me your talk."

Third, the cruelest layer: AI also talks, and often more "idea-looking" than humans. Once ideas can only be expressed through talk, and AI can mass-produce the talk layer too, then "whose talk actually has ideas behind it" becomes something no machine can adjudicate. In the show-code era, code killed talk; in the show-idea era, code is cheap, and you have nothing in hand that can kill talk — so talk floods, and real ideas and polished fakes mix together, inseparable.

This is what "harder" actually means. It isn't that ideas are harder to think than code (they always were) — it's that **the idea lost its judge**. In the code era, you had an impartial tyrant (the compiler) arbitrating for you; in the idea era, the tyrant has abdicated.

## The engineering response: nailing ideas back to code

Faced with "ideas have no judge," there's an engineering response, even if it only treats the symptom: forcibly nail ideas back to code.

The concrete method is, don't accept any claim that stays at the talk layer — require that every claim be translatable into an executable piece of code that observes a real side effect. If it runs, it's true; if it doesn't, it's false. This method drags judgment from "who sounds right" back to "does it run," and re-summons the abdicated tyrant.

Its value isn't in being perfect — it only covers claims with "observable side effects," and doesn't cover pure design or pure tradeoff ideas. Its value is: where it can be used, it turns unarbitrable talk back into arbitrateable code.

And building this kind of "nailing ideas back to code" machine is itself judging work, itself consumption. It's a cruel loop: the tool you use to fight "judging is too consuming" is itself judging, and consumes you too. But at least it consumes itself in a place with direction.

## The human condition

What's a programmer to do, standing in the middle of this shift. Honestly, there are no cheap answers. But a few things are clear.

First, judging fatigue is real. It isn't an illusion, and it isn't that you're not strong enough. Acknowledging it is the start of handling it. A lot of people are stuck in the guilt between "I should be enjoying the efficiency AI brings" and "why am I so empty" — that guilt alone is stealing what little energy is left.

Second, the yield on this path is non-linear. Judging, accumulating, writing, spacing out — most of the time you feel like you've caught nothing. This isn't you doing it wrong, this is what accumulation-in-progress feels like. Inspiration is a phase transition — long investment, occasional flashes. The people who catch it aren't smarter, they've survived more no-flashlight cycles.

Third, inspiration is caught by letting go, not by gripping hard. Gripping hard is the posture of judging (conscious effort to grasp); the harder you grip, the more it runs. Letting go, spacing out, letting the subconscious connect the materials — that's the posture of building. Guilty spacing out isn't spacing out — guilt means you're still staring at yourself with the judging eye. Relaxed spacing out, letting the default mode network work, is an irreplaceable part of the loop.

Fourth, don't compare yourself to "the masters." The so-called masters aren't people who arrived somewhere you haven't — they're people who caught it a few times and didn't stop. The difference is hit rate and length of persistence, both of which are accumulateable; whereas "catching up to an endpoint" isn't accumulateable, it only makes you tired. Cross out the comparison column, and a little more energy comes back to your hands.

## Finally

Writing this article itself runs a risk: using frameworks like "building vs. judging," "show idea," "nailing ideas back to code" to package a fatigue into a piece that looks deep — that's exactly the behavior this article warns against, the act of talk masquerading as idea. This self-reference can't be eliminated, only acknowledged.

So this article doesn't declare any truth. It's just one person standing in the middle of this shift, trying to translate "why am I so tired" from one person's confusion into the condition of a group. Saying it clearly is the first step in handling it — even if the second after saying it clearly, it gets overturned by a new counterargument. And that overturning is exactly the evidence that it's still alive.

---

*Companion essays: [Judging Fatigue — From Verifying AI to Verifying Myself](blog-essay-judging-fatigue.en.md) · [The Mirror Cannot Reflect Thought](blog-essay-mirror-no-thought.en.md)*
