"""Compatibility verdict for the frozen zlib 1.4 surfaces.

compression_level_9 is not a collected surface. Uncollected names stay
not_compared. A match is not universal and is not accepted_pass by itself.
"""

from __future__ import annotations

from raee_reverse.compare import COLLECTED_SURFACES, UNCOLLECTED_SURFACES, compare_surfaces

# The contract uses the surfaces that were sealed. Level -9 is intentionally absent.
CONTRACT_SURFACES = COLLECTED_SURFACES


def zlib_verdict(observed: dict, expected: dict) -> dict:
    if "compression_level_9" in CONTRACT_SURFACES:
        raise RuntimeError("compression_level_9 must stay out of the compatibility verdict")
    result = compare_surfaces(observed, expected, collected=CONTRACT_SURFACES)
    result["acceptance"] = "non-blind"
    result["compression_level_9"] = "not_compared"
    for name in UNCOLLECTED_SURFACES:
        result["surfaces"][name] = "not_compared"
    return result
