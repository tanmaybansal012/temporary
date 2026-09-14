"""
netlist_parser.py — Parse text netlist files into Circuit objects.

Netlist Format Specification
============================

Lines are processed in order. Blank lines and lines starting with '#' are
ignored as comments. Tokens are whitespace-separated.

Directives:

  INPUT <wire1> [wire2 ...]
      Declare one or more primary input wires.
      Example: INPUT A B CIN

  GATE <gate_name> <gate_type> <input1> [input2 ...]
      Add a gate driving an implicitly-created output wire named <gate_name>.
      The wire driven by this gate will have the same name as the gate itself.
      Example: GATE XOR1 XOR A B
        → creates a wire "XOR1" driven by an XOR gate reading wires A and B.

  OUTPUT <wire1> [wire2 ...]
      Declare which wires are primary outputs (must have been driven by a GATE
      or declared as INPUT first).
      Example: OUTPUT XOR1 AND1

Error handling:
  - Unknown gate types → ValueError with line number
  - Duplicate gate names → ValueError with line number
  - References to undeclared wires in OUTPUT → these are created as output wires
    (the Circuit will evaluate them as UNKNOWN if not driven)
  - All errors include the offending line number for easy debugging
"""

from __future__ import annotations
from typing import List

from logic_sim.circuit import Circuit
from logic_sim.gates import GATE_REGISTRY


def parse_netlist(text: str, source_name: str = "<string>") -> Circuit:
    """
    Parse a netlist text and return a configured Circuit.

    Args:
        text:        Full text content of the netlist file.
        source_name: A label for error messages (e.g. the filename).

    Returns:
        A Circuit object ready for evaluation.

    Raises:
        ValueError: On any syntax or semantic error, including the line number.
    """
    circuit = Circuit()

    # Track all wire names referenced so we can validate OUTPUT declarations
    declared_inputs: set[str] = set()
    declared_gates: dict[str, int] = {}  # gate_name → line_number

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        tokens = line.split()
        directive = tokens[0].upper()

        if directive == "INPUT":
            if len(tokens) < 2:
                raise ValueError(
                    f"{source_name}:{lineno}: INPUT directive requires at least "
                    f"one wire name. Got: {line!r}"
                )
            for wire_name in tokens[1:]:
                if wire_name in declared_gates:
                    raise ValueError(
                        f"{source_name}:{lineno}: '{wire_name}' was already declared "
                        f"as a gate output (line {declared_gates[wire_name]}). "
                        f"Cannot also declare it as a primary input."
                    )
                circuit.add_input(wire_name)
                declared_inputs.add(wire_name)

        elif directive == "GATE":
            # Syntax: GATE <name> <type> <in1> [in2 ...]
            if len(tokens) < 4:
                raise ValueError(
                    f"{source_name}:{lineno}: GATE directive requires at least "
                    f"<name> <type> <input1>. Got: {line!r}"
                )
            gate_name = tokens[1]
            gate_type = tokens[2].upper()
            input_wire_names = tokens[3:]

            # Validate gate type
            if gate_type not in GATE_REGISTRY:
                raise ValueError(
                    f"{source_name}:{lineno}: Unknown gate type '{gate_type}'. "
                    f"Valid types: {sorted(GATE_REGISTRY.keys())}"
                )

            # Validate NOT gate arity
            if gate_type == "NOT" and len(input_wire_names) != 1:
                raise ValueError(
                    f"{source_name}:{lineno}: NOT gate takes exactly 1 input, "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )

            # Validate minimum 2 inputs for other gate types
            if gate_type != "NOT" and len(input_wire_names) < 2:
                raise ValueError(
                    f"{source_name}:{lineno}: {gate_type} gate requires at least "
                    f"2 inputs, got {len(input_wire_names)}: {input_wire_names}"
                )

            # Check for duplicate gate names
            if gate_name in declared_gates:
                raise ValueError(
                    f"{source_name}:{lineno}: Duplicate gate name '{gate_name}'. "
                    f"First declared at line {declared_gates[gate_name]}."
                )

            # The output wire name matches the gate name (convention)
            output_wire_name = gate_name

            try:
                circuit.add_gate(gate_name, gate_type, input_wire_names, output_wire_name)
            except ValueError as e:
                raise ValueError(f"{source_name}:{lineno}: {e}") from e

            declared_gates[gate_name] = lineno

        elif directive == "OUTPUT":
            if len(tokens) < 2:
                raise ValueError(
                    f"{source_name}:{lineno}: OUTPUT directive requires at least "
                    f"one wire name. Got: {line!r}"
                )
            for wire_name in tokens[1:]:
                circuit.add_output(wire_name)

        else:
            raise ValueError(
                f"{source_name}:{lineno}: Unknown directive '{directive}'. "
                f"Expected INPUT, GATE, or OUTPUT. Got: {line!r}"
            )

    return circuit


def parse_netlist_file(filepath: str) -> Circuit:
    """
    Read a netlist file from disk and parse it into a Circuit.

    Args:
        filepath: Path to the .net file.

    Returns:
        A fully configured Circuit object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        On any parse error (includes line numbers).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    return parse_netlist(text, source_name=filepath)
