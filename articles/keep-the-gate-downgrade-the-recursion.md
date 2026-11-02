---
title: Keep the Gate, Downgrade the Recursion
published: false
description: "An eight-day A/B gave +0.34% relative add-to-cart, and the offline search behind the candidate gained +0.0036 on holdout. What the recursive-self-improvement label is allowed to mean, and which floor of it was never measured."
tags: ai, machinelearning, architecture, experimentation
---

# Keep the Gate, Downgrade the Recursion

Eight days of a first online A/B, and store-level add-to-cart conversion (P2) was up 0.34% relative. That number is from *基于 RSI 架构的淘宝闪购店铺装修选品 Agent 实践* ("A Store-Decoration Selection Agent for Taobao Flash Sale, Built as RSI").

Source: [基于RSI 架构的淘宝闪购店铺装修选品Agent 实践](https://53ai.com/news/AIdianshang/2026102980739.html) (53AI mirror of the Taobao tech-team article; numbers below were checked against this text on 2026-11-03)

The article says what the number is allowed to mean. It supports a staged business result. Whether several rounds of online experience keep improving the next search still needs its own experiment. Automatic write-back of those results is still being wired up.

The engineering is worth copying. Parameter search is a loop you can audit, stop, and refuse to ship. The phrase "recursive self-improvement" should be lowered by one floor: the floor that has not been measured. A semantic layer is the longer road. It is not finished enough to cross search off the list.

## The engineering is the honest part

The opening already separates two results. Under a fixed budget, CMA-ES gets a higher average holdout score. In the first A/B, P2 is up 0.34% relative. The first supports a local feedback update. The second supports a staged business result. A higher offline score, the article says outright, does not prove a multi-round business gain.

It also says the sentence most write-ups skip. Finishing one generation, finding one high-scoring candidate, and seeing one positive A/B answer different questions. Keeping the baseline when the evidence is thin is a legitimate outcome of the loop. That sentence is in the definition, not in a footnote.

The early evaluator used aggregate features. Swap a product and the score barely moved. Search had nothing to update on. Later the inputs were expanded by slot, then built into Slot Expert. From the slot model to Slot Expert, the article's retention-test R² went from 0.0707 to 0.2341, and MAE from 0.1298 to 0.1166. The article limits those figures to prediction on that architecture log. The eval-set definition is not fully stated. Do not read them as a clean gain across generations.

A swap test covered 1,000 store-days and 3,000 replacements. The input actually changed in 2,754 of them. After calibration, the same-score rate was 7.12%. Most real swaps move the prediction. A tie region remains.

The online gate freezes a candidate, then runs the A/B. "Keep the baseline when the evidence is thin" is first a stated rule. One concrete decision matches it. An automatic boundary round lifted validation ranking by 0.427 percentage points, short of a preset 0.5. In the shared bins, the worst raw MAE got about 18.2% worse, past the tolerance. That round was not adopted, and no extra seeds were added.

On scheduling, rules propose an executable plan first. Qwen may suggest a change only inside an allowed range. If the check fails, the run falls back to the rules. Whether the model earns its call cost over rules alone is listed as a comparison still to run. There is no separate result yet.

The discipline is three constraints. The score has to tell candidates apart. The thing you ship has to be frozen. An update that does not clear the bar has to stop.

## Recursion has two clocks

The article defines recursion this way. This round's evaluation is written into the search distribution, the archive, and the experience store. The next round's candidate generator reads that state. The definition is complete. The evidence splits by clock.

The inner clock is one offline search. The data window and the evaluator stay fixed. CMA-ES updates the sampling distribution from this batch of scores. The next batch is drawn from the updated distribution. The comparison turns off migration, experience guidance, and dynamic scheduling. The only difference is whether feedback updates the distribution. Four categories, 10 paired seeds. Average the categories with equal weight inside each seed, then pair the seeds. Random search gained +0.010593 on holdout. CMA-ES gained +0.014150. The difference is +0.003557, with a 95% paired interval of [+0.002089, +0.005234]. The drinks category alone has an interval that crosses zero. The advantage is in the final candidate, not in speed. The preset bar was the initial score plus 0.002. Mean evaluations to reach it were 5.300 for random search and 6.275 for CMA-ES. In 37 of 40 pairs, both sides had already cleared that bar inside the shared first batch. Inside this budget, updating the distribution buys a slightly better final holdout candidate. It does not show a faster hit, and it does not price multi-island search, migration, or experience one by one.

The outer clock is the business loop. Freeze a candidate, run it online, then let that experience shape the next search. The first A/B covered four categories and about 40,000 stores, split 50:50 by user. Over eight days, store-level P2 was up 0.34% relative (p = 0.0389). Visit-to-order was up 0.46% relative. Store-entry to order was up 0.44% relative. The article is explicit. This is a staged gain for the whole package, in that scope and that window. It does not isolate one weight, one slot, or one search operator, and it is not a long-run result. Automatic write-back is not finished. To test value across rounds, compare "inherit the experience" with "reset the experience": same budget, and the only change is whether past feedback is used. That experiment was not run. The ending leaves it as the open question. Does carrying experience forward beat starting each round clean?

Three sentences cover it. The 0.34% supports a staged gain for the whole package. The inner distribution update has a small offline increment. Cross-round inheritance has no separate evidence. Drop the outer loop and the evaluator, the freeze, the A/B, and the baseline rule still stand. The business number still has an explanation. Drop the inner distribution update and the holdout candidate is lower by 0.003557.

The outer loop can still be worth something over a long horizon, if feedback reliably changes the next set of candidates and the environment is actually drifting. That takes the inherit-versus-reset experiment. It does not follow from an offline score and a single A/B.

## When the outer loop is too much machine

The outer loop is probably too heavy when all of the following are true. Pinned items, capacity, and dedup squeeze the feasible set, so search saturates fast. The catalog, the traffic mix, and preferences move slowly, so one offline tune plus a scheduled review is enough. Eight days bought a 0.34% move, and another slower feedback layer will not wait. Operators have to say why these products, and a searched parameter bundle is often hard to explain. The evaluator is fixed and the window is short, so extra rounds can inflate the model score while the live metric stays flat.

Under those conditions the practical setup is one search inside a budget, a person reading the result, a rerun on a schedule, and the gates this article already built. The swap test and the online A/B are there to stop score-hacking. They also show that closing the loop is not cheap.

What stays fixed is usually the definition of P2, the category structure, and the constraint rules. The catalog, competitors, season, and user preference can move. The system is aimed at that second kind of change: the goal holds, the environment drifts, the strategy has to follow. When drift is fast and the combination space is large, search has a job. What has been measured is the small offline increment on the inner clock, plus one A/B of the whole package. Whatever the outer loop adds over "start clean each round" still has to be measured on its own. The difference between the two setups is drift speed and verification budget.

## Semantics is the longer road

A mature platform is missing a layer that makes products, scenes, constraints, and goals computable. Category and attributes. What pairs, and what substitutes. Traffic and campaigns. Capacity and compliance. Which local changes in P2 can actually be told apart. Once that layer is clear, selection can lean on constrained optimization, rules, and a scheduled recompute.

The article puts the bottleneck on the whole feedback path. If the weights change and the assortment does not, the optimizer has nothing new to try. If the assortment changes and the score gap is not reliable, search has no direction. The early aggregate features were the second failure. Slots and Slot Expert put recent sales, exposure, clicks, add-to-cart, and image clarity on each position, so a local swap can enter the model. That supports a narrower claim: the model has to see the swap. Scene, pairing, intent, and local cause are a longer layer. They cross teams, and they are hard to write as rules. Eight days of online feedback is small and slow. Until the semantic layer exists, a bounded search still has to cover the part you cannot yet tell apart.

Clearer semantics shrinks the space you have to search. Open the 10 exponents and the 2 diversity coefficients as well, and the continuous degrees of freedom reach 66. The article counts a parameter space, not a claim that every run searched every variable. Dedup and capacity sit beside that count. The space does not vanish because the semantics got clearer. Semantics can be the main road. Search stays on the residual that semantics still cannot separate, and that is worth a verification budget. The residual gets smaller. It is still there.

## Rules can take the explicit layer

This is a sketch, not a result from the article.

Explicit conditions fit an inverted index and rules: category, price, stock, time window, past hits. That layer is millisecond-scale and repeatable. Where rules do not cover, a typed judgment with a restricted output can return a probability and a branch. High confidence takes the automatic path. Low confidence goes back to a person or a conservative baseline. The model output does not execute itself.

The article did not test an inverted index plus that kind of judgment API. The sketch is about whether a single decision stays controllable. If the inner search still runs, it still needs an evaluator, a candidate archive, and scheduler state. The two can sit together. A sketch is not a shipped design.

## What to take home

Copy four engineering facts. The evaluator has to see a product swap. Freeze the candidate before the A/B. Stop an update that does not clear the bar. Let rules hold the publish gate. Lower the brand. "Recursive self-improvement" makes 0.34% sound like the accumulated gain of many self-improving rounds.

The inner distribution update has a small offline result. Inheritance across online rounds does not. Semantics is worth building as the main road, and it is not finished enough to delete search. Drop the brand one floor. Keep the loop. Leave the unmeasured floor unmeasured.

---

*A note on sourcing: the article under discussion is in Chinese, published by the Taobao tech team; the linked page is a mirror. Quoted and paraphrased phrasing is my translation, and every number in this piece is reported as the source reports it — including the figures the source itself flags as limited (the retention-test R²/MAE pair and the "predictions on that architecture log" qualifier).*
