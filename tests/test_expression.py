"""
tests/test_expression.py — Tests for boolean expression simplification.

Tests cover:
  - Simple AND/OR/NOT gate expressions
  - XOR circuit expression (verifies don't-care handling from UNKNOWN
    doesn't produce wrong minimization)
  - Half adder and full adder example fixtures
  - Constant output edge case
"""

import pytest
import os
from logic_sim.expression import simplify_circuit
from logic_sim.netlist_parser import parse_netlist, parse_netlist_file
from logic_sim.signal import Signal

L = Signal.LOW
H = Signal.HIGH


class TestSimpleExpressions:
    def test_and_gate_expression(self):
        """AND gate should simplify to 'A & B'."""
        c = parse_netlist("INPUT A B\nGATE Y AND A B\nOUTPUT Y")
        exprs = simplify_circuit(c)
        assert "Y" in exprs
        assert exprs["Y"] == "A & B"

    def test_or_gate_expression(self):
        """OR gate should simplify to 'A | B'."""
        c = parse_netlist("INPUT A B\nGATE Y OR A B\nOUTPUT Y")
        exprs = simplify_circuit(c)
        assert "Y" in exprs
        assert exprs["Y"] == "A | B"

    def test_not_gate_expression(self):
        """NOT gate should simplify to '~A'."""
        c = parse_netlist("INPUT A\nGATE Y NOT A\nOUTPUT Y")
        exprs = simplify_circuit(c)
        assert "Y" in exprs
        assert exprs["Y"] == "~A"

    def test_xor_circuit_expression(self):
        """
        XOR circuit should produce a valid boolean expression.

        Since SOPform produces sum-of-products, XOR(A, B) becomes
        (A & ~B) | (B & ~A) — verify it's logically correct by
        checking it contains the right terms.
        """
        c = parse_netlist("INPUT A B\nGATE Y XOR A B\nOUTPUT Y")
        exprs = simplify_circuit(c)
        assert "Y" in exprs
        expr = exprs["Y"]
        # XOR in SOP is: (A & ~B) | (~A & B)
        # Verify both minterms are present (order may vary)
        assert "A" in expr
        assert "B" in expr
        assert "&" in expr
        assert "|" in expr
        # Verify correctness by evaluating the expression symbolically
        _verify_xor_expression(expr)

    def test_constant_zero_output(self):
        """
        A circuit where the output is always 0 should produce '0'.
        Example: AND(A, NOT(A)) — always 0 since A AND ~A = 0.
        """
        net = "INPUT A\nGATE N NOT A\nGATE Y AND A N\nOUTPUT Y"
        c = parse_netlist(net)
        exprs = simplify_circuit(c)
        assert exprs["Y"] == "0"

    def test_constant_one_output(self):
        """
        A circuit where the output is always 1 should produce '1'.
        Example: OR(A, NOT(A)) — always 1 since A OR ~A = 1.
        """
        net = "INPUT A\nGATE N NOT A\nGATE Y OR A N\nOUTPUT Y"
        c = parse_netlist(net)
        exprs = simplify_circuit(c)
        assert exprs["Y"] == "1"


class TestFixtureExpressions:
    def test_half_adder_from_file(self):
        """Parse half_adder.net and verify both output expressions."""
        net_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "half_adder.net"
        )
        net_path = os.path.normpath(net_path)
        if not os.path.exists(net_path):
            pytest.skip("half_adder.net not found")

        c = parse_netlist_file(net_path)
        exprs = simplify_circuit(c)

        # SUM = A XOR B = (A & ~B) | (~A & B) in SOP form
        assert "SUM" in exprs
        _verify_xor_expression(exprs["SUM"])

        # COUT = A AND B
        assert "COUT" in exprs
        assert exprs["COUT"] == "A & B"

    def test_full_adder_from_file(self):
        """Parse full_adder.net and verify output expressions are valid."""
        net_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "full_adder.net"
        )
        net_path = os.path.normpath(net_path)
        if not os.path.exists(net_path):
            pytest.skip("full_adder.net not found")

        c = parse_netlist_file(net_path)
        exprs = simplify_circuit(c)

        # The full adder has outputs XOR2 (SUM) and COUT
        assert "XOR2" in exprs
        assert "COUT" in exprs

        # Verify correctness by checking against all 8 truth table rows
        _verify_expression_against_circuit(c, exprs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_xor_expression(expr_str: str) -> None:
    """Verify an expression string is equivalent to XOR(A, B)."""
    from sympy import symbols, sympify
    A, B = symbols("A B")
    expr = sympify(expr_str)
    xor_expr = (A & ~B) | (~A & B)
    # Check equivalence by simplifying the difference
    from sympy.logic.boolalg import Equivalent
    assert Equivalent(expr, xor_expr) == True  # noqa: E712


def _verify_expression_against_circuit(circuit, exprs: dict) -> None:
    """
    Verify that the simplified expressions match the circuit's truth table.
    Evaluates each expression symbolically for all input combos and compares.
    """
    import itertools
    from sympy import symbols, sympify

    input_names = circuit.input_names
    output_names = circuit.output_names
    syms = symbols(input_names)
    if len(input_names) == 1:
        syms = [syms]

    for combo in itertools.product([0, 1], repeat=len(input_names)):
        input_values = {
            name: Signal.from_int(val)
            for name, val in zip(input_names, combo)
        }
        circuit_outputs = circuit.evaluate(input_values)

        # Build substitution dict for sympy
        subs = {s: bool(v) for s, v in zip(syms, combo)}

        for out_name in output_names:
            circuit_val = circuit_outputs[out_name]
            if circuit_val == Signal.UNKNOWN:
                continue  # don't-care — skip

            expr = sympify(exprs[out_name])
            expr_val = bool(expr.subs(subs))
            expected = (circuit_val == Signal.HIGH)
            assert expr_val == expected, (
                f"Expression mismatch for {out_name} at inputs "
                f"{dict(zip(input_names, combo))}: "
                f"expression={expr_val}, circuit={expected}"
            )
