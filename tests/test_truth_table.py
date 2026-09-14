"""
tests/test_truth_table.py — Tests for truth table and state transition table generators.
"""

import itertools
import pytest
from logic_sim.circuit import Circuit
from logic_sim.truth_table import (
    generate_truth_table,
    print_truth_table,
    generate_state_transition_table,
    print_state_transition_table,
)
from logic_sim.sequential import DFlipFlop, JKFlipFlop, TFlipFlop
from logic_sim.signal import Signal

L = Signal.LOW
H = Signal.HIGH
X = Signal.UNKNOWN


def make_and_circuit():
    c = Circuit()
    c.add_input("A"); c.add_input("B")
    c.add_gate("Y", "AND", ["A", "B"], "Y")
    c.add_output("Y")
    return c


def make_half_adder():
    c = Circuit()
    c.add_input("A"); c.add_input("B")
    c.add_gate("SUM", "XOR", ["A", "B"], "SUM")
    c.add_gate("COUT", "AND", ["A", "B"], "COUT")
    c.add_output("SUM")
    c.add_output("COUT")
    return c


class TestGenerateTruthTable:
    def test_and_gate_rows(self):
        c = make_and_circuit()
        rows = generate_truth_table(c)
        assert len(rows) == 4  # 2^2

    def test_and_gate_values(self):
        c = make_and_circuit()
        rows = generate_truth_table(c)
        expected = [
            (L, L, L),
            (L, H, L),
            (H, L, L),
            (H, H, H),
        ]
        for row, (a, b, y) in zip(rows, expected):
            assert row["A"] == a
            assert row["B"] == b
            assert row["Y"] == y

    def test_half_adder_8_rows(self):
        c = make_half_adder()
        rows = generate_truth_table(c)
        assert len(rows) == 4  # 2 inputs → 4 rows

        # Row 3: A=1, B=1 → SUM=0, COUT=1
        assert rows[3]["A"] == H
        assert rows[3]["B"] == H
        assert rows[3]["SUM"] == L
        assert rows[3]["COUT"] == H

    def test_three_input_circuit(self):
        """Full adder should have 2^3 = 8 rows."""
        c = Circuit()
        c.add_input("A"); c.add_input("B"); c.add_input("C")
        c.add_gate("Y", "AND", ["A", "B", "C"], "Y")
        c.add_output("Y")
        rows = generate_truth_table(c)
        assert len(rows) == 8

    def test_all_inputs_enumerated(self):
        """All 2^n combinations must appear exactly once."""
        c = make_half_adder()
        rows = generate_truth_table(c)
        combos = set()
        for row in rows:
            combos.add((row["A"], row["B"]))
        # Should have all 4 combinations
        expected = {(L, L), (L, H), (H, L), (H, H)}
        assert combos == expected


class TestPrintTruthTable:
    def test_print_returns_string(self):
        c = make_and_circuit()
        rows = generate_truth_table(c)
        result = print_truth_table(rows, c.input_names, c.output_names)
        assert isinstance(result, str)
        assert "A" in result
        assert "B" in result
        assert "Y" in result

    def test_print_contains_all_values(self):
        c = make_and_circuit()
        rows = generate_truth_table(c)
        result = print_truth_table(rows, c.input_names, c.output_names)
        assert "0" in result
        assert "1" in result


class TestStateTransitionTable:
    def test_d_flipflop_rows(self):
        ff = DFlipFlop(clock_edge="rising")
        rows = generate_state_transition_table(ff, ["D", "CLK"])
        # 2 states × 2 D values = 4 rows
        assert len(rows) == 4

    def test_d_flipflop_correct_transitions(self):
        ff = DFlipFlop(clock_edge="rising")
        rows = generate_state_transition_table(ff, ["D", "CLK"])
        # Each row: Q_next should equal D (D flip-flop definition)
        for row in rows:
            assert row["Q_next"] == row["D"]

    def test_jk_flipflop_rows(self):
        ff = JKFlipFlop(clock_edge="rising")
        rows = generate_state_transition_table(ff, ["J", "K", "CLK"])
        # 2 states × 4 JK combinations = 8 rows
        assert len(rows) == 8

    def test_t_flipflop_toggle_transitions(self):
        ff = TFlipFlop(clock_edge="rising")
        rows = generate_state_transition_table(ff, ["T", "CLK"])
        # When T=1, Q_next should be NOT Q_current
        for row in rows:
            if row["T"] == H:
                assert row["Q_next"] == row["Q_current"].invert()

    def test_t_flipflop_hold_transitions(self):
        ff = TFlipFlop(clock_edge="rising")
        rows = generate_state_transition_table(ff, ["T", "CLK"])
        for row in rows:
            if row["T"] == L:
                assert row["Q_next"] == row["Q_current"]
