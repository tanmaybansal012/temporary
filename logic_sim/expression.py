"""
expression.py — Boolean expression simplification for combinational circuits.

Given a Circuit, generates a minimized sum-of-products (SOP) boolean expression
for each primary output wire, expressed in terms of the primary inputs.

Implementation:
  1. Reuse generate_truth_table() from truth_table.py — do not re-derive
     circuit semantics.
  2. For each output column, collect minterms (rows where output == HIGH) and
     don't-cares (rows where output == UNKNOWN).
  3. Use sympy.logic.boolalg.SOPform to minimize each output's expression.
  4. Render the expression using standard operators: & (AND), | (OR), ~ (NOT).
"""

from __future__ import annotations
from typing import Dict, List

from logic_sim.circuit import Circuit
from logic_sim.signal import Signal
from logic_sim.truth_table import generate_truth_table


def simplify_circuit(circuit: Circuit) -> Dict[str, str]:
    """
    Compute minimized SOP boolean expressions for all primary outputs.

    Args:
        circuit: A fully constructed Circuit with declared inputs and outputs.

    Returns:
        Dict mapping each output wire name to its minimized expression string.
        Expressions use the operators & (AND), | (OR), ~ (NOT).
        Constant outputs are rendered as "0" or "1".

    Example::

        c = parse_netlist("INPUT A B\\nGATE Y AND A B\\nOUTPUT Y")
        exprs = simplify_circuit(c)
        # exprs == {"Y": "A & B"}
    """
    from sympy import symbols as sympy_symbols
    from sympy.logic.boolalg import SOPform

    input_names = circuit.input_names
    output_names = circuit.output_names

    # Generate the full truth table (all 2^n rows)
    rows = generate_truth_table(circuit)

    # Create sympy symbols for each input
    # Use space-separated string to get a tuple; for a single name, symbols()
    # returns a single Symbol, so we always wrap in a list for uniformity.
    sym_list = list(sympy_symbols(input_names))

    results: Dict[str, str] = {}

    for out_name in output_names:
        minterms: List[List[int]] = []
        dontcares: List[List[int]] = []

        for row in rows:
            # Build the input combination as a list of 0/1 ints
            input_combo = []
            for inp_name in input_names:
                val = row[inp_name]
                input_combo.append(1 if val == Signal.HIGH else 0)

            out_val = row[out_name]
            if out_val == Signal.HIGH:
                minterms.append(input_combo)
            elif out_val == Signal.UNKNOWN:
                dontcares.append(input_combo)
            # Signal.LOW rows are simply omitted (off-set)

        # SOPform returns a sympy boolean expression
        expr = SOPform(sym_list, minterms, dontcares)

        # Convert to string using standard operator notation
        expr_str = _format_expression(expr)
        results[out_name] = expr_str

    return results


def _format_expression(expr) -> str:
    """
    Convert a sympy boolean expression to a human-readable string
    using & (AND), | (OR), ~ (NOT) operators.

    Handles special cases:
      - sympy.true  → "1"
      - sympy.false → "0"
      - Single symbol → just the symbol name
    """
    from sympy import true as sym_true, false as sym_false

    if expr is sym_true or expr == True:  # noqa: E712
        return "1"
    if expr is sym_false or expr == False:  # noqa: E712
        return "0"

    # Use sympy's string representation which already uses & | ~
    # but clean up whitespace for readability
    s = str(expr)

    # sympy renders as "A & B", "A | B", "~A" which is our target format
    return s
