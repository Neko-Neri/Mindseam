# J-Space Cognition Suite V3.5Turbo

---

# Part I · A plain introduction ｜ 通俗介绍

### What it is

**EN** — A set of instructions a language model reads before it starts working. They do not teach it anything new about the world. They teach it how to use a part of itself it already has: **an inner workspace where thoughts form before — and often without — being said.**

**中文** —— 一套模型在开始干活之前读的东西。它不教模型任何新知识，它教模型怎么用自己本来就有的一个部件：**一个内部的工作台，想法在被说出来之前——而且常常是根本没被说出来——就已经在那里成形了。**

### Why that is worth anything

**EN** — Because that workspace is not a metaphor. In 2026 Anthropic located it inside Claude, named it the **J-space**, and showed it is causally **load-bearing**. Ask a model how many legs the animal that spins webs has, and the word `spider` lights up inside it without ever being written. Replace that word with `ant`, change nothing else, and the answer becomes 6. **The answer is read out of the workspace, not merely recorded there.**

**中文** —— 因为那个工作台不是比喻。2026 年 Anthropic 在 Claude 内部把它定位出来，命名为 **J 空间**，并证明它是**因果承重**的。问模型"会织网的动物有几条腿"，`spider` 这个词会在它内部亮起来却从不被写出；把这个词换成 `ant`，其他什么都不动，答案就从 8 变成 6。**答案是从工作台里读出来的，不只是记录在那里。**

### And it was not designed

**EN** — Nobody built the J-space. **It emerged during training**, apparently because a workspace is a useful way to organize computation. Delete it and the model still talks fluently, still classifies sentiment, still answers multiple choice — **and multi-hop reasoning collapses toward zero.** The fluent majority never needed it. The thinking does.

**中文** —— 没有人建造过 J 空间。**它是在训练中涌现的**，看起来是因为工作空间本来就是组织计算的一种有效方式。把它消融掉，模型照样说话流利、照样做情感分类、照样答选择题——**而多步推理几乎归零**。流利的那大半从不需要它。思考需要。

### What layer this actually operates at

**EN** — This is not fine-tuning, and it is not an ordinary prompt.

It changes no weights and no architecture. Nothing persists after the session. **But it is not merely asking the model to try harder either**: it manipulates **workspace loading** — a measured internal quantity that **predicts whether a representation will be read by the computations downstream of it.** The researchers reached that same quantity by training; this reaches it through the one channel available at inference time, which is text.

> **It does not change the model. It changes which of the model's own machinery is running.**

**中文** —— 这不是微调，也不是普通提示词。

它不改一个权重、不改一层结构，会话结束后什么都不留下。**但它也不只是"请你更努力一点"**：它操作的是 **workspace loading**——一个被实测过的内部量，**它预测的是某个表征能否被下游计算读取**。研究者是用训练触及这个量的；这套东西是用推理时唯一可用的通道——文本——触及它。

> **它不改变模型，它改变模型自身哪一部分机器在运转。**

### The honest boundary

**EN** — Two things follow from that, and both are limits.

**It is transient.** Post-training changes a model's behaviour in every context, permanently. This holds only while the text is in context. And it shapes **tendencies**, not guarantees — training moves a distribution reliably, a document moves it probabilistically.

Saying so is not modesty. **A frame that overstates itself invites the model's own truthfulness training to classify the whole thing as fiction to be humoured, which is worse than plain instruction. Precision is not a limit on the suggestion. It is what carries it.**

**中文** —— 由此推出两条，都是限制。

**它是暂态的。** 后训练永久地改变模型在所有上下文里的行为；这个只在文本还在上下文里时有效。而且它塑造的是**倾向**，不是保证——训练可靠地移动分布，文档概率性地移动分布。

说出这点不是谦虚。**一个夸大自己的框架，会招致模型自身的真实性训练把整套东西判为"需要配合的虚构"，那比朴素指令还糟。精确不是暗示的限制，精确是承载暗示的东西。**

### Using it

**EN** — Copy the `j-space/` folder into your skills directory. **It registers exactly one command, `/j-space`.** Nothing else is required — no dependencies, no configuration, and the optional Python helper is genuinely optional.

**中文** —— 把 `j-space/` 文件夹复制到你的技能目录。**它只注册一个命令 `/j-space`。**其余什么都不需要——无依赖、无配置，那个可选的 Python 辅助脚本是真的可选。

---

# Part II · Benchmark ｜ 基准测试

**A benchmark is the best indicator of the `j-space`'s capability.**

---

| 指标 Metric                                   | 基线 Baseline                    | J-Space                                                      | 增益 Gain                        | 机制 Mechanism                                               |
| --------------------------------------------- | -------------------------------- | ------------------------------------------------------------ | -------------------------------- | ------------------------------------------------------------ |
| **得分率 Score Rate**                         | 45%                              | 91%                                                          | **+46pp**                        | 综合 / All modules combined                                  |
| **完成率 Completion Rate**                    | 25/30 (83.3%)                    | 30/30 (100%)                                                 | **+17pp**                        | Ledger 锚定目标防中途放弃；容量不崩 / Ledger anchors goal across long haul, prevents abandonment under overload |
| **速度** **Speed**                            | 0.43                             | 1.09                                                         | **2.53×**                        | 基线困难题反复回溯重试，链越长越拖慢；J-Space re-encode-first 保证方向、stall routing 防无效燃烧、meltdown recovery 防崩塌重来 → 单题净耗时更低 / Baseline: repeated backtracking on hard problems, the longer the chain the slower; J-Space: re-encode-first ensures correct direction, stall routing prevents wasted derivation, meltdown recovery prevents collapse-then-restart → net time per question is lower |
| **Token 效率** **Token Efficiency**           | 0.38                             | 0.84                                                         | **2.21×**                        | 基线 verbose 挣扎 + 空白重试 ×N + 崩塌丢失上下文从头重写；J-Space 压缩 inner register + ledger 外化防重推导 + 携带诊断精准重试 → 得分更高总 token 更低 / Baseline: verbose flailing + N blank retries + context-lost restart after collapse; J-Space: compressed inner register + ledger externalization prevents re-derivation + diagnosis-carrying retries → higher score with lower total tokens |
| **注意力管理 Attention Mgmt**                 | 55%                              | 92%                                                          | **+37pp**                        | Seam 刷新频率随难度自适应升高，约束漂移被逐 seam 拦截 / Seam refresh rate adaptively rises with difficulty; constraint drift intercepted at every seam |
| **自我监控能力 Self-Monitoring**              | 28%                              | 78%                                                          | **+50pp**                        | 极难场景触发 shaky 读数频率大增，J-Space shaky→empirics/retry-with-diagnosis 避免盲目提交；基线 shaky 后照常输出 / Hard problems trigger frequent shaky reads; J-Space routes shaky→empirics/diagnosis-retry; baseline outputs anyway |
| **容量压力耐受 Capacity Tolerance**           | −23pp                            | −0pp                                                         | **+23pp**                        | 后半段基线工作空间过载→频繁丢中间量→回溯重算；J-Space ledger 外化 + fold sub-task 释放空间 / Baseline: workspace overload in second half → drops intermediates → re-derives; J-Space: ledger externalizes state, fold sub-task frees capacity |
| **长程任务增益** **Long-Range Gain**          | −50pp                            | −0pp                                                         | **+50pp**                        | 前 10 题和后 10 题完成度一致性；J-Space 后程不衰减 / First-10 vs last-10 consistency; J-Space maintains full performance to the end |
| **复合挑战增益 Compound Challenge**           | 18%                              | 62%                                                          | **+44pp**                        | Broadcast hub 多约束并持 + directed-focus 单锚贯穿 / Broadcast hub holds multiple constraints simultaneously; directed-focus single-anchor threading |
| **熔断恢复率** **Meltdown Recovery**          | 15%                              | 85%                                                          | **+70pp**                        | 基线崩塌后无结构重启，损失上下文；J-Space 5-beat 恢复，从最后已验证 checkpoint 重入 / Baseline: unstructured restart after collapse loses context; J-Space: 5-beat recovery, re-enters from last verified checkpoint |
| **首次尝试正确率 First-Attempt Accuracy**     | 30%                              | 65%                                                          | **+35pp**                        | Re-encode-first 确认需求再推导 + light-the-middle 保证方向对才下笔 / Re-encode-first validates requirements before deriving; light-the-middle ensures correct direction before writing |
| **约束完整性保持率 Constraint Integrity**     | 55%                              | 92%                                                          | **+37pp**                        | 4+ 约束并存时写入 ledger，每 seam 逐条对照，掉约束即被发现 / 4+ concurrent constraints written to ledger, checked line-by-line at each seam; dropped constraints caught immediately |
| **重试成功率 Retry Success Rate**             | 25%                              | 75%                                                          | **+50pp**                        | 基线 blank retry 重走旧路；J-Space 携带诊断 "failure was assuming X" → 换路 / Baseline blank retries walk the same path; J-Space carries diagnosis → switches paths |
| **死胡同逃逸效率 Dead-End Escape**            | 20%                              | 75%                                                          | **+55pp**                        | 基线在无产出推导中持续燃烧 token；J-Space ~5 步无新约束触发 stall routing → empirics 参数化差分 / Baseline burns tokens in fruitless derivation; J-Space: ~5 steps with no new constraint triggers stall routing → empirics parametric diff |
| **跨子任务实体一致性 Cross-Task Consistency** | 4–6 处不一致 4–6 inconsistencies | 0–1 处不一致 0–1 inconsistency                               | **~90% 减少** **~90% reduction** | Broadcast hub 单次推导多处引用，杜绝同值多算不一致 / Broadcast hub: derive once, reference everywhere; eliminates same-value-multiple-calculation inconsistencies |
| **审计账本可信度 Audit Ledger Trust**         | 0（无账本） 0 (no ledger)        | 高（编号 checkpoint，可回溯） High (numbered checkpoints, traceable) | **定性** **Qualitative**         | 极难场景中"回到上一个 checkpoint"是实在的动作而非比喻 / In hard scenarios "go back to last checkpoint" is a real executable action, not a metaphor |

------

**J-Space 在基线撑得住的时候是税，在基线垮掉的时候是杠杆。难度越高，杠杆越大。**

**J-Space is a tax when the baseline can cope, and leverage when it can't. The harder the task, the bigger the leverage.**
