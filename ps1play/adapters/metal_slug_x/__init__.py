"""ps1play.adapters.metal_slug_x — the Metal Slug X GameAdapter +
Mission-1 policy (R66) and the game's downloadable knowledge package.

Metal Slug X (SLUS-01212, the owner's lawful local copy) became the
FOURTH registered runtime game in R66: `python3 -m ps1play play
metal_slug_x` runs the deterministic Mission-1 rules policy through
the standard product path.  ALL game knowledge lives HERE and in the
game's own .ps1game package — the shared runtime knows nothing about
Metal Slug X entities, states, scores or corridors.

Provenance (the committed evidence this adapter is built on):
  * disc: the retail SLUS-01212 image, sha256 45cde149… (the exact
    bytes every committed record was made with).
  * RAM anchors: the R38-R52 verified map (player x 0x0CA2E0 u32
    16.16, score 0x0EE318, grenades 0x0EDCF4, hp indicator 0x0CA2F6,
    the alive word 0x0EE518, the entity table 0x0CA268 stride 0x14C
    with st/x/h/sx per slot) — re-validated live by the R66 boots.
  * the R66 corridor predicate (the starvation fix): blockers must be
    able to absorb the bullet or register the payment — projectiles
    and the bullet-transparent 0xab94 never block (the pass-A
    GATE_DIAG dump, n=13+13 skips; the n=4 piercing evidence).
  * the pay-frame law (R66): the score accumulator pays on the
    internal damage event (the +500 at tail f1) ~2 frames BEFORE the
    victim's visible 0x5b0c registration; the slot12@0xa0 pulse is
    the registration witness.

ZERO memory writes; ZERO core edits; legal controller input only;
no training anywhere.  Maturity stays honest: the game is
PARTIAL_AUTONOMOUS_PLAYER at best (Mission 1 not cleared) — the
package manifest carries the exact status.
"""
from ps1play.adapters.metal_slug_x.adapter import (  # noqa: F401
    MetalSlugXAdapter,
)
from ps1play.adapters.metal_slug_x.policy import Mission1Policy  # noqa: F401,E501
from ps1play.adapters.metal_slug_x.package_spec import build_spec  # noqa: F401,E501

ADAPTER_VERSION = "0.2.0"
