"""
truth_table.py — Truth table and state transition table generators.

For combinational circuits, we enumerate all 2^n input combinations and
collect the corresponding output values. This is the standard verification
technique: if your circuit's truth table matches the specification, the
implementation is correct for all possible inputs.

For sequential elements, we enumerate (current_state × input_combinations)
to produce the state transition table used in sequential circuit analysis
and state machine minimization.
"""

from __future__ import annotations
import itertools
from typing import Any, Dict, List, Union

from logic_sim.circuit import Circuit
from logic_sim.signal import Signal


# ---------------------------------------------------------------------------
# Combinational truth table
# ---------------------------------------------------------------------------

def generate_truth_table(circuit: Circuit) -> List[Dict[str, Any]]:
    """
    Generate the full truth table for an n-input combinational circuit.

    Enumerates all 2^n binary input combinations using itertools.product,
    evaluates the circuit for each, and returns the results as a list of
    row dicts.

    Args:
        circuit: A fully constructed Circuit with declared inputs and outputs.

    Returns:
        List of dicts, one per input combination. Each dict has an entry for
        every input and every output wire, with Signal values.

    Example::

        rows = generate_truth_table(half_adder_circuit)
        print_truth_table(rows, half_adder_circuit.input_names,
                          half_adder_circuit.output_names)
    """
    input_names = circuit.input_names
    output_names = circuit.output_names
    rows: List[Dict[str, Any]] = []

    for combo in itertools.product([0, 1], repeat=len(input_names)):
        input_values = {
            name: Signal.from_int(val)
            for name, val in zip(input_names, combo)
        }
        output_values = circuit.evaluate(input_values)
        row = {**input_values, **output_values}
        rows.append(row)

    return rows


def print_truth_table(
    rows: List[Dict[str, Any]],
    input_names: List[str],
    output_names: List[str],
) -> str:
    """
    Format and print a truth table with aligned columns.

    Uses str.format alignment — no external table library required.

    Args:
        rows:         Output of generate_truth_table().
        input_names:  Ordered list of input column names.
        output_names: Ordered list of output column names.

    Returns:
        The formatted table as a string (also printed to stdout).
    """
    all_cols = input_names + output_names
    col_width = max(len(name) for name in all_cols) + 2

    # Header
    header = "".join(f"{name:^{col_width}}" for name in all_cols)
    sep = "-" * len(header)
    lines = [header, sep]

    for row in rows:
        line = "".join(
            f"{str(row[col]):^{col_width}}" for col in all_cols
        )
        lines.append(line)

    table_str = "\n".join(lines)
    print(table_str)
    return table_str


# ---------------------------------------------------------------------------
# State transition table (for sequential elements)
# ---------------------------------------------------------------------------

def generate_state_transition_table(
    element: Any,
    input_names: List[str],
    n_state_bits: int = 1,
) -> List[Dict[str, Any]]:
    """
    Generate a state transition table for a sequential element.

    Enumerates all combinations of (current_state ∈ {0,1}^n_state_bits)
    × (inputs ∈ {0,1}^|input_names|), drives the element, and records
    (current_state, inputs, next_state, Q).

    For single-bit elements (DFlipFlop, TFlipFlop, JKFlipFlop):
      n_state_bits = 1.

    Args:
        element:      A sequential element instance (DFlipFlop, JKFlipFlop, etc.)
                      with a clock_tick(inputs) method and a .state attribute.
        input_names:  List of input signal names to enumerate (e.g. ['D', 'CLK']
                      — but typically we enumerate data inputs and fix CLK to
                      trigger each row; see note below).
        n_state_bits: Number of state bits (1 for all standard flip-flops).

    Returns:
        List of row dicts with keys: 'Q_current', all input_names, 'Q_next'.

    Note:
        For edge-triggered flip-flops, we simulate one LOW→HIGH clock edge
        per row (driving CLK from 0→1) so that each row shows one triggered
        evaluation. The 'CLK' key is excluded from input_names for clarity
        and is handled internally.
    """
    rows: List[Dict[str, Any]] = []
    data_inputs = [n for n in input_names if n != "CLK"]

    for state_combo in itertools.product([0, 1], repeat=n_state_bits):
        # Set the element's state directly to enumerate all possible current states
        element.state = Signal.from_int(state_combo[0])
        # Reset clock tracking for edge-triggered elements (not applicable to latches)
        if hasattr(element, "_prev_clk"):
            element._prev_clk = Signal.LOW

        for inp_combo in itertools.product([0, 1], repeat=len(data_inputs)):
            inputs: Dict[str, Signal] = {
                name: Signal.from_int(val)
                for name, val in zip(data_inputs, inp_combo)
            }
            q_current = element.state

            # Drive a rising clock edge: LOW phase then HIGH phase
            if hasattr(element, "_prev_clk"):
                element._prev_clk = Signal.LOW
            inputs["CLK"] = Signal.HIGH
            q_next = element.clock_tick(inputs)

            row: Dict[str, Any] = {"Q_current": q_current}
            for name, val in zip(data_inputs, inp_combo):
                row[name] = Signal.from_int(val)
            row["Q_next"] = q_next
            rows.append(row)

            # Reset state for next iteration
            element.state = q_current
            if hasattr(element, "_prev_clk"):
                element._prev_clk = Signal.LOW

    return rows


def print_state_transition_table(
    rows: List[Dict[str, Any]],
    input_names: List[str],
) -> str:
    """
    Format and print a state transition table.

    Args:
        rows:        Output of generate_state_transition_table().
        input_names: Data input names (excluding CLK).

    Returns:
        The formatted table as a string (also printed to stdout).
    """
    data_inputs = [n for n in input_names if n != "CLK"]
    all_cols = ["Q_current"] + data_inputs + ["Q_next"]
    col_width = max(len(c) for c in all_cols) + 2

    header = "".join(f"{col:^{col_width}}" for col in all_cols)
    sep = "-" * len(header)
    lines = [header, sep]

    for row in rows:
        line = "".join(f"{str(row[col]):^{col_width}}" for col in all_cols)
        lines.append(line)

    table_str = "\n".join(lines)
    print(table_str)
    return table_str
