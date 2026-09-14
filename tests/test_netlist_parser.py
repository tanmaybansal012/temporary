"""
tests/test_netlist_parser.py — Tests for the netlist file parser.

Tests cover:
  - Successful parsing of valid netlists (half adder, full adder)
  - Correct circuit structure after parsing
  - Error cases: unknown gate types, duplicate gate names, missing inputs,
    wrong arity, invalid directives
"""

import pytest
from logic_sim.netlist_parser import parse_netlist, parse_netlist_file
from logic_sim.signal import Signal
import os

L = Signal.LOW
H = Signal.HIGH


# ---------------------------------------------------------------------------
# Valid netlists
# ---------------------------------------------------------------------------

HALF_ADDER_NET = """
# Half adder
INPUT A B
GATE SUM XOR A B
GATE COUT AND A B
OUTPUT SUM COUT
"""

FULL_ADDER_NET = """
# Full adder
INPUT A B CIN
GATE XOR1 XOR A B
GATE AND1 AND A B
GATE XOR2 XOR XOR1 CIN
GATE AND2 AND XOR1 CIN
GATE COUT OR AND1 AND2
OUTPUT XOR2 COUT
"""

INVERTER_NET = """
INPUT A
GATE NOT_A NOT A
OUTPUT NOT_A
"""


class TestValidParsing:
    def test_half_adder_inputs(self):
        c = parse_netlist(HALF_ADDER_NET)
        assert c.input_names == ["A", "B"]

    def test_half_adder_outputs(self):
        c = parse_netlist(HALF_ADDER_NET)
        assert set(c.output_names) == {"SUM", "COUT"}

    def test_half_adder_gate_count(self):
        c = parse_netlist(HALF_ADDER_NET)
        assert len(c.gate_names) == 2

    def test_half_adder_evaluate(self):
        c = parse_netlist(HALF_ADDER_NET)
        out = c.evaluate({"A": H, "B": H})
        assert out["SUM"] == L   # 1 XOR 1 = 0
        assert out["COUT"] == H  # 1 AND 1 = 1

    def test_full_adder_input_count(self):
        c = parse_netlist(FULL_ADDER_NET)
        assert len(c.input_names) == 3

    def test_full_adder_8_row_truth_table(self):
        from logic_sim.truth_table import generate_truth_table
        c = parse_netlist(FULL_ADDER_NET)
        rows = generate_truth_table(c)
        assert len(rows) == 8

    def test_full_adder_known_values(self):
        c = parse_netlist(FULL_ADDER_NET)
        # A=1, B=1, CIN=1 → SUM=1, COUT=1
        out = c.evaluate({"A": H, "B": H, "CIN": H})
        assert out["XOR2"] == H  # SUM = 1 XOR 1 XOR 1 = 1
        assert out["COUT"] == H  # COUT = 1

    def test_inverter_net(self):
        c = parse_netlist(INVERTER_NET)
        out = c.evaluate({"A": H})
        assert out["NOT_A"] == L
        out = c.evaluate({"A": L})
        assert out["NOT_A"] == H

    def test_blank_lines_and_comments_ignored(self):
        net = """
        # This is a comment

        # Another comment
        INPUT A

        GATE Y NOT A
        OUTPUT Y
        """
        c = parse_netlist(net)
        assert c.input_names == ["A"]

    def test_case_insensitive_gate_type(self):
        """Gate types in netlists should be uppercased by the parser."""
        net = "INPUT A B\nGATE Y and A B\nOUTPUT Y"
        # Parser uppercases gate_type internally, so 'and' → 'AND'
        c = parse_netlist(net)
        out = c.evaluate({"A": H, "B": H})
        assert out["Y"] == H


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestParserErrors:
    def test_unknown_gate_type(self):
        net = "INPUT A B\nGATE Y BUFFER A B\nOUTPUT Y"
        with pytest.raises(ValueError, match="Unknown gate type"):
            parse_netlist(net)

    def test_duplicate_gate_name(self):
        net = "INPUT A B\nGATE G1 AND A B\nGATE G1 OR A B\nOUTPUT G1"
        with pytest.raises(ValueError, match="Duplicate gate name"):
            parse_netlist(net)

    def test_not_gate_too_many_inputs(self):
        net = "INPUT A B\nGATE Y NOT A B\nOUTPUT Y"
        with pytest.raises(ValueError, match="exactly 1 input"):
            parse_netlist(net)

    def test_binary_gate_too_few_inputs(self):
        net = "INPUT A\nGATE Y AND A\nOUTPUT Y"
        with pytest.raises(ValueError, match="at least 2 inputs"):
            parse_netlist(net)

    def test_input_directive_no_names(self):
        net = "INPUT\n"
        with pytest.raises(ValueError, match="at least one wire name"):
            parse_netlist(net)

    def test_output_directive_no_names(self):
        net = "INPUT A\nGATE Y NOT A\nOUTPUT"
        with pytest.raises(ValueError, match="at least one wire name"):
            parse_netlist(net)

    def test_unknown_directive(self):
        net = "INPUT A\nWIRE A B\nOUTPUT A"
        with pytest.raises(ValueError, match="Unknown directive"):
            parse_netlist(net)

    def test_gate_then_input_same_name_raises(self):
        """A wire that has already been driven by a gate cannot become a primary input."""
        net = "INPUT A B\nGATE W AND A B\nINPUT W\nOUTPUT W"
        with pytest.raises(ValueError):
            parse_netlist(net)

    def test_error_includes_line_number(self):
        net = "INPUT A B\nGATE Y UNKNOWNTYPE A B\nOUTPUT Y"
        with pytest.raises(ValueError) as exc_info:
            parse_netlist(net, source_name="test.net")
        # The error message should include the line number (line 2)
        assert "2" in str(exc_info.value)
        assert "test.net" in str(exc_info.value)


# ---------------------------------------------------------------------------
# File-based parsing
# ---------------------------------------------------------------------------

class TestFileParser:
    def test_parse_half_adder_file(self):
        """Parse the actual half_adder.net example file."""
        net_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "half_adder.net"
        )
        net_path = os.path.normpath(net_path)
        if not os.path.exists(net_path):
            pytest.skip("half_adder.net not found")

        c = parse_netlist_file(net_path)
        assert set(c.input_names) == {"A", "B"}
        assert set(c.output_names) == {"SUM", "COUT"}

    def test_parse_full_adder_file(self):
        """Parse the actual full_adder.net example file and verify all 8 rows."""
        net_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "full_adder.net"
        )
        net_path = os.path.normpath(net_path)
        if not os.path.exists(net_path):
            pytest.skip("full_adder.net not found")

        from logic_sim.truth_table import generate_truth_table
        c = parse_netlist_file(net_path)
        rows = generate_truth_table(c)
        assert len(rows) == 8

        # Row 7: A=1, B=1, CIN=1 → SUM=1, COUT=1
        last_row = rows[7]
        assert last_row["XOR2"] == H
        assert last_row["COUT"] == H

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_netlist_file("nonexistent_file.net")
