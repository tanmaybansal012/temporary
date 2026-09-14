"""
tests/test_gates.py — Unit tests for all logic gate primitives.

Tests cover:
  - Correct truth table for each gate type
  - UNKNOWN propagation cases (the non-obvious behavior)
  - Arity validation (wrong number of inputs raises ValueError)
"""

import pytest
from logic_sim.gates import (
    NOTGate, ANDGate, ORGate, NANDGate, NORGate, XORGate, XNORGate
)
from logic_sim.signal import Signal

L = Signal.LOW
H = Signal.HIGH
X = Signal.UNKNOWN


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def eval_gate(gate_cls, *inputs):
    """Instantiate gate, set inputs, return evaluate() result."""
    g = gate_cls()
    g.inputs = list(inputs)
    return g.evaluate()


# ---------------------------------------------------------------------------
# NOT gate
# ---------------------------------------------------------------------------

class TestNOTGate:
    def test_not_low(self):
        assert eval_gate(NOTGate, L) == H

    def test_not_high(self):
        assert eval_gate(NOTGate, H) == L

    def test_not_unknown(self):
        assert eval_gate(NOTGate, X) == X

    def test_not_too_many_inputs(self):
        g = NOTGate()
        g.inputs = [L, L]
        with pytest.raises(ValueError):
            g.evaluate()

    def test_not_zero_inputs(self):
        g = NOTGate()
        g.inputs = []
        with pytest.raises(ValueError):
            g.evaluate()


# ---------------------------------------------------------------------------
# AND gate
# ---------------------------------------------------------------------------

class TestANDGate:
    def test_and_truth_table(self):
        assert eval_gate(ANDGate, L, L) == L
        assert eval_gate(ANDGate, L, H) == L
        assert eval_gate(ANDGate, H, L) == L
        assert eval_gate(ANDGate, H, H) == H

    def test_and_zero_dominates_unknown(self):
        """AND(0, X) = 0 — LOW is the absorbing element for AND."""
        assert eval_gate(ANDGate, L, X) == L
        assert eval_gate(ANDGate, X, L) == L

    def test_and_one_and_unknown_is_unknown(self):
        """AND(1, X) = X — cannot determine output."""
        assert eval_gate(ANDGate, H, X) == X
        assert eval_gate(ANDGate, X, H) == X

    def test_and_unknown_unknown(self):
        assert eval_gate(ANDGate, X, X) == X

    def test_and_three_inputs(self):
        assert eval_gate(ANDGate, H, H, H) == H
        assert eval_gate(ANDGate, H, H, L) == L
        assert eval_gate(ANDGate, L, X, X) == L  # 0 still dominates

    def test_and_one_input_raises(self):
        g = ANDGate()
        g.inputs = [H]
        with pytest.raises(ValueError):
            g.evaluate()


# ---------------------------------------------------------------------------
# OR gate
# ---------------------------------------------------------------------------

class TestORGate:
    def test_or_truth_table(self):
        assert eval_gate(ORGate, L, L) == L
        assert eval_gate(ORGate, L, H) == H
        assert eval_gate(ORGate, H, L) == H
        assert eval_gate(ORGate, H, H) == H

    def test_or_one_dominates_unknown(self):
        """OR(1, X) = 1 — HIGH is the absorbing element for OR."""
        assert eval_gate(ORGate, H, X) == H
        assert eval_gate(ORGate, X, H) == H

    def test_or_zero_and_unknown_is_unknown(self):
        """OR(0, X) = X — cannot determine output."""
        assert eval_gate(ORGate, L, X) == X
        assert eval_gate(ORGate, X, L) == X

    def test_or_unknown_unknown(self):
        assert eval_gate(ORGate, X, X) == X

    def test_or_three_inputs(self):
        assert eval_gate(ORGate, L, L, L) == L
        assert eval_gate(ORGate, H, X, X) == H   # 1 dominates


# ---------------------------------------------------------------------------
# NAND gate
# ---------------------------------------------------------------------------

class TestNANDGate:
    def test_nand_truth_table(self):
        assert eval_gate(NANDGate, L, L) == H
        assert eval_gate(NANDGate, L, H) == H
        assert eval_gate(NANDGate, H, L) == H
        assert eval_gate(NANDGate, H, H) == L

    def test_nand_zero_gives_high(self):
        """NAND(0, X) = NOT(AND(0,X)) = NOT(0) = 1."""
        assert eval_gate(NANDGate, L, X) == H
        assert eval_gate(NANDGate, X, L) == H

    def test_nand_one_and_unknown(self):
        """NAND(1, X) = NOT(AND(1,X)) = NOT(X) = X."""
        assert eval_gate(NANDGate, H, X) == X
        assert eval_gate(NANDGate, X, H) == X


# ---------------------------------------------------------------------------
# NOR gate
# ---------------------------------------------------------------------------

class TestNORGate:
    def test_nor_truth_table(self):
        assert eval_gate(NORGate, L, L) == H
        assert eval_gate(NORGate, L, H) == L
        assert eval_gate(NORGate, H, L) == L
        assert eval_gate(NORGate, H, H) == L

    def test_nor_one_gives_low(self):
        """NOR(1, X) = NOT(OR(1,X)) = NOT(1) = 0."""
        assert eval_gate(NORGate, H, X) == L
        assert eval_gate(NORGate, X, H) == L

    def test_nor_zero_and_unknown(self):
        """NOR(0, X) = NOT(OR(0,X)) = NOT(X) = X."""
        assert eval_gate(NORGate, L, X) == X
        assert eval_gate(NORGate, X, L) == X


# ---------------------------------------------------------------------------
# XOR gate
# ---------------------------------------------------------------------------

class TestXORGate:
    def test_xor_truth_table(self):
        assert eval_gate(XORGate, L, L) == L
        assert eval_gate(XORGate, L, H) == H
        assert eval_gate(XORGate, H, L) == H
        assert eval_gate(XORGate, H, H) == L

    def test_xor_any_unknown_propagates(self):
        """XOR has no absorbing element — any UNKNOWN propagates."""
        assert eval_gate(XORGate, X, L) == X
        assert eval_gate(XORGate, X, H) == X
        assert eval_gate(XORGate, L, X) == X
        assert eval_gate(XORGate, H, X) == X
        assert eval_gate(XORGate, X, X) == X

    def test_xor_three_inputs_parity(self):
        """XOR(1,1,1) = 1 (odd number of 1s)."""
        assert eval_gate(XORGate, H, H, H) == H
        assert eval_gate(XORGate, H, H, L) == L
        assert eval_gate(XORGate, H, L, L) == H


# ---------------------------------------------------------------------------
# XNOR gate
# ---------------------------------------------------------------------------

class TestXNORGate:
    def test_xnor_truth_table(self):
        assert eval_gate(XNORGate, L, L) == H
        assert eval_gate(XNORGate, L, H) == L
        assert eval_gate(XNORGate, H, L) == L
        assert eval_gate(XNORGate, H, H) == H

    def test_xnor_unknown_propagates(self):
        assert eval_gate(XNORGate, X, L) == X
        assert eval_gate(XNORGate, H, X) == X
