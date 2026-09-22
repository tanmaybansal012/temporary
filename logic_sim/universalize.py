"""
universalize.py — Convert any combinational circuit to use only NAND or NOR gates.

Given a Circuit and a target universal gate type ("nand" or "nor"), walks every
gate and rebuilds it using the existing NAND/NOR constructions from
gate_conversion.py. Uses actual NANDGate/NORGate instances (not hardcoded
boolean math) so UNKNOWN propagation stays correct.

The result is a new, valid Circuit object that can be fed straight into
layout.py and render.py unmodified.
"""

from __future__ import annotations
from typing import Literal, List

from logic_sim.circuit import Circuit


# Global counter to ensure unique internal wire/gate names
_counter = 0


def _uid() -> str:
    """Generate a unique suffix to avoid gate/wire name collisions."""
    global _counter
    _counter += 1
    return f"_u{_counter}"


def to_universal(circuit: Circuit, gate: Literal["nand", "nor"]) -> Circuit:
    """
    Rebuild a circuit using only NAND or NOR gates.

    Args:
        circuit: A fully constructed Circuit with declared inputs and outputs.
        gate:    "nand" or "nor" — the target universal gate type.

    Returns:
        A new Circuit object with the same primary inputs and outputs, but
        all internal gates replaced by NAND-only or NOR-only constructions.
        The truth table of the new circuit is identical to the original.

    Raises:
        ValueError: If gate is not "nand" or "nor".
        CombinationalCycleError: If the circuit has a combinational cycle.
    """
    if gate not in ("nand", "nor"):
        raise ValueError(f"gate must be 'nand' or 'nor', got {gate!r}")

    global _counter
    _counter = 0  # reset per call for deterministic naming

    universal_type = gate.upper()  # "NAND" or "NOR"

    new_circuit = Circuit()

    # Copy primary inputs
    for inp_name in circuit.input_names:
        new_circuit.add_input(inp_name)

    # Walk gates in topological order
    for node in circuit.topological_sort():
        gate_type_name = type(node.gate).__name__
        input_wire_names = [w.name for w in node.input_wires]
        output_wire_names = [w.name for w in node.output_wires]
        primary_output = output_wire_names[0]

        # Multi-output gates (decoders) are kept as-is
        if gate_type_name in ("DEC2X4Gate", "DEC3X8Gate", "MUX2Gate", "MUX4Gate"):
            gate_type_str = _class_to_type_str(gate_type_name)
            explicit_outs = output_wire_names if len(output_wire_names) > 1 else None
            new_circuit.add_gate(
                node.name, gate_type_str, input_wire_names,
                primary_output, explicit_outs
            )
            continue

        # If already the target type, keep as-is
        if gate_type_name == "NANDGate" and gate == "nand":
            new_circuit.add_gate(node.name, "NAND", input_wire_names, primary_output)
            continue
        if gate_type_name == "NORGate" and gate == "nor":
            new_circuit.add_gate(node.name, "NOR", input_wire_names, primary_output)
            continue

        # Rebuild using universal gates
        if gate_type_name == "NOTGate":
            _build_not(new_circuit, universal_type, input_wire_names[0], primary_output)
        elif gate_type_name == "ANDGate":
            _build_nary(new_circuit, universal_type, "AND", input_wire_names, primary_output)
        elif gate_type_name == "ORGate":
            _build_nary(new_circuit, universal_type, "OR", input_wire_names, primary_output)
        elif gate_type_name == "NANDGate":
            # NAND = NOT(AND)
            and_wire = f"{node.name}_and{_uid()}"
            _build_nary(new_circuit, universal_type, "AND", input_wire_names, and_wire)
            _build_not(new_circuit, universal_type, and_wire, primary_output)
        elif gate_type_name == "NORGate":
            # NOR = NOT(OR)
            or_wire = f"{node.name}_or{_uid()}"
            _build_nary(new_circuit, universal_type, "OR", input_wire_names, or_wire)
            _build_not(new_circuit, universal_type, or_wire, primary_output)
        elif gate_type_name == "XORGate":
            _build_xor_nary(new_circuit, universal_type, input_wire_names, primary_output)
        elif gate_type_name == "XNORGate":
            # XNOR = NOT(XOR)
            xor_wire = f"{node.name}_xor{_uid()}"
            _build_xor_nary(new_circuit, universal_type, input_wire_names, xor_wire)
            _build_not(new_circuit, universal_type, xor_wire, primary_output)
        else:
            raise ValueError(
                f"Cannot universalize gate type '{gate_type_name}' "
                f"for gate '{node.name}'"
            )

    # Copy primary outputs
    for out_name in circuit.output_names:
        new_circuit.add_output(out_name)

    return new_circuit


# ---------------------------------------------------------------------------
# Internal construction helpers
# ---------------------------------------------------------------------------

def _class_to_type_str(class_name: str) -> str:
    """Convert gate class name to GATE_REGISTRY key."""
    mapping = {
        "NOTGate": "NOT", "ANDGate": "AND", "ORGate": "OR",
        "NANDGate": "NAND", "NORGate": "NOR", "XORGate": "XOR",
        "XNORGate": "XNOR", "MUX2Gate": "MUX2", "MUX4Gate": "MUX4",
        "DEC2X4Gate": "DEC2X4", "DEC3X8Gate": "DEC3X8",
    }
    return mapping[class_name]


def _build_not(
    circuit: Circuit, universal: str,
    input_wire: str, output_wire: str
) -> None:
    """
    Build NOT using universal gates.
    NAND: NOT(A) = NAND(A, A)
    NOR:  NOT(A) = NOR(A, A)
    """
    gname = f"not{_uid()}"
    circuit.add_gate(gname, universal, [input_wire, input_wire], output_wire)


def _build_and_2(
    circuit: Circuit, universal: str,
    a: str, b: str, output_wire: str
) -> None:
    """
    Build 2-input AND using universal gates.
    NAND: AND(A,B) = NAND(NAND(A,B), NAND(A,B))
    NOR:  AND(A,B) = NOR(NOR(A,A), NOR(B,B))
    """
    if universal == "NAND":
        w1 = f"and_nab{_uid()}"
        circuit.add_gate(f"and_g1{_uid()}", "NAND", [a, b], w1)
        circuit.add_gate(f"and_g2{_uid()}", "NAND", [w1, w1], output_wire)
    else:  # NOR
        w_na = f"and_na{_uid()}"
        w_nb = f"and_nb{_uid()}"
        circuit.add_gate(f"and_g1{_uid()}", "NOR", [a, a], w_na)
        circuit.add_gate(f"and_g2{_uid()}", "NOR", [b, b], w_nb)
        circuit.add_gate(f"and_g3{_uid()}", "NOR", [w_na, w_nb], output_wire)


def _build_or_2(
    circuit: Circuit, universal: str,
    a: str, b: str, output_wire: str
) -> None:
    """
    Build 2-input OR using universal gates.
    NAND: OR(A,B) = NAND(NAND(A,A), NAND(B,B))
    NOR:  OR(A,B) = NOR(NOR(A,B), NOR(A,B))
    """
    if universal == "NAND":
        w_na = f"or_na{_uid()}"
        w_nb = f"or_nb{_uid()}"
        circuit.add_gate(f"or_g1{_uid()}", "NAND", [a, a], w_na)
        circuit.add_gate(f"or_g2{_uid()}", "NAND", [b, b], w_nb)
        circuit.add_gate(f"or_g3{_uid()}", "NAND", [w_na, w_nb], output_wire)
    else:  # NOR
        w1 = f"or_nab{_uid()}"
        circuit.add_gate(f"or_g1{_uid()}", "NOR", [a, b], w1)
        circuit.add_gate(f"or_g2{_uid()}", "NOR", [w1, w1], output_wire)


def _build_xor_2(
    circuit: Circuit, universal: str,
    a: str, b: str, output_wire: str
) -> None:
    """
    Build 2-input XOR using universal gates.
    NAND (4 gates): XOR = NAND(NAND(A, NAND(A,B)), NAND(B, NAND(A,B)))
    NOR (5 gates):  W=NOR(A,B); X=NOR(A,W); Y=NOR(B,W); XNOR=NOR(X,Y); XOR=NOR(XNOR,XNOR)
    """
    if universal == "NAND":
        w = f"xor_w{_uid()}"
        x = f"xor_x{_uid()}"
        y = f"xor_y{_uid()}"
        circuit.add_gate(f"xor_g1{_uid()}", "NAND", [a, b], w)
        circuit.add_gate(f"xor_g2{_uid()}", "NAND", [a, w], x)
        circuit.add_gate(f"xor_g3{_uid()}", "NAND", [b, w], y)
        circuit.add_gate(f"xor_g4{_uid()}", "NAND", [x, y], output_wire)
    else:  # NOR
        w = f"xor_w{_uid()}"
        x = f"xor_x{_uid()}"
        y = f"xor_y{_uid()}"
        xnor = f"xor_xnor{_uid()}"
        circuit.add_gate(f"xor_g1{_uid()}", "NOR", [a, b], w)
        circuit.add_gate(f"xor_g2{_uid()}", "NOR", [a, w], x)
        circuit.add_gate(f"xor_g3{_uid()}", "NOR", [b, w], y)
        circuit.add_gate(f"xor_g4{_uid()}", "NOR", [x, y], xnor)
        circuit.add_gate(f"xor_g5{_uid()}", "NOR", [xnor, xnor], output_wire)


def _build_nary(
    circuit: Circuit, universal: str,
    operation: str, input_wires: List[str], output_wire: str
) -> None:
    """
    Build an N-input AND or OR by left-folding 2-input universal constructions.
    """
    if len(input_wires) == 2:
        if operation == "AND":
            _build_and_2(circuit, universal, input_wires[0], input_wires[1], output_wire)
        elif operation == "OR":
            _build_or_2(circuit, universal, input_wires[0], input_wires[1], output_wire)
        return

    # N > 2: fold left
    current = input_wires[0]
    for i, next_wire in enumerate(input_wires[1:]):
        is_last = (i == len(input_wires) - 2)
        step_output = output_wire if is_last else f"chain{_uid()}"

        if operation == "AND":
            _build_and_2(circuit, universal, current, next_wire, step_output)
        elif operation == "OR":
            _build_or_2(circuit, universal, current, next_wire, step_output)

        current = step_output


def _build_xor_nary(
    circuit: Circuit, universal: str,
    input_wires: List[str], output_wire: str
) -> None:
    """
    Build an N-input XOR by left-folding 2-input XOR constructions.
    """
    if len(input_wires) == 2:
        _build_xor_2(circuit, universal, input_wires[0], input_wires[1], output_wire)
        return

    # N > 2: fold left
    current = input_wires[0]
    for i, next_wire in enumerate(input_wires[1:]):
        is_last = (i == len(input_wires) - 2)
        step_output = output_wire if is_last else f"xchain{_uid()}"
        _build_xor_2(circuit, universal, current, next_wire, step_output)
        current = step_output
