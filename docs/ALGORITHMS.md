# Algorithms and worked examples

## EWMA

`E_t = alpha * b_t + (1-alpha) * E_(t-1)`, with `E_0 = b_0`.
For alpha=.25, initial burst 8 ms and next burst 16 ms, prediction before observing the second burst is 8 ms; the updated estimate is 10 ms. The project classifies an estimated burst above 4 ms as CPU-bound; this is a configurable-in-code heuristic, not an OS scheduling class.

## Sliding n-grams

For sequence S and order n, `P(g)=count(g)/(len(S)-n+1)`. With S=[1,2,1,2], bigrams are (1,2), (2,1), (1,2): probabilities 2/3 and 1/3. A deque retains the latest 2,048 syscall IDs. New batches connect to previous batches in the same process identity. On expiry, distributions are reconstructed, so expired contributions disappear exactly. Baselines capture the training window and are frozen thereafter.

## Z-score and normalization

`z=abs(x-mu)/max(sigma, abs(mu)*0.1, 0.01)`. Population standard deviation is used. The denominator floor avoids division by zero and excessive sensitivity to nearly constant baselines. With baseline [10,10,10] and x=20, z=10. The component `min(1,z/6)` is therefore 1. This floor is a deliberate robustness adjustment, not a classical pure Z-score.

## Jensen-Shannon divergence

`M=(P+Q)/2`, `JS(P,Q)=0.5 KL(P||M)+0.5 KL(Q||M)` using log base 2 and omitting zero terms. It lies in [0,1]. Identical distributions give zero; disjoint point masses give one. The syscall component averages JS over orders 1, 2, 3. Missing distributions produce zero evidence, not proof of normality; inspect collector health.

## Composite score and state

`A=.25*burst + .20*faults + .15*I/O + .40*syscalls`.
If all components equal one, A=1. If only syscall distribution shifts, A<=.4; the default .55 threshold deliberately requires corroboration. A lone syscall shift can therefore be missed; lower the threshold only after evaluating false positives. At .55, scores [.7,.8,.75] progress WARNING, WARNING, ANOMALOUS. Scores below .33 for three windows enter RECOVERING; six return to NORMAL. Confidence is training completion fraction, not a calibrated probability of maliciousness.

Mahalanobis distance is not implemented: short baselines and unstable covariance would add complexity without defensible calibration.

## Jain fairness

`J=(sum x_i)^2/(n*sum x_i^2)`. For [10,10], J=1; for [10,0], J=.5. Empty/all-zero inputs return 1 as a neutral policy convention. CPU usage fairness is not demand-normalized fairness: a sleeping process may legitimately consume less. The Linux harness also reports fairness from measured cgroup CPU-time deltas across two contending leaves.

## Page replacement

- FIFO evicts the earliest inserted resident page. Hits do not reorder it.
- LRU evicts the resident with the oldest last reference.
- LRU-K retains K most recent timestamps per referenced page (K=2 by default). A resident with fewer than K references is cold and evicted before a mature page; ties use oldest retained timestamp. Nonresident history is retained.
- BARG uses LRU when the last 32 references contain at most `frames` unique pages, and LRU-K otherwise. This is a project-specific locality heuristic, not ARC or a kernel algorithm.

For [1,2,1,3,1] with two frames, FIFO has one hit; LRU and LRU-2 have two. `replacements=max(0,faults-initial distinct resident fills)`. Runtime is the Python simulator's measured wall time; it is not kernel eviction latency.

## Bounded decision

`new_weight = clip(old_weight + clip(target-old_weight,-20,20),50,200)`.
Target=50 for enabled confirmed anomaly response; target=120 for latency-sensitive behavior with J>=.8; otherwise target=100. At weight=100, an anomaly gives 80, then 60, then 50 on eligible cooldown intervals. Recovery reverses toward the normal target gradually. Memory.low moves by at most 8 MiB toward a target in [0,64 MiB]. No routine OOM-inducing memory.max limit is used.
