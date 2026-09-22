"""
tests/test_layout.py — Tests for the circuit layout computation.

Tests cover:
  - Layer assignment for half adder (all gates at layer 1)
  - Layer assignment for full adder (increasing dependency depth)
  - Longer dependency chain
  - Primary inputs at layer 0
"""

import pytest
from logic_sim.layout import compute_layout
from logic_sim.netlist_parser import parse_netlist, parse_netlist_file
import os


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

CHAIN_NET = """
# A chain of 4 gates, each depending on the previous
INPUT A B
GATE G1 AND A B
GATE G2 NOT G1
GATE G3 NOT G2
GATE G4 NOT G3
OUTPUT G4
"""


class TestLayerAssignment:
    def test_half_adder_both_gates_at_layer_1(self):
        """Both SUM and COUT gates read only from primary inputs → layer 1."""
        c = parse_netlist(HALF_ADDER_NET)
        layout = compute_layout(c)
        assert layout["SUM"][0] == 1
        assert layout["COUT"][0] == 1

    def test_full_adder_layers(self):
        """
        Full adder gate layers:
          XOR1, AND1 → layer 1 (read from inputs)
          XOR2, AND2 → layer 2 (read from XOR1 + inputs)
          COUT       → layer 3 (reads from AND1 + AND2, AND2 is at layer 2)
        """
        c = parse_netlist(FULL_ADDER_NET)
        layout = compute_layout(c)
        assert layout["XOR1"][0] == 1
        assert layout["AND1"][0] == 1
        assert layout["XOR2"][0] == 2
        assert layout["AND2"][0] == 2
        assert layout["COUT"][0] == 3

    def test_longer_chain_layers(self):
        """A chain of 4 gates should produce layers 1, 2, 3, 4."""
        c = parse_netlist(CHAIN_NET)
        layout = compute_layout(c)
        assert layout["G1"][0] == 1
        assert layout["G2"][0] == 2
        assert layout["G3"][0] == 3
        assert layout["G4"][0] == 4

    def test_inputs_at_layer_zero(self):
        """All primary inputs should be at layer 0."""
        c = parse_netlist(FULL_ADDER_NET)
        layout = compute_layout(c)
        assert layout["A"] == (0, 0)
        assert layout["B"] == (0, 1)
        assert layout["CIN"] == (0, 2)

    def test_full_adder_file(self):
        """Parse the actual full_adder.net file and verify layout."""
        net_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "full_adder.net"
        )
        net_path = os.path.normpath(net_path)
        if not os.path.exists(net_path):
            pytest.skip("full_adder.net not found")

        c = parse_netlist_file(net_path)
        layout = compute_layout(c)

        # Verify basic structure: inputs at 0, gates at 1+
        for inp in c.input_names:
            assert layout[inp][0] == 0

        # All gates should have layer >= 1
        for gate in c.gate_names:
            assert layout[gate][0] >= 1

    def test_y_coordinates_stable(self):
        """Gates in the same layer should have distinct y-coordinates."""
        c = parse_netlist(FULL_ADDER_NET)
        layout = compute_layout(c)

        # Layer 1: XOR1, AND1 — should have different y-values
        layer_1_ys = [layout[g][1] for g in ["XOR1", "AND1"]]
        assert len(set(layer_1_ys)) == 2

        # Layer 2: XOR2, AND2 — should have different y-values
        layer_2_ys = [layout[g][1] for g in ["XOR2", "AND2"]]
        assert len(set(layer_2_ys)) == 2
