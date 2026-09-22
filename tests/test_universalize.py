"""
tests/test_universalize.py — Tests for universal gate circuit conversion.

The most important correctness check: the truth table of a universalized
circuit must exactly match the truth table of the original circuit for
both NAND and NOR conversions.
"""

import pytest
import os
from logic_sim.universalize import to_universal
from logic_sim.netlist_parser import parse_netlist, parse_netlist_file
from logic_sim.truth_table import generate_truth_table
from logic_sim.signal import Signal

L = Signal.LOW
H = Signal.HIGH


def _assert_truth_tables_match(original_circuit, converted_circuit):
    """Verify two circuits produce identical truth tables."""
    original_rows = generate_truth_table(original_circuit)
    converted_rows = generate_truth_table(converted_circuit)

    assert len(original_rows) == len(converted_rows), (
        f"Row count mismatch: {len(original_rows)} vs {len(converted_rows)}"
    )

    for i, (orig, conv) in enumerate(zip(original_rows, converted_rows)):
        for out_name in original_circuit.output_names:
            assert orig[out_name] == conv[out_name], (
                f"Row {i}: output '{out_name}' differs. "
                f"Original={orig[out_name]}, Converted={conv[out_name]}"
            )


HALF_ADDER_NET = """
INPUT A B
GATE SUM XOR A B
GATE COUT AND A B
OUTPUT SUM COUT
"""

FULL_ADDER_NET = """
INPUT A B CIN
GATE XOR1 XOR A B
GATE AND1 AND A B
GATE XOR2 XOR XOR1 CIN
GATE AND2 AND XOR1 CIN
GATE COUT OR AND1 AND2
OUTPUT XOR2 COUT
"""


class TestNANDConversion:
    def test_half_adder_nand_truth_table(self):
        """Half adder converted to NAND gates should have identical truth table."""
        c = parse_netlist(HALF_ADDER_NET)
        c_nand = to_universal(c, "nand")
        _assert_truth_tables_match(c, c_nand)

    def test_full_adder_nand_truth_table(self):
        """Full adder converted to NAND gates should have identical truth table."""
        c = parse_netlist(FULL_ADDER_NET)
        c_nand = to_universal(c, "nand")
        _assert_truth_tables_match(c, c_nand)

    def test_single_not_gate_nand(self):
        """Single NOT gate NAND conversion."""
        c = parse_netlist("INPUT A\nGATE Y NOT A\nOUTPUT Y")
        c_nand = to_universal(c, "nand")
        _assert_truth_tables_match(c, c_nand)

    def test_xor_gate_nand(self):
        """Standalone XOR gate NAND conversion."""
        c = parse_netlist("INPUT A B\nGATE Y XOR A B\nOUTPUT Y")
        c_nand = to_universal(c, "nand")
        _assert_truth_tables_match(c, c_nand)


class TestNORConversion:
    def test_half_adder_nor_truth_table(self):
        """Half adder converted to NOR gates should have identical truth table."""
        c = parse_netlist(HALF_ADDER_NET)
        c_nor = to_universal(c, "nor")
        _assert_truth_tables_match(c, c_nor)

    def test_full_adder_nor_truth_table(self):
        """Full adder converted to NOR gates should have identical truth table."""
        c = parse_netlist(FULL_ADDER_NET)
        c_nor = to_universal(c, "nor")
        _assert_truth_tables_match(c, c_nor)

    def test_single_not_gate_nor(self):
        """Single NOT gate NOR conversion."""
        c = parse_netlist("INPUT A\nGATE Y NOT A\nOUTPUT Y")
        c_nor = to_universal(c, "nor")
        _assert_truth_tables_match(c, c_nor)

    def test_xor_gate_nor(self):
        """Standalone XOR gate NOR conversion."""
        c = parse_netlist("INPUT A B\nGATE Y XOR A B\nOUTPUT Y")
        c_nor = to_universal(c, "nor")
        _assert_truth_tables_match(c, c_nor)


class TestEdgeCases:
    def test_invalid_gate_type_raises(self):
        """Passing an invalid gate type should raise ValueError."""
        c = parse_netlist("INPUT A B\nGATE Y AND A B\nOUTPUT Y")
        with pytest.raises(ValueError, match="'nand' or 'nor'"):
            to_universal(c, "invalid")

    def test_nand_gate_stays_nand_in_nand_mode(self):
        """A NAND gate should remain as-is when converting to NAND."""
        c = parse_netlist("INPUT A B\nGATE Y NAND A B\nOUTPUT Y")
        c_nand = to_universal(c, "nand")
        _assert_truth_tables_match(c, c_nand)

    def test_nor_gate_stays_nor_in_nor_mode(self):
        """A NOR gate should remain as-is when converting to NOR."""
        c = parse_netlist("INPUT A B\nGATE Y NOR A B\nOUTPUT Y")
        c_nor = to_universal(c, "nor")
        _assert_truth_tables_match(c, c_nor)

    def test_three_input_and_nand(self):
        """Three-input AND gate NAND conversion should work correctly."""
        c = parse_netlist("INPUT A B C\nGATE Y AND A B C\nOUTPUT Y")
        c_nand = to_universal(c, "nand")
        _assert_truth_tables_match(c, c_nand)
