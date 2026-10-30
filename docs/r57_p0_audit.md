# R57 P0 — provenance audit + seed splits

Base commit: `2d2c41e` · 70 files hashed · 22 model sidecars.

## The 20-pipe qualification verdict

Every historical training set contains teacher labels beyond
pipe 20 (measured teacher pipes per life: k6=51, k12=38, k30=37, k45=30, k60=38, k90=34, k120=34, k210=34).
Therefore **no historical checkpoint qualifies** as the R57
bootstrap student: p6v7h128 (R55), C1, C2, C3, C4 and the p7v7
family all remain frozen historical references only. The
bootstrap must be newly collected under the cap.

## Checkpoints

| artifact | bytes | feature_version | teacher provenance | verdict |
|---|---|---|---|---|
| `flappy_student_feat_p4sf4.npz` | 992 | 4 |  | historical-only (labels > pipe 20) |
| `flappy_student_feat_p5v7.npz` | 1134 | 7 | behavior cloning on the teacher's own recorded flight (tv7n traces) | historical-only (labels > pipe 20) |
| `flappy_student_feat_p5v7d1.npz` | 1159 | 7 | behavior cloning on the teacher's own recorded flight (tv7n traces) +  | historical-only (labels > pipe 20) |
| `flappy_student_feat_p6v7.npz` | 1149 | 7 | behavior cloning on the teacher's own recorded flight (tv7n traces) | historical-only (labels > pipe 20) |
| `flappy_student_feat_p6v7f.npz` | 1165 | 7 | behavior cloning on the teacher's own recorded flight (tv7n traces) +  | historical-only (labels > pipe 20) |
| `flappy_student_feat_p6v7f128.npz` | 1164 | 7 | behavior cloning on the teacher's own recorded flight (tv7n traces) +  | historical-only (labels > pipe 20) |
| `flappy_student_feat_p6v7g.npz` | 1168 | 7 | behavior cloning on the teacher's own recorded flight (tv7n traces) +  | historical-only (labels > pipe 20) |
| `flappy_student_feat_p6v7h128.npz` | 1149 | 7 | behavior cloning on the teacher's own recorded flight (tv7n traces) | historical-only (labels > pipe 20) |
| `flappy_student_feat_p6v7h96.npz` | 1150 | 7 | behavior cloning on the teacher's own recorded flight (tv7n traces) | historical-only (labels > pipe 20) |
| `flappy_student_feat_p7v7h128.npz` | 1043 | 7 | BC on the tv8 teacher lives (8 seeds incl. k12/45/120) | historical-only (labels > pipe 20) |
| `flappy_student_feat_p7v7h128w1.npz` | 1092 | 7 | BC on the tv8 teacher lives (8 seeds incl. k12/45/120) + 2 r56b surgic | historical-only (labels > pipe 20) |
| `flappy_student_feat_p7v7h128w2.npz` | 1089 | 7 | BC on the tv8 teacher lives (8 seeds incl. k12/45/120) + 2 r56b surgic | historical-only (labels > pipe 20) |
| `flappy_student_feat_p7v7h128w3.npz` | 1087 | 7 | BC on the tv8 teacher lives (8 seeds incl. k12/45/120) + 2 r56b surgic | historical-only (labels > pipe 20) |
| `flappy_student_feat_p7v7h192.npz` | 1044 | 7 | BC on the tv8 teacher lives (8 seeds incl. k12/45/120) | historical-only (labels > pipe 20) |
| `flappy_student_feat_p7v7h192w1.npz` | 1091 | 7 | BC on the tv8 teacher lives (8 seeds incl. k12/45/120) + 2 r56b surgic | historical-only (labels > pipe 20) |
| `flappy_student_feat_p7v7h192w2.npz` | 1088 | 7 | BC on the tv8 teacher lives (8 seeds incl. k12/45/120) + 2 r56b surgic | historical-only (labels > pipe 20) |
| `flappy_student_feat_p7v7h192w3.npz` | 1088 | 7 | BC on the tv8 teacher lives (8 seeds incl. k12/45/120) + 2 r56b surgic | historical-only (labels > pipe 20) |
| `flappy_student_feat_r56_c1.npz` | 1033 | 7 | BC on the tv8 teacher lives [6, 60] | historical-only (labels > pipe 20) |
| `flappy_student_feat_r56_c2.npz` | 1039 | 7 | BC on the tv8 teacher lives [6, 60, 12, 120] | historical-only (labels > pipe 20) |
| `flappy_student_feat_r56_c3.npz` | 1098 | 7 | BC on the tv8 teacher lives [6, 60, 12, 120] + the r56b walkback corre | historical-only (labels > pipe 20) |
| `flappy_student_feat_r56_c4.npz` | 1209 | 7 | BC on the tv8 teacher lives k6+k60 (the r55 champion recipe) + the r56 | historical-only (labels > pipe 20) |
| `pong_student_feat_p4d4.npz` | 1721 | 2 |  | historical-only (labels > pipe 20) |

## Seed splits (committed before collection)

- TRAIN (bootstrap demos, capped): [6, 30, 60, 12, 45]
- VAL: [90, 210] (all historical seeds demoted to VAL)
- TEST (never booted before this round): [8, 16, 20, 28, 33, 40, 48, 57, 63, 72, 84, 96, 108, 111, 117, 132, 141, 156, 165, 180, 195, 201, 216, 228] (24 seeds, n=3 boots each, retired after the final eval)
- History-set (never TEST): [6, 12, 18, 24, 30, 36, 42, 45, 54, 60, 66, 78, 90, 100, 102, 114, 120, 126, 130, 150, 174, 198, 210, 222, 246, 270, 294]

Full machine-readable copies: `data/learn/r57_seed_splits.json`
and `data/learn/r57_provenance_manifest.json`.
