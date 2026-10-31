# KNOWN_LIMITATIONS.md — honest limits of the final system

1. **The ONNX graph is the decision function ONLY.** Perception
   (BirdObserverV7, GapTrackerV7, the gap finder, the action-history
   counters) is host-side numpy frame processing without learned
   weights. A consumer must implement INTERFACE.md to drive the game;
   the model alone cannot play.
2. **NumPy is a hard runtime dependency** (perception + ORT I/O).
   Full portability beyond Python/numpy/onnxruntime is NOT claimed;
   the package pins and installs its dependencies (clean-room
   verified) instead.
3. **Parity scope**: bit-exact parity is verified for float32 CPU
   executors (onnxruntime 1.19.2 CPUExecutionProvider, single thread,
   and the numpy/BLAS reference). GPU, quantized, or other runtimes
   are NOT claimed.
4. **Perception latch class (open)**: when the bird overlaps a pipe
   column, color-mask observers degrade (the R57 k-analysis,
   `r57_latch_analysis.json`); GapTrackerV7's constant-gap pinning
   mitigates it; the recorded worst-16% y error is ~76 px in that
   regime. Frames-only fix paths (per-column template matching, tiny
   CNN observer) are documented as future work. In the recorded
   episodes this manifests as occasional suboptimal line-holding, not
   a crash.
5. **Heavy-tailed per-seed behavior**: on unseen seeds the policy's
   trajectory is byte-identical to its base on some seeds and
   diverges hugely on others (both directions; e.g. R59 TEST k64 +48
   vs k80 −26). Aggregate claims are aggregate-only.
6. **C1 comparability**: on the R61 fresh 30-seed split the frozen R56
   reference C1 edges the champion (mean 53.37 vs 52.30, W/T/L
   12/11/7 for C1). The champion strictly dominates its own base. No
   all-metrics-superiority claim is made, and this did not reopen
   training (see the R61 closure record).
7. **Razor-edge fragility**: the 87-alive family record is a sharp
   optimum; any weight change (including fine-tunes that look
   harmless) collapses it. The artifact is FROZEN for this reason.
8. **Determinism scope**: byte-exact episode reproduction holds for
   the recorded stack (same machine, same core build, same ISO sha,
   same seed, n-frame budget). Cross-machine byte-identity is NOT
   claimed.
9. **The R57 save incident is documented, not fixable**: the
   mis-saved `r57_es2_dir2p.npz` (32.7% ARS-subspace energy) was
   superseded by the offline reconstruction `r58_dir2p_true.npz`;
   the incident's root cause died with the wiped scratch disk.
10. **hello_pong is a regression gate only** — the pong student is a
    separate artifact with no shared weights; it is not evidence of
    cross-game generalization.
