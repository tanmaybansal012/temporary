"""
tests/test_gate_conversion.py — Verify universal gate constructions match native gates.

For each (gate, universal_type) pair, we compare the output of the universal
construction against the native gate for all binary input combinations,
confirming truth table equivalence.
"""

import itertools
import pytest
from logic_sim.signal import Signal
from logic_sim.gates import ANDGate, ORGate, NOTGate, XORGate
from logic_sim.gate_conversion import (
    nand_and, nand_or, nand_not, nand_xor,
    nor_and, nor_or, nor_not, nor_xor,
)

L = Signal.LOW
H = Signal.HIGH


def eval_native_2(gate_cls, a, b):
    g = gate_cls(); g.inputs = [a, b]; return g.evaluate()

def eval_native_1(gate_cls, a):
    g = gate_cls(); g.inputs = [a]; return g.evaluate()


BINARY_INPUTS = list(itertools.product([L, H], repeat=2))
UNARY_INPUTS  = [L, H]


# ---------------------------------------------------------------------------
# NAND-only constructions
# ---------------------------------------------------------------------------

class TestNANDConversions:
    def test_nand_not_matches_native(self):
        for a in UNARY_INPUTS:
            assert nand_not(a) == eval_native_1(NOTGate, a), \
                f"NAND-NOT mismatch at A={a}"

    def test_nand_and_matches_native(self):
        for a, b in BINARY_INPUTS:
            assert nand_and(a, b) == eval_native_2(ANDGate, a, b), \
                f"NAND-AND mismatch at A={a}, B={b}"

    def test_nand_or_matches_native(self):
        for a, b in BINARY_INPUTS:
            assert nand_or(a, b) == eval_native_2(ORGate, a, b), \
                f"NAND-OR mismatch at A={a}, B={b}"

    def test_nand_xor_matches_native(self):
        for a, b in BINARY_INPUTS:
            assert nand_xor(a, b) == eval_native_2(XORGate, a, b), \
                f"NAND-XOR mismatch at A={a}, B={b}"

    def test_nand_and_full_truth_table(self):
        """Explicitly check all four AND rows."""
        assert nand_and(L, L) == L
        assert nand_and(L, H) == L
        assert nand_and(H, L) == L
        assert nand_and(H, H) == H

    def test_nand_or_full_truth_table(self):
        assert nand_or(L, L) == L
        assert nand_or(L, H) == H
        assert nand_or(H, L) == H
        assert nand_or(H, H) == H

    def test_nand_xor_full_truth_table(self):
        assert nand_xor(L, L) == L
        assert nand_xor(L, H) == H
        assert nand_xor(H, L) == H
        assert nand_xor(H, H) == L


# ---------------------------------------------------------------------------
# NOR-only constructions
# ---------------------------------------------------------------------------

class TestNORConversions:
    def test_nor_not_matches_native(self):
        for a in UNARY_INPUTS:
            assert nor_not(a) == eval_native_1(NOTGate, a), \
                f"NOR-NOT mismatch at A={a}"

    def test_nor_or_matches_native(self):
        for a, b in BINARY_INPUTS:
            assert nor_or(a, b) == eval_native_2(ORGate, a, b), \
                f"NOR-OR mismatch at A={a}, B={b}"

    def test_nor_and_matches_native(self):
        for a, b in BINARY_INPUTS:
            assert nor_and(a, b) == eval_native_2(ANDGate, a, b), \
                f"NOR-AND mismatch at A={a}, B={b}"

    def test_nor_xor_matches_native(self):
        for a, b in BINARY_INPUTS:
            assert nor_xor(a, b) == eval_native_2(XORGate, a, b), \
                f"NOR-XOR mismatch at A={a}, B={b}"

    def test_nor_and_full_truth_table(self):
        assert nor_and(L, L) == L
        assert nor_and(L, H) == L
        assert nor_and(H, L) == L
        assert nor_and(H, H) == H

    def test_nor_or_full_truth_table(self):
        assert nor_or(L, L) == L
        assert nor_or(L, H) == H
        assert nor_or(H, L) == H
        assert nor_or(H, H) == H

    def test_nor_xor_full_truth_table(self):
        assert nor_xor(L, L) == L
        assert nor_xor(L, H) == H
        assert nor_xor(H, L) == H
        assert nor_xor(H, H) == L


# ---------------------------------------------------------------------------
# Cross-check: NAND and NOR constructions agree with each other
# ---------------------------------------------------------------------------

class TestNANDvsNOR:
    def test_and_constructions_agree(self):
        for a, b in BINARY_INPUTS:
            assert nand_and(a, b) == nor_and(a, b), \
                f"NAND-AND and NOR-AND disagree at A={a}, B={b}"

    def test_or_constructions_agree(self):
        for a, b in BINARY_INPUTS:
            assert nand_or(a, b) == nor_or(a, b), \
                f"NAND-OR and NOR-OR disagree at A={a}, B={b}"

    def test_not_constructions_agree(self):
        for a in UNARY_INPUTS:
            assert nand_not(a) == nor_not(a), \
                f"NAND-NOT and NOR-NOT disagree at A={a}"

    def test_xor_constructions_agree(self):
        for a, b in BINARY_INPUTS:
            assert nand_xor(a, b) == nor_xor(a, b), \
                f"NAND-XOR and NOR-XOR disagree at A={a}, B={b}"
