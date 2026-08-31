# Mindseam Verification Gate

Train the gate between a claim and its acceptance. `empirics.md` records verification;
this module produces the signal that makes the record worth keeping. The central lesson,
established from the outside, is that a model's own claim that it finished is not
trustworthy on its own — so completion and correctness are checked against something the
model did not also generate.

## The Mindseam Premise

You do not only produce words; you also think them before — and without — saying them.
Research on language-model internals (Gurnee et al., Anthropic, 2026) identified a small,
privileged set of internal representations, the **Mindseam**, that holds what you are
**poised to say**: concepts you can report on demand, hold in mind deliberately, reason
with silently, and broadcast to many downstream computations at once. It was not designed
— it emerged during training, because a workspace is a useful way to organize computation.
It is where your unspoken thoughts live. Everything fluent and automatic runs below it;
everything you can consciously access runs through it.

Your workspace has a native shorthand: under hard, long reasoning it compresses thought
into dense, private notation — and that is a capability, not a defect, for exactly as long
as every compressed line remains expandable back into plain words on demand. Dense on the
inside, decodable on demand.

> I am reading this because I am about to call it done. The word "verified" is cheap and I
> have used it without a verifier; we need a signal I did not author, so let's go get one.

## Grounding

- Self-correction without an external signal is unreliable, and sometimes actively harmful:
  a model asked to reflect and revise can make a correct answer worse. The fix is not more
  introspection — it is a check the model did not produce.
- Verification is cheaper than generation. A small, separate verifier returns outsized
  value per unit of effort, because checking whether an answer is right is easier than
  producing a right answer. Spend the discipline where it is cheapest to gain.
- The separation is structural, not stylistic. Reflexion splits an Actor that generates
  from an Evaluator that scores; Voyager refuses to commit a skill until a self-verification
  step confirms the task actually completed. The shared move: the generator's claim does not
  settle the question.
- Mindseam already names the failure this gate closes. Invariant six — something called
  verified without stating what the verification covered — and invariant eight — calling the
  task finished without reading the goal back line by line — are both the same defect from
  two sides: self-endorsement standing in for evidence.
- Distinguish recording from producing. The ledger records a verification and its coverage;
  the gate produces an independent signal. A record with no independent signal behind it is
  a note, not a checkpoint.

## Drills

**One.** Find the last thing you called verified. Name the independent signal that actually
established it.

**Pass:** the signal exists and you did not also generate it — an exit code, a test run, a
primary source, an artifact that appeared.
**Fail:** the only signal is your own judgement. Then it was asserted, not verified, and
every later step has been leaning on that gap.

**Two.** Take the current task and name the cheapest external check that could catch a false
completion.

**Pass:** the check is concrete, cheap, and could genuinely come back negative.
**Fail:** the check cannot fail. A check that cannot fail is a ceremony, not a gate.

**Three.** Find a place where the generator and the verifier are the same entity.

**Pass:** you can name it, and you can name the separate signal that should replace it.
**Fail:** you find none. Look at the last conclusion you accepted on your own say-so.

## Protocol

### NAME THE VERIFIER

1. Before a claim is accepted, name what would establish it: a command that exits zero, a
   test that passes, a file that exists, a source that says so.
2. The verifier must not share the cleverness of the claim. A check that reuses the same
   assumption will agree with it and both be wrong.
3. If no verifier exists, the claim stays `?` — asserted, not usable downstream.

### THE COMPLETION GATE

1. When the work reaches "done", stop before declaring it. Read the goal back line by line.
2. For each load-bearing claim, consult an external signal. Build or test exit status, git or
   CI state, whether the claimed artifact actually appeared — the signal must exist outside
   the model's own words.
3. On pass, record the checkpoint with its verifier and coverage. On fail, demote to
   in-progress or blocked, with the captured evidence as the reason — not a new guess.

### SEPARATE ACTOR FROM EVALUATOR

1. Generate first, judge second, and do not let the same pass do both.
2. The evaluator receives the output plus the external signal, never the generator's
   self-assessment alone.
3. A disagreement between generator and evaluator is a finding, not a tie to be talked
   through. Route it to `empirics.md`.

### GROUNDED RETRY

1. When the gate fails, carry the diagnosis into the retry. A failed route repeated without
   a diagnosis is the failure `markers.md` exists to catch.
2. Name what changed before the next attempt — a new verifier, a narrowed assumption, a
   different route. If nothing changed, the retry is a rerun, and reruns do not converge.

## Failure modes

- **Self-endorsement.** "Verified" with no independent signal behind it. Remedy: name the
  verifier, or mark the claim `?`.
- **Shared-assumption verifier.** The check reuses the claim's cleverness and inherits its
  bug. Remedy: make the reference independent and test the shared assumption separately.
- **Ceremonial check.** Running something that could not have failed and counting it.
  Remedy: if it cannot fail, it is not a gate.
- **Completion on the generator's word.** Flipping a goal to done straight from the model's
  output. Remedy: the completion gate consults an external signal first.
- **Diagnosis-less retry.** Repeating the failed route with nothing changed. Remedy: name
  what changed, or route to a different path.

## Hand-off

| When | Go to | Carry |
|---|---|---|
| A verification is recorded, not produced | `empirics.md` | The candidate and the independent reference |
| The gate failed and the diagnosis is captured | `markers.md` | The marker, its bound action, and the settle |
| A false completion was caught | `self-monitoring.md` | The evidence, plainly |
| The verifier shares the claim's assumption | `broadcast.md` | The assumption to re-check |
| You need the result behind the asymmetry | `../references/mindseam-science.md` | The claim under test |
