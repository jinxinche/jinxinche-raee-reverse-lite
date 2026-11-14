from raee_reverse.compare import UNCOLLECTED_SURFACES
from raee_reverse.zlib_contract import CONTRACT_SURFACES, zlib_verdict


def test_level_9_stays_out_of_the_verdict():
    assert "compression_level_9" not in CONTRACT_SURFACES
    observed = {
        "stdout_sha256": "a" * 64,
        "stderr_sha256": "b" * 64,
        "exit_code": 0,
        "roundtrip_equals_input": True,
        "crc32_hex": "352441c2",
    }
    verdict = zlib_verdict(observed, observed)
    assert verdict["compatible_on_collected_surfaces"] is True
    assert verdict["compression_level_9"] == "not_compared"
    assert verdict["surfaces"]["compression_level_9"] == "not_compared"
    assert verdict["universal"] is False
    assert verdict["acceptance"] == "non-blind"
    for name in UNCOLLECTED_SURFACES:
        assert verdict["surfaces"][name] == "not_compared"


def test_a_mismatch_is_not_compatible():
    observed = {
        "stdout_sha256": "a" * 64,
        "stderr_sha256": "b" * 64,
        "exit_code": 0,
        "roundtrip_equals_input": True,
        "crc32_hex": "352441c2",
    }
    expected = dict(observed)
    expected["exit_code"] = 1
    verdict = zlib_verdict(observed, expected)
    assert verdict["compatible_on_collected_surfaces"] is False
    assert verdict["mismatches"] == ["exit_code"]
    assert verdict["accepted_pass"] is False
