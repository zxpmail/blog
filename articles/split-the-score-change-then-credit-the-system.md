---
title: Split the Score Change, Then Credit the System
published: true
canonical_url: https://dev.to/zxpmail/split-the-score-change-then-credit-the-system-267j
description: "How the round-over-round score change splits into an environment term and a learning term. The method is one re-scoring of last round's deployed candidate per round. Over 100 paired seeds, the misattribution rates vary with the direction and speed of environment drift; 14% under slow random drift. The rates belong to this toy and do not transfer."
tags: ai, machinelearning, experimentation, statistics
---

# Split the Score Change, Then Credit the System

Picture a system that regenerates a plan and deploys it every round: product selection, parameters, scheduling all qualify. At the end of each round it receives a score — conversion, click-through, any business metric. When such a system is said to be "self-improving," the evidence is usually this: this round's score stands above last round's.

But a rise or fall has two sources. The plan actually got better. Or the environment changed — the same shelf earns differently this week and next; the goods did not change, the shoppers and the competition did. From the change alone, the two sources cannot be told apart.

This piece does three things. First, it gives the split: the difference between two rounds' scores equals an environment term plus a learning term — the environment term is the effect of the environment changing, the learning term is the effect of swapping the plan — and one extra evaluation per round computes it online. Second, it measures how wrong the un-split number gets, in a toy with known ground truth over 100 paired seeds: when the environment moves fast enough, more than nine seeds in ten show a falling score with a positive learning total; under fast movement in the plan's favor, half of all seeds show a rising score owed mainly to the environment; under slow random drift, 14% of seeds have the environment total exceed the learning total. Third, it lists the conditions the split needs to hold online.

The conclusion up front: the sign of the round-over-round difference is by itself neither evidence that the system learned nor evidence that it failed. What to read are the two terms.

Two sentences of background. The previous piece, [Keep the Gate, Downgrade the Recursion](https://dev.to/zxpmail/keep-the-gate-downgrade-the-recursion-2ml0), checked an article by the Taobao Flash Sale team about a store-decoration selection system, which included an eight-day A/B with a +0.34% relative lift (P2). That comparison ran candidate against baseline over the same stretch of time, split 50:50 by user, with the environment on the same side for both — it is not exposed to the confusion this piece discusses, and this piece does not estimate the environment's share in it; the number carries over from the previous piece's check. The comment thread under that piece left a question open: online, how do you tell "the experience helped" apart from "the environment happened to move our way"? This piece supplies that measurement.

## The score change is the sum of two terms

Write the scoring terrain as T, the incumbent — the currently deployed plan — as x, and the evaluator as f, so f(T, x) reads: the score of plan x on terrain T. The raw change is this round's reading minus last round's:

naive(t) = f(T_t, x_t) − f(T_{t−1}, x_{t−1}).

It equals the sum of two terms.

The environment term: the environment changed, the candidate stayed where it was.

env(t) = f(T_t, x_{t−1}) − f(T_{t−1}, x_{t−1}).

The learning term: the candidate was swapped, the environment held at this round.

search(t) = f(T_t, x_t) − f(T_t, x_{t−1}).

The identity naive = env + search holds algebraically. What is missing, to compute it, is the middle reading: last round's candidate, scored on this round's terrain. Online, that is one extra evaluation per round — re-score the candidate deployed last round under today's evaluator.

A frozen candidate is read alongside. It stops searching after deployment and only takes readings. Its readings carry no learning term; they measure the environment alone.

The re-score is charged to the system's own budget. From round 2 on, each round has 48 evaluations: one incumbent re-score, plus 47 fresh samples. The evaluation spent on the re-score is one the system does not search with.

## Three arms and a drift, inside the toy

The terrain and the searcher are the same family as inherit-versus-reset in the previous piece. The settings needed for reproduction: 6 dimensions, 12 Gaussian bumps, bump width 0.18, box [−1, 1]. The score is the maximum of the bumps at the point, with no observation noise. The searcher is a (4, 12) evolution strategy with a 1/5 step rule. Six rounds, 100 paired seeds. The three arms inside one seed share one terrain and one drift trajectory.

Round 1 is identical across arms: one evaluation at the start, then 48 samples. The deployed point is x_1. From round 2 on, the deployed arm and the reset arm each spend 48 per round: one opening evaluation, then 47 fresh samples.

The deployed arm carries its search state into the next round. A challenger replaces the incumbent only if it scores higher on today's terrain. The learning term on this arm is therefore greater than or equal to zero in every round. A candidate already seen as worse is not swapped in.

The reset arm searches from scratch each round. Its one opening evaluation is symmetric with the deployed arm's incumbent re-score; both are charged inside their own 48.

The frozen arm searches only in round 1, then reads x_1 and spends no search budget.

At every round boundary, the scoring terrain shifts by one step; this movement is the drift. The drift starts at the boundary of round 2. Each bump moves along a unit direction by a step of δ, reflecting off the box walls. The direction is fixed at the first boundary and never changes after.

Three settings of direction.

Favorable drift, meaning it benefits the deployed plan: each bump points from its own center toward x_1. The reference point is the point deployed in round 1. Once the direction is fixed, it does not follow later incumbents.

Adverse drift, the opposite: each bump points away from x_1.

Random drift: the direction is drawn once per seed and then fixed. It is not aimed at x_1.

δ takes 0.04, 0.16, and 0.48, plus one setting with no drift at all. Relative to the bump width 0.18, the three steps are about 0.22, 0.89, and 2.7 bump widths. By round 6, the cumulative displacement without reflection is 5δ.

## Expectations written into the script before the run

Five expectations were written into the script's docstring, before this run.

1. Under favorable drift at δ=0.48, the frozen arm's mean peak (highest reading over the six rounds, minus its start) is greater than 0, with a 95% interval excluding 0.
2. At δ=0.48, the false-rise rate under favorable drift exceeds that under adverse drift, and the false-fall rate under adverse drift exceeds that under favorable drift. Both comparisons are paired by seed, with the interval of the difference excluding 0.
3. The identity residual, in every cell and every round, is below 1e-9.
4. At zero drift, the environment term and the frozen arm's change are 0 seed by seed, and the naive total equals the learning total, within 1e-12.
5. A soft expectation, not counted toward pass or fail: in some random-drift cell, the false-rise rate is greater than 0.

The first four held. The fifth met its own passing line. That line only requires greater than 0. The random-drift false-rise rates across the three cells are 14%, 2%, and 0% (δ from small to large). Greater than 0 appears in the first two cells; the δ=0.48 cell is 0.

The zero-drift row caught two pairing errors — subtractions between readings that did not belong together — while the script was being built. The numbers below come from the run after the fixes. This row is what checks the instrument itself.

## Illusions counted per seed, not spread across rounds

Each seed is first summed over rounds 2 through 6, then reduced to a yes or a no. A cell has 100 seeds and therefore 100 such verdicts. The intervals are bootstrap percentile intervals over these 100 numbers, resampled 2000 times, at 95%. The per-seed arrays are kept in the results JSON.

False rise illusion: the naive total is greater than 0, and the environment total exceeds the learning total.

False fall illusion: the naive total is less than 0, and the learning total is greater than 0.

The learning term on the deployed arm is never negative. False fall therefore mostly says: the naive total is negative, and this seed replaced its incumbent at least once in the five rounds. At large drift the rate runs high; the main cause is that the environment term is almost always negative. The replace-only-if-better-today rule sets which seeds qualify — learning above zero is equivalent to at least one replacement — it does not push the rate up itself. What the pre-registration compares is the difference between drift directions.

## Readings by cell

Two things get established in this section. First, the score can be pushed up by environment movement alone: under favorable drift at δ=0.48, a candidate that never searched again after deployment peaked +0.858 above its start. Second, once the environment moves fast enough, a falling score is the default state while learning is still happening: at δ=0.48, under adverse and random drift, more than nine seeds in ten end with a negative naive total and a positive learning total. The remaining paragraphs are the boundaries and corroboration of these two sentences.

The frozen peak is the frozen arm's highest reading over the six rounds minus its start. The frozen end is the round-6 reading minus the start. The naive, environment, and learning columns are seed means of the deployed arm's five-round totals, rounded to three decimals. Subtracting the learning column from the naive column in the same row may differ from the environment column by 0.001; that difference is rounding, not a mistake.

| drift | δ | frozen peak | frozen end | naive total | env total | search total | false rise | false fall |
|---|---|---|---|---|---|---|---|---|
| — | 0 | 0 (exact) | 0 (exact) | +0.472 | 0 (exact) | +0.472 | 0% | 0% |
| adverse | 0.04 | 0 | −0.073 | +0.337 | −0.133 | +0.470 | 0% | 15% |
| random | 0.04 | +0.013 | −0.022 | +0.429 | −0.079 | +0.508 | 14% | 2% |
| favorable | 0.04 | +0.292 | +0.292 | +0.552 | +0.061 | +0.491 | 30% | 0% |
| adverse | 0.16 | +0.001 | −0.078 | −0.048 | −0.376 | +0.328 | 3% | 78% |
| random | 0.16 | +0.016 | −0.077 | −0.035 | −0.523 | +0.488 | 2% | 54% |
| favorable | 0.16 | +0.791 | +0.377 | +0.261 | −0.199 | +0.460 | 22% | 13% |
| adverse | 0.48 | +0.005 | −0.078 | −0.068 | −0.142 | +0.075 | 4% | 91% |
| random | 0.48 | +0.015 | −0.078 | −0.074 | −0.287 | +0.213 | 0% | 95% |
| favorable | 0.48 | +0.858 | +0.468 | +0.332 | +0.050 | +0.282 | 50% | 20% |

In the zero-drift row, both illusion rates are 0, and the naive total equals the learning total seed by seed. Across all cells, the largest identity residual is about 1.1e-16.

Under favorable drift at δ=0.48, the frozen arm's peak is +0.858 above its start, interval [+0.836, +0.879]. The point is x_1, unmoved since deployment. The bumps were pushed toward where it sits; the rise in the reading comes from the terrain. Under adverse drift at the same speed, the peak is +0.005 [+0.002, +0.009], and the end is −0.078.

The adverse cells all end below their start, at about −0.07 to −0.08. Their peaks sit near 0 or slightly above. The peak is the highest point across the six rounds; after a bump reflects off a wall, it can pass near x_1 again.

This toy has no observation noise; all movement on the frozen arm comes from the terrain. Live readings carry noise. Taking a maximum over several noisy rounds biases the result upward. The identity uses per-round endpoint readings. The peak only says where the frozen arm got to across the six rounds.

Favorable drift pushes the bumps toward x_1, and the frozen arm stands on x_1. The deployed arm leaves that point. Under the same favorable setting, the environment term on the incumbent can be negative.

Favorable at δ=0.16 is such a case. The deployed arm's environment total averages −0.199, interval [−0.283, −0.113], excluding 0. The learning total is +0.460, the naive total +0.261. The cell is named favorable, and the incumbent's environment account is a deduction on average.

Under favorable drift at δ=0.48, the environment total averages +0.050, interval [−0.058, +0.157], including 0. The learning total averages +0.282, above the environment total. The false-rise rate in this cell is 50% [40, 60]. The 50% says: in half the seeds, the environment total exceeded the learning total. That is not the same sentence as "the mean of the environment column exceeds the mean of the learning column." In this cell, the learning column's mean is larger.

The pre-registered comparisons hold at δ=0.48. The false-rise rate under favorable drift exceeds adverse by 0.46 [+0.35, +0.56]. The false-fall rate under adverse drift exceeds favorable by 0.71 [+0.62, +0.80].

Random drift does not aim at x_1. At δ=0.04, about 0.22 bump widths, the false-rise rate is 14% [8, 21]. The cell's naive total is +0.429, learning total +0.508, environment total −0.079. On most seeds, the naive sign matches the learning sign. The 14% are the false-rise seeds.

As δ grows, random drift takes another shape. At δ=0.16, about 0.89 bump widths: naive total −0.035, learning total +0.488, false fall 54% [44, 64]. At δ=0.48, about 2.7 bump widths: naive total −0.074, learning total +0.213, false fall 95% [90, 99], false rise 0. These δ are already at the terrain's own scale.

One more item was not in the pre-registration. It is the deployed arm's round-6 score minus the reset arm's round-6 score, asking whether carrying search state to the next round was worth anything.

At zero drift the difference is +0.457 [+0.381, +0.537]. At δ=0.04, all three drift settings sit roughly between +0.34 and +0.53. Beyond that:

| drift | δ=0.16 | δ=0.48 |
|---|---|---|
| adverse | −0.022 (interval crosses 0) | −0.099 [−0.126, −0.074] |
| random | −0.041 [−0.061, −0.021] | −0.071 [−0.090, −0.053] |
| favorable | +0.091 [+0.025, +0.156] | +0.287 [+0.212, +0.363] |

Adverse and random drift fall to around zero or below; under favorable drift the difference stays positive. This prices no component of a production system and no real experience store.

## Conditions that must hold to carry this online

Inside the toy, the middle reading is given directly by the simulator, so the identity is exact. Carried online, the same subtraction needs all three of these.

Both readings use the same ruler. If the evaluator changed versions between rounds, the ruler's change enters the environment term. Record the evaluator version next to every reading.

Last round's deployed candidate must stay measurable. It is either still live, or replayable through the current evaluator exactly as it was frozen.

The re-score is charged to the system's budget. A re-score placed outside the budget adds samples to the system.

The reset control asks whether search state should carry to the next round. The split asks, of this round's increment, how much came from the environment and how much from replacing the candidate. Both fit inside one six-round run. The real cross-round A/B on real business was not run here and was not run in the previous piece.

The remaining conditions are recorded here. The terrain is a toy, the score is a maximum of bumps, there is no A/B gate, and there is no business noise. The percentages in the table belong to this toy and these δ. δ is a length relative to the bump width 0.18; under another ruler it does not carry over.

## Conclusions

Three conclusions.

The split works, and it is cheap. The round-over-round difference equals an environment term plus a learning term; filling in the middle cell online costs one incumbent re-score per round plus one reading of a frozen candidate, both charged to the budget.

The un-split score misattributes at measurable rates when the environment moves. Under fast movement in the plan's favor (δ=0.48), half of all seeds show a rising score owed mainly to the environment; under adverse and random drift, more than nine seeds in ten end with a falling score and a positive learning total; under slow random drift, 14% of seeds have the environment total exceed the learning total. The rates belong to this toy; the shape belongs to any environment that moves. Under slow drift, most seeds' naive sign still matches the learning sign — the rate moves with speed, the confusion does not vanish.

So the sign of the round-over-round difference is by itself neither evidence that the system learned nor evidence that it failed; when the environment moves, it mostly reflects the environment. What to read are the environment term and the learning term. Back to the question the comment thread left open — how to tell *the experience helped* apart from *the environment happened to move our way* — the answer is the measurement itself: with it, the two questions separate; without it, the rise and fall stays unattributed.

---

The full run is at [scripts/ratchet-attribution-test.py](https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/ratchet-attribution-test.py). The results JSON keeps per-seed arrays for every cell. The rates and intervals above can be recomputed from the raw trials.

*A note on sourcing: the article under discussion is in Chinese, published by the Taobao tech team; the linked page is a mirror. The relative P2 +0.34% cited here was checked against the source text during the previous piece; see that piece's sourcing note.*

*The numbers come from the same run as the Chinese draft, and the sections correspond one to one.*
