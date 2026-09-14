"""
tests/test_circuit.py — Unit tests for Circuit, topological sort, and evaluation.

Tests cover:
  - Simple gate networks
  - Multi-gate pipelines (half adder, full adder)
  - Topological sort correctness
  - Cycle detection
  - UNKNOWN propagation through circuits
"""

import pytest
from logic_sim.circuit import Circuit, CombinationalCycleError
from logic_sim.signal import Signal

L = Signal.LOW
H = Signal.HIGH
X = Signal.UNKNOWN


# ---------------------------------------------------------------------------
# Helpers to build standard circuits
# ---------------------------------------------------------------------------

def make_half_adder() -> Circuit:
    """Build a half adder: SUM = A XOR B, COUT = A AND B."""
    c = Circuit()
    c.add_input("A")
    c.add_input("B")
    c.add_gate("SUM",  "XOR", ["A", "B"], "SUM")
    c.add_gate("COUT", "AND", ["A", "B"], "COUT")
    c.add_output("SUM")
    c.add_output("COUT")
    return c


def make_full_adder() -> Circuit:
    """
    Build a full adder:
      XOR1 = A XOR B
      AND1 = A AND B
      XOR2 = XOR1 XOR CIN   (SUM output)
      AND2 = XOR1 AND CIN
      COUT = AND1 OR AND2
    """
    c = Circuit()
    c.add_input("A")
    c.add_input("B")
    c.add_input("CIN")
    c.add_gate("XOR1", "XOR", ["A", "B"], "XOR1")
    c.add_gate("AND1", "AND", ["A", "B"], "AND1")
    c.add_gate("XOR2", "XOR", ["XOR1", "CIN"], "XOR2")
    c.add_gate("AND2", "AND", ["XOR1", "CIN"], "AND2")
    c.add_gate("COUT", "OR",  ["AND1", "AND2"], "COUT")
    c.add_output("XOR2")
    c.add_output("COUT")
    return c


# ---------------------------------------------------------------------------
# Basic gate evaluation through the circuit
# ---------------------------------------------------------------------------

class TestCircuitBasic:
    def test_and_gate_circuit(self):
        c = Circuit()
        c.add_input("A"); c.add_input("B")
        c.add_gate("Y", "AND", ["A", "B"], "Y")
        c.add_output("Y")

        assert c.evaluate({"A": L, "B": L}) == {"Y": L}
        assert c.evaluate({"A": L, "B": H}) == {"Y": L}
        assert c.evaluate({"A": H, "B": L}) == {"Y": L}
        assert c.evaluate({"A": H, "B": H}) == {"Y": H}

    def test_not_gate_circuit(self):
        c = Circuit()
        c.add_input("A")
        c.add_gate("Y", "NOT", ["A"], "Y")
        c.add_output("Y")

        assert c.evaluate({"A": L}) == {"Y": H}
        assert c.evaluate({"A": H}) == {"Y": L}
        assert c.evaluate({"A": X}) == {"Y": X}

    def test_unknown_propagation_through_chain(self):
        """UNKNOWN should propagate through a chain of gates."""
        c = Circuit()
        c.add_input("A")
        c.add_input("B")
        c.add_gate("Y1", "AND", ["A", "B"], "Y1")
        c.add_gate("Y2", "NOT", ["Y1"], "Y2")
        c.add_output("Y2")

        # AND(1, X) = X; NOT(X) = X
        assert c.evaluate({"A": H, "B": X}) == {"Y2": X}
        # AND(0, X) = 0; NOT(0) = 1
        assert c.evaluate({"A": L, "B": X}) == {"Y2": H}

    def test_unapplied_input_defaults_to_unknown(self):
        """Inputs not in the evaluate() dict should default to UNKNOWN."""
        c = Circuit()
        c.add_input("A"); c.add_input("B")
        c.add_gate("Y", "AND", ["A", "B"], "Y")
        c.add_output("Y")

        # A provided as HIGH, B omitted → B = UNKNOWN → AND(1, X) = X
        result = c.evaluate({"A": H})
        assert result["Y"] == X

    def test_invalid_input_name_raises(self):
        c = Circuit()
        c.add_input("A")
        c.add_gate("Y", "NOT", ["A"], "Y")
        c.add_output("Y")

        with pytest.raises(ValueError, match="not a declared primary input"):
            c.evaluate({"Z": H})


# ---------------------------------------------------------------------------
# Half adder truth table
# ---------------------------------------------------------------------------

class TestHalfAdder:
    EXPECTED = [
        (L, L, L, L),  # A=0,B=0 → SUM=0,COUT=0
        (L, H, H, L),  # A=0,B=1 → SUM=1,COUT=0
        (H, L, H, L),  # A=1,B=0 → SUM=1,COUT=0
        (H, H, L, H),  # A=1,B=1 → SUM=0,COUT=1
    ]

    def test_half_adder_truth_table(self):
        c = make_half_adder()
        for A, B, expected_sum, expected_cout in self.EXPECTED:
            out = c.evaluate({"A": A, "B": B})
            assert out["SUM"]  == expected_sum,  f"A={A},B={B}: SUM wrong"
            assert out["COUT"] == expected_cout, f"A={A},B={B}: COUT wrong"


# ---------------------------------------------------------------------------
# Full adder truth table
# ---------------------------------------------------------------------------

class TestFullAdder:
    EXPECTED = [
        # (A, B, CIN, SUM, COUT)
        (L, L, L, L, L),
        (L, L, H, H, L),
        (L, H, L, H, L),
        (L, H, H, L, H),
        (H, L, L, H, L),
        (H, L, H, L, H),
        (H, H, L, L, H),
        (H, H, H, H, H),
    ]

    def test_full_adder_truth_table(self):
        c = make_full_adder()
        for A, B, CIN, exp_sum, exp_cout in self.EXPECTED:
            out = c.evaluate({"A": A, "B": B, "CIN": CIN})
            assert out["XOR2"] == exp_sum,  f"A={A},B={B},CIN={CIN}: SUM wrong, got {out['XOR2']}"
            assert out["COUT"] == exp_cout, f"A={A},B={B},CIN={CIN}: COUT wrong, got {out['COUT']}"


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

class TestTopologicalSort:
    def test_sort_no_cycle(self):
        """A simple DAG should sort without error."""
        c = make_half_adder()
        order = c.topological_sort()
        # Should return both gates (SUM and COUT) in some valid order
        names = [n.name for n in order]
        assert "SUM" in names
        assert "COUT" in names

    def test_sort_respects_dependency_order(self):
        """In a chain A→G1→G2, G1 must appear before G2."""
        c = Circuit()
        c.add_input("A")
        c.add_gate("G1", "NOT", ["A"], "G1")
        c.add_gate("G2", "NOT", ["G1"], "G2")
        c.add_output("G2")

        order = c.topological_sort()
        names = [n.name for n in order]
        assert names.index("G1") < names.index("G2")

    def test_sort_detects_cycle(self):
        """
        Build a circuit with a feedback wire to trigger cycle detection.
        We manually wire a gate to use its own output as input via the internal API.
        """
        c = Circuit()
        c.add_input("A")

        # Manually create a wire and a gate that feeds back to itself
        # Using internal _wires to simulate the cycle
        from logic_sim.circuit import Wire, GateNode
        from logic_sim.gates import ANDGate

        w_a = c._wires.get("A") or c._get_or_create_wire("A")
        w_fb = c._get_or_create_wire("FB")  # feedback wire

        gate = ANDGate(name="G_cycle")
        node = GateNode("G_cycle", gate, [w_a, w_fb], w_fb)
        w_fb.driven_by = node
        c._gates["G_cycle"] = node

        with pytest.raises(CombinationalCycleError):
            c.topological_sort()

    def test_sort_cached_after_first_call(self):
        """Calling topological_sort() twice returns the same list object."""
        c = make_half_adder()
        order1 = c.topological_sort()
        order2 = c.topological_sort()
        assert order1 is order2  # cache hit

    def test_sort_cache_invalidated_after_add_gate(self):
        """Cache should be invalidated when a new gate is added."""
        c = Circuit()
        c.add_input("A"); c.add_input("B")
        c.add_gate("Y1", "AND", ["A", "B"], "Y1")
        c.add_output("Y1")

        order1 = c.topological_sort()
        assert len(order1) == 1

        c.add_gate("Y2", "OR", ["A", "B"], "Y2")
        c.add_output("Y2")
        order2 = c.topological_sort()
        assert len(order2) == 2  # now includes Y2


# ---------------------------------------------------------------------------
# Multiple drivers / duplicate gate name errors
# ---------------------------------------------------------------------------

class TestCircuitValidation:
    def test_duplicate_gate_name_raises(self):
        c = Circuit()
        c.add_input("A"); c.add_input("B")
        c.add_gate("G1", "AND", ["A", "B"], "G1")
        with pytest.raises(ValueError, match="already exists"):
            c.add_gate("G1", "OR", ["A", "B"], "G2")

    def test_multiple_drivers_raises(self):
        c = Circuit()
        c.add_input("A"); c.add_input("B")
        c.add_gate("G1", "AND", ["A", "B"], "WIRE_Y")
        with pytest.raises(ValueError, match="already driven"):
            c.add_gate("G2", "OR", ["A", "B"], "WIRE_Y")

    def test_input_driven_by_gate_raises(self):
        c = Circuit()
        c.add_input("A"); c.add_input("B")
        c.add_gate("A_gate", "AND", ["A", "B"], "A_gate")
        # Trying to declare a wire already driven by a gate as a primary input
        # (the driven_by check in add_input)
        # NOTE: "A" is already a primary input, but here we test the reverse:
        # if a wire named "A" was somehow driven by a gate, add_input should fail.
        c2 = Circuit()
        c2.add_input("X"); c2.add_input("Y")
        c2.add_gate("W", "AND", ["X", "Y"], "W")
        with pytest.raises(ValueError):
            c2.add_input("W")   # W is driven by gate, cannot be primary input
