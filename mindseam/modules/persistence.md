# Mindseam Persistence

Train the optional layer that carries the ledger past a single workspace directory. The
ledger (`capacity.md`) is the externalized workspace; persistence is how that externalized
state survives gaps the page cannot bridge on its own — sessions, compactions, and the
transition from one machine or one agent to the next.

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

> I am reading this because the task will outlive this session. I carry the five ledger
> lines, but the page that holds them has a boundary; we need the state to cross it, so
> let's put it somewhere that outlives the directory.

## Grounding

- The controller's ledger is a local text file, `.mindseam/WORKSPACE.md`, written atomically
  by `../scripts/mindseam.py`. It is durable, append-only, and verifier-checked — but it is
  also passive. Nothing extracts, retrieves, deduplicates, or ages it. Re-reading it is
  still a manual step at every seam.
- The failure this layer addresses is measured from the outside: long-horizon agents
  degrade mainly through a context-handling gap, not a reasoning gap. A task that succeeds
  in a short run can collapse once it is embedded in a long interaction history — because
  the state that mattered was never carried forward.
- Persistence is an optional upper layer, not a replacement. The controller stays
  dependency-free and network-free; the five ledger lines remain the source of truth. A
  memory layer sits on top, mirroring those lines so they can be retrieved after the page
  is gone.
- Three gaps justify the layer. A session boundary: the directory survives but the
  conversation does not. A compaction: the middle of the task is summarised away and the
  ledger must be re-anchored. A handover: another agent or another machine picks up the
  task and needs the state, not a re-derivation.
- The mapping is one-to-one. Goal, Core, Verified, Open, Next each become a retrievable
  entry. Verified stays append-only and carries its verifier and coverage; Open keeps the
  test that would settle it. No structure is invented; the five lines are just mirrored.

## Drills

**One.** Name the last task whose middle you lost across a session boundary.

**Pass:** you can name it, and you can name the single line that would have re-anchored it.
**Fail:** you cannot name one. Then find the current task and name the one line that, if
carried, would let a stranger resume it without the conversation.

**Two.** Take your current ledger and read each of the five lines as if they were to be
stored and retrieved by a memory layer.

**Pass:** each line is self-contained — a stranger could read it cold and act on it.
**Fail:** some line depends on context that lives only in this conversation. Rewrite it
until it stands alone.

**Three.** Name one fact in your ledger that is no longer true.

**Pass:** you can name it, and you mark it superseded rather than silently overwriting it.
**Fail:** you can name none, or you would overwrite it without a trace. A store that only
grows and never marks the superseded is drift wearing the mask of memory.

## Protocol

### WHEN TO EXTERNALIZE

1. Open a persistent mirror at the start of any task that will span sessions, compactions,
   or agents. Short single-session tasks do not need it; the page already outlives them.
2. Re-anchor after any long gap — a compaction, a summarisation, a session boundary. The
   ledger survives; the premise and the invariants do not.
3. Externalize at seams, not continuously. Persisting every intermediate is noise; persisting
   nothing is how a long task stops being the task you were given.

### MAP THE LEDGER

1. Mirror the five lines, not a paraphrase. Goal and Next stay scalar; Verified stays
   numbered and append-only; Open keeps its settling test; Core keeps its one defining fact
   per entry.
2. Preserve the verifier and coverage on every Verified entry. A checkpoint without its
   evidence is a claim, not a checkpoint.
3. Keep the source of truth on the page. The memory layer is a mirror; when they disagree,
   the ledger wins and the mirror is corrected.

### RETRIEVE AT SEAM

1. At each seam, read the mirror before re-deriving anything already settled.
2. Retrieve narrowly — the goal, the live core, the last verified line, the open questions,
   the next action. Do not load the whole history.
3. If retrieval returns nothing, treat it as a fresh start, not a corruption. An empty store
   is a new task; a half-remembered store is a trap.

### AGE AND DEDUPE

1. Mark superseded entries rather than overwriting them. Verified is append-only; a changed
   fact gets a new entry and the old one gets a superseded marker.
2. Drop trivia. A store that keeps everything is unsearchable; a store that keeps the
   load-bearing lines is memory.
3. Schedule forgetting at the boundary, not mid-task. Prune only what the current goal no
   longer reads.

## Failure modes

- **Mirror as replacement.** Treating the memory layer as the ledger and letting the page
  drift. Remedy: the page is the source of truth; the mirror is corrected, never trusted
  over the ledger.
- **Store everything.** Mirroring every intermediate so retrieval returns noise. Remedy:
  persist at seams, keep the five lines, drop the middle.
- **Dependency creep.** Wiring the controller to a specific memory service and losing the
  no-dependency guarantee. Remedy: the controller stays standard-library; persistence is an
  optional mirror above it.
- **Silent overwrite.** Replacing a settled fact without marking the old one. Remedy: append
  and mark superseded; rollback needs an address.
- **Unread mirror.** A memory layer that is written but never retrieved. Remedy: retrieve at
  seam is the whole point; a store you never read is not memory.

## Hand-off

| When | Go to | Carry |
|---|---|---|
| The task will span sessions or agents | `capacity.md` | The five lines to mirror |
| A checkpoint must carry evidence | `verification-gate.md` | The verifier and coverage |
| State was lost and must be rebuilt | `../SKILL.md` | The pass and the first action back |
| The mirror disagrees with the page | `self-monitoring.md` | The mismatch, plainly |
| You need the numbers behind the degradation | `../references/mindseam-science.md` | The context gap |
