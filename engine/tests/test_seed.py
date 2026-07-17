from __future__ import annotations

from testdata_factory_engine import seeded_random, stable_seed


def test_stable_seed_is_repeatable() -> None:
    assert stable_seed("register", "valid_signup", 0) == stable_seed("register", "valid_signup", 0)


def test_seeded_random_is_repeatable() -> None:
    first = seeded_random("register", "valid_signup", 0).randint(1, 1_000_000)
    second = seeded_random("register", "valid_signup", 0).randint(1, 1_000_000)

    assert first == second
