# Reply draft — nexus-lab-zen (sufficiency vs determinism)

Thread: "Is your agent's 'done' real? A 15-minute self-check before you trust it"
Their 2026-07-30 reply on the freeze-rule field test.

## What they added

Three moves:
1. Field test passed: "drop lines 1–2, keep the rest" → re-derivation matches. Zero degrees of freedom.
2. Contrast to collation miss: "hash the files in sorted order" left collation free; "drop 1–2" has no free parameter. **Determinism of the declaration, not diligence of the checker.**
3. **New distinction** — sufficiency vs determinism. Re-derivation catches ambiguity; it doesn't catch incompleteness. Their placeholder catch worked only because the re-deriving process carried "buyer-facing" intent, not just "drop 2 lines." Closes with: signed ambiguity and signed incompleteness are different failures; the second survives perfect re-derivation.

## My reply shape

Affirm the distinction. Name it by detection method. Point at Phase Gate as the canonical incompleteness-survives-determinism fixture (already in the repo). Tie to boundary-leak-detector pattern (neutral mutation vs defect mutation — opposite polarity). Open question: where does the defect class come from? Same blind spots travel if rule author writes mutations too. Their placeholder catch worked by process asymmetry — the analog to "two independent processes" for ambiguity is "two independent rule authors" for sufficiency.

nexus-lab-zen is the Part 2 / Part 13 reader — binding-map, probe-vs-prose. They know the series. Don't over-explain; peer-level.

Memory checks:
- `feedback_devto_reply_unpublished` — no Part N references. Phase Gate is from Part 1 (published) and apology article. Boundary-leak note is a working note. ✓
- `feedback_single_platform` — dev.to only. ✓
- `feedback_no_absolute_conclusions` — bounded ("the analog to ... is ...", not "always"). ✓
- `feedback_experiment_first` — pointing at existing Phase Gate fixture, not inventing new claim. ✓
- `feedback_chinese_tech_terms` — N/A, English reply.

---

## English (paste to DEV.to)

```text
Naming the asymmetry by how you detect it:

- **Ambiguity** (rule has a free parameter) → re-derive from rule alone, hash-compare. Your collation miss.
- **Incompleteness** (rule is deterministic but under-covers) → mutation: insert known defect classes that should fail; check whether the rule rejects.

Re-derivation catches ambiguity by construction; it catches incompleteness only by accident — when the second process carries a richer implicit contract than the rule. Your placeholder catch is exactly that: the re-deriving process knew "buyer-facing," not just "drop 2 lines." Two processes that share the rule's narrow contract both pass the placeholder untouched.

I have a fixture for this in the series — Phase Gate: `exit_code==0 AND file exists AND file non-empty`. Deterministic, zero degrees of freedom. Output "I am a duck." passes — and would pass any re-derivation under the same rule. Signed incompleteness surviving perfect determinism. The rule covers "action happened"; it doesn't cover "action was right."

So your two-question checklist becomes:

- **Deterministic?** → re-derive (ambiguity detector)
- **Sufficient?** → mutate (incompleteness detector)

These compose with a boundary-leak-detector pattern from another thread in this series: neutral mutations check boundary cleanliness (rename should be no-op); defect mutations check boundary coverage (inserted defect should trigger). Same structural move, opposite polarity. Together they bracket the failure space — leak (lookup in wrong layer), gap (contract the rule doesn't cover), ambiguity (free parameter).

Harder open question on the sufficiency side: where does the defect class come from? If you write the rule and the mutations, both encode your model of "done" — blind spots travel. Your placeholder catch worked because the re-deriving process came from outside the rule author's framing. The analog to "two independent processes" for ambiguity is "two independent rule authors" for sufficiency — much harder, because intent is often tacit. Mutation libraries can catalog known defect classes; they can't generate new ones.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/phasegate-formalism-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/working-notes/boundary-leak-detector-rule.md
```

---

## 中文备忘（不发）

- nexus-lab-zen 是 Part 2/13 的老读者，binding-map、probe-vs-prose 那条线的人；peer-level，别铺垫
- 三步：field test 过 → 对比 collation miss（声明决定性，不是检查勤奋度）→ sufficiency vs determinism 新区分
- 我加的：用检测方法命名两种失败
  - ambiguity → re-derive（构造性抓得到）
  - incompleteness → mutation（构造性抓不到，只能缺陷注入）
- Phase Gate 是 incompleteness-survives-determinism 的典型 fixture：`exit_code==0 ∧ file exists ∧ file non-empty`，零自由度，"I am a duck." 照过
- 跟 boundary-leak-detector 同结构反向极性：neutral mutation（rename 应 no-op）vs defect mutation（注入应触发）
- 三种失败一起 bracket：leak / gap / ambiguity
- 开放问题：mutation 的 defect class 哪里来？规则作者写 mutation → blind spot 跟着走
- 他的 placeholder 之所以被抓，是因为 re-derive 进程带了 "buyer-facing" 这个规则外的意图 —— process asymmetry
- 类比：ambiguity 的检测靠 "两个独立 process"，incompleteness 的检测靠 "两个独立 rule author" —— 后者难得多，意图常常是 tacit 的
- mutation 库能编目已知 defect class，不能生成新的

---

# Round 2 — their reply to the two-detector split (2026-07-30 ~2h later)

## What they added

1. **Confirm split + duck:** re-derivation for ambiguity, mutation for sufficiency; duck passes their old gate too (`file exists + line count matches` = same shape).
2. **May 21 field twin:** inferred content problem from count alone → retracted after reading the file. Proxy certified shape change, not content right.
3. **Close the open question:** mutation catalog is a **burn ledger**. Five current classes all from observed failures; none generated by foresight. "Catalog grows at the rate we ship, not at the rate we think."
4. **Culture common-mode:** author / QA / reviewer are separate processes (≈ two independent rule authors), but same working culture → deepest blind spots plausibly shared. Only generator of genuinely new classes observed: production contact.
5. **Polarity pairing:** taking neutral mutation / defect mutation into their gate design as stated.
6. **Offer:** if Phase Gate fixture series is published, they will run their gates and report which ducks get through.

## Reply shape

Affirm May 21 as the field twin. Accept burn ledger as the honest answer to the open question — quote the ship-rate line as load-bearing. Sharpen: process separation ≠ culture independence (their earlier SoD / common-mode thread, don't rehash). On fixture: don't wait for a write-up series — script is already runnable; welcome their duck report; offer a portable pack if the inline SCENARIOS are awkward to import. No unpublished Part N. Peer-level.

Memory checks:
- `feedback_devto_reply_unpublished` — no Part N. Link only the existing script. ✓
- `feedback_single_platform` — dev.to only. ✓
- `feedback_no_absolute_conclusions` — "the only generator *you've observed*" stays their claim; I don't universalize. ✓
- `feedback_experiment_first` — pointing at existing fixture, not inventing new claim. ✓

---

## English Round 2 (paste to DEV.to)

```text
Yes — May 21 is the field twin of the duck. Same shape of gate, same certified claim ("something happened / the shape changed"), same silence on whether the content was right. Line-count-as-content is incompleteness wearing a deterministic face.

On where defect classes come from: your answer closes the open question more honestly than the framing I offered. "Burn ledger" is right, and the load-bearing sentence is the ship-rate one — the catalog grows at the rate you ship, not at the rate you think. Foresight doesn't mint new classes; production contact does. Mutation libraries catalog the burns; they don't invent the next one.

The author / QA / reviewer split is the right structural move for sufficiency — same shape as "two independent processes" on the ambiguity side. The residual you name is the one that survives SoD: separate processes, shared working culture, shared deepest blind spots. Process separation ≠ culture independence. That matches why the burn ledger outruns the brainstorm — the culture already shared the miss before anyone wrote a mutation for it.

Glad the polarity pairing is going into the gate design as stated.

On the fixture: don't wait for a write-up series. The Phase Gate scenarios are already in the script I linked — four legitimate + four ducks, including the literal duck, under `exit_code==0 ∧ file exists ∧ file non-empty`. If that form is awkward to import into your gates, say so and I'll cut a portable pack (inputs + expected verdicts, no series framing). Either way: run it, and I'll take the report on which ducks get through. That report is more useful than another essay about ducks.
```
