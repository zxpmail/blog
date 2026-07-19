---
title: "Judging Fatigue: From Verifying AI to Verifying Myself"
published: false
description: "I built a verification system to check whether AI's output can be trusted. Then I asked what it was actually for. The answer explained a fatigue I couldn't name for months."
tags: ai, llm, essay
series: "Judging vs. Building in the AI Era"
series_part: 1
canonical_url: ""
---

# Judging Fatigue

**— From verifying AI to verifying myself**

I started with a purely technical question.

I had built this verification system — a setup that checks whether AI-written code can be trusted, whether the claims it makes about itself are actually true. One day it occurred to me: does this count as LLM self-evaluation? That "AI judging AI" thing that, in a lot of discussions, is almost a synonym for "unreliable."

I spent some time pulling the question apart and found that it actually had two dimensions I'd been conflating. One is identity — whether the judge and the judged are the same model. The other is where the judgment lands — does it land on text (reading what the AI wrote and judging that), or on the result of code execution (running a piece of code and watching its side effects)? These two dimensions are independent. My system was working hard to avoid self-evaluation: independent endpoint for the judge (avoiding it on identity), final verdict landing on code execution rather than text where possible (avoiding it on landing).

Pulled apart this way, I thought the question was settled — technically, it isn't self-evaluation, it's a design that deliberately avoids self-evaluation. Fine.

Then I asked a second question: so what is this system actually for?

This one was harder. I started with a harsh self-review: essentially, it used a pile of articles and experiments to rediscover three things old programmers already knew — AI lies, you can't trust everything it writes, you have to run the code yourself and see. Naive enough to be embarrassing. I even suspected that part of the reason I wrote so many articles was that writing articles is more comfortable than writing verification scripts — it looks like "thinking" rather than "bricklaying."

But the accounting showed it had forced something real out. The most critical judgment layer was forced out by a commenter — he pointed out a gap in my design, and that gap made me add an entire layer. Without that article, without that commenter, there would have been no such layer. So it is useful — it's just that its usefulness rests heavily on the scarcity of "nobody else is willing to spend this effort."

Up to here, it was still technical self-examination. Cold, a little harsh, but in a safe zone.

The break happened at the next question.

I asked myself: so what am I actually doing all day?

When the answer came, I froze for a second. What I was doing all day was judging whether AI-produced output was trustworthy — verifying it, distilling it, building processes to judge it. Distilling this, distilling that. Either distilling, or on the way to distilling. I wasn't building things. I was judging things AI had built.

The difference doesn't look large, but it explained a fatigue I hadn't been able to name for a long time. That fatigue wasn't tiredness, it was emptiness. Before, when I finished writing a piece of code and watched it run, there was a real satisfaction, like my hand had left a mark on something. Now, after a day's work, I felt hollowed out. Writing articles, replying to comments, verifying AI — rationally I knew all of this was useful (I'd just done the accounting), but knowing it was useful didn't stop it from being boring. The rational "useful" and the felt "empty" are two different things. I often asked myself: how did I become this. The question had no answer, only more emptiness.

It took me a while to find a structure for this emptiness.

Before, when I wrote programs, I was building. Building was tiring, but it sustained me — the feedback it generated refueled you.

Now I was judging. Judging was pure consumption: spend judgment, produce nothing new. No creation to refuel on. AI took over the bulk of building, left judging to me. Judging needs humans (for now), but it doesn't sustain them. I was placed in the position of "needed, but not nourished."

So I was empty. Not because the workload grew, but because the texture of the work shifted from replenishing to consuming. This wasn't me failing to adapt — it was the structure of the division of labor changing.

Once I understood this layer, the meaning of that earlier technical question changed too. That verification system of mine that worked so hard to "avoid self-evaluation" — it wasn't just a technical design, it was the engineering manifestation of "judging all day." I took judging to its limit, built it into a system. I built a machine specifically for judging, and then I spent all day working inside this machine. No wonder I was empty.

Then I noticed another layer, and this one was colder.

Slowly I realized it wasn't only that my judging felt empty — judging itself had gotten harder. Before, a programmer's work could be verified with a single sentence: "show me your code." Code could kill pretty words, because code had a machine judge — the compiler, tests, exit codes. Code was both the implementation of an idea and the verification of it.

But now code was cheap. AI could mass-produce it, and produce it neatly. Code lost its function of "proving this is yours" — AI could write code that looked right, even code that ran, but that didn't mean it expressed your idea. Code, sitting there, no longer carried trust by default. So judging what someone had made shifted from "what can you write" back to "what are you thinking" — show me your idea.

This was harder. Because ideas had no machine judge, you couldn't run an idea. And ideas could only manifest through words, and words happened to be fakeable — an empty idea could be packaged to look deep. Worse, AI could also write words, and often more "idea-looking" than humans. Once ideas could only be expressed through words, and AI could mass-produce the word layer too, then "whose words actually had ideas behind them" became something no machine could adjudicate.

It wasn't that ideas were harder to think than code (they always were) — it was that ideas had lost their judge. Before, there was an impartial tyrant — the compiler — to arbitrate for you. Now the tyrant had abdicated.

And what I was doing — "landing judgment on code execution" — was essentially a form of resistance: I refused to stay at the word layer, I demanded that every claim be translatable into an executable piece of code that observed a real side effect — if it ran, it was true; if it didn't, it was false. I was forcing the idea that had lost its judge back onto code that had one. This machine wasn't perfect — it only covered claims with observable side effects — but where I could use it, it turned unarbitrable words back into arbitrateable code.

The cruel part was that building this "resistance-judging" machine was itself judging work, and it consumed me too. I was using a judging tool to fight judging fatigue. It was a loop. But at least it consumed itself in a place with direction.

So — standing in the middle of this shift, what to do.

I don't have a cheap answer. But there are a few things I have genuinely thought through — not that thinking them through stops the pain, but that thinking them through is the precondition for starting to handle them.

First, this emptiness is real. It isn't an illusion, and it isn't that I'm not strong enough. For a long time I was stuck between "I should be enjoying the efficiency AI brings" and "why am I this empty" — every day was like explaining to myself why I should be content. That guilt itself was stealing my energy. Comparing myself to masters was the same — I thought writing a few more articles, sitting through a few more blank stares would let me catch up to them, but what it actually stole was exactly the energy needed to catch inspiration. Acknowledging these costs is the first step in handling them.

Second, inspiration is caught by letting go, not by gripping hard. Gripping hard is the posture of judging — the harder you grab, the more it runs. Letting go, emptying out, letting the subconscious connect the materials — that's when it surfaces. But guilty emptiness isn't emptiness — it's just still staring at yourself with the judging eye.

I hesitated writing these things down, and hesitated for a long time. On one hand, using frameworks like "building vs. judging," "show idea," "nailing ideas back to code" to turn an emptiness into a structured piece — that's exactly the behavior this article warns against, the act of using words to masquerade as ideas. On the other hand, laying out these personal confusions carried real exposure: I wasn't sure if it was sincerity, or another form of performance.

I can't resolve either of these doubts, only acknowledge them.

So this article doesn't declare any truth. It's just one person trying to translate "why am I this empty" from a private confusion into the condition of a group. Saying it clearly is the first step in handling it — even if the second after saying it clearly, it gets overturned by a new counterargument.

---

*Companion essays: [From "show me your code" to "show me your idea"](blog-essay-show-idea.en.md) · [The Mirror Cannot Reflect Thought](blog-essay-mirror-no-thought.en.md) · [The Boundary of the Harness](blog-essay-harness-border.en.md)*
