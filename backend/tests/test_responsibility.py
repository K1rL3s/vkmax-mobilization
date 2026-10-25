from zheka.core.enums import RequestPlace
from zheka.core.responsibility import LEAVES, SPOTS, Verdict

MIN_LEAVES = 15
MAX_LEAVES = 20


def test_every_spot_leads_to_15_to_20_leaves_in_all() -> None:
    assert MIN_LEAVES <= len(LEAVES) <= MAX_LEAVES
    assert {leaf.spot for leaf in LEAVES.values()} == set(SPOTS)


def test_every_leaf_gives_a_verdict_with_its_basis() -> None:
    for leaf in LEAVES.values():
        assert leaf.basis
        assert not leaf.basis.endswith(".")
        assert not leaf.label[0].isalnum()
        assert (leaf.category is not None) is (leaf.verdict is Verdict.MANAGEMENT)
        if leaf.verdict is Verdict.UTILITY:
            assert leaf.service is not None
        if leaf.verdict in {Verdict.MANAGEMENT, Verdict.OWNER, Verdict.UTILITY}:
            assert "ПП 491" in leaf.basis


def test_a_leaf_files_the_place_of_its_spot() -> None:
    assert LEAVES["riser_leak"].place is RequestPlace.FLAT
    assert LEAVES["roof"].place is RequestPlace.HOUSE


def test_a_radiator_is_common_property_only_with_the_tap_exception() -> None:
    for leaf in LEAVES.values():
        if "батаре" in leaf.basis:
            assert "Минстрой" in leaf.basis, leaf.label
