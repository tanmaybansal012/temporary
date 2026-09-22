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
from logic_sim.sequential import SEQUENTIAL_REGISTRY


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
            # Syntax: GATE <name> <type> <in1> [in2 ...] [-> <out1> ...]
            if len(tokens) < 4:
                raise ValueError(
                    f"{source_name}:{lineno}: GATE directive requires at least "
                    f"<name> <type> <input1>. Got: {line!r}"
                )
            gate_name = tokens[1]
            gate_type = tokens[2].upper()
            
            # Check for explicit outputs using "->"
            if "->" in tokens[3:]:
                arrow_idx = tokens.index("->", 3)
                input_wire_names = tokens[3:arrow_idx]
                explicit_output_names = tokens[arrow_idx + 1:]
            else:
                input_wire_names = tokens[3:]
                explicit_output_names = None

            # Validate gate type
            is_sequential = gate_type in SEQUENTIAL_REGISTRY
            if not is_sequential and gate_type not in GATE_REGISTRY:
                valid_types = sorted(list(GATE_REGISTRY.keys()) + list(SEQUENTIAL_REGISTRY.keys()))
                raise ValueError(
                    f"{source_name}:{lineno}: Unknown gate type '{gate_type}'. "
                    f"Valid types: {valid_types}"
                )

            # Validate gate arity
            if gate_type == "NOT" and len(input_wire_names) != 1:
                raise ValueError(
                    f"{source_name}:{lineno}: NOT gate takes exactly 1 input, "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            elif gate_type == "MUX2" and len(input_wire_names) != 3:
                raise ValueError(
                    f"{source_name}:{lineno}: MUX2 gate takes exactly 3 inputs [A, B, SEL], "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            elif gate_type == "MUX4" and len(input_wire_names) != 6:
                raise ValueError(
                    f"{source_name}:{lineno}: MUX4 gate takes exactly 6 inputs [D0..D3, S0, S1], "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            elif gate_type == "DEC2X4" and len(input_wire_names) != 3:
                raise ValueError(
                    f"{source_name}:{lineno}: DEC2X4 gate takes exactly 3 inputs [A0, A1, EN], "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            elif gate_type == "DEC3X8" and len(input_wire_names) != 4:
                raise ValueError(
                    f"{source_name}:{lineno}: DEC3X8 gate takes exactly 4 inputs [A0, A1, A2, EN], "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            elif gate_type == "DFF" and len(input_wire_names) != 2:
                raise ValueError(
                    f"{source_name}:{lineno}: DFF requires exactly 2 inputs [D, CLK], "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            elif gate_type == "JKFF" and len(input_wire_names) != 3:
                raise ValueError(
                    f"{source_name}:{lineno}: JKFF requires exactly 3 inputs [J, K, CLK], "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            elif gate_type == "TFF" and len(input_wire_names) != 2:
                raise ValueError(
                    f"{source_name}:{lineno}: TFF requires exactly 2 inputs [T, CLK], "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            elif gate_type == "SRLATCH" and len(input_wire_names) not in (2, 3):
                raise ValueError(
                    f"{source_name}:{lineno}: SRLATCH requires 2 or 3 inputs [S, R, EN?], "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            elif gate_type == "DLATCH" and len(input_wire_names) not in (1, 2):
                raise ValueError(
                    f"{source_name}:{lineno}: DLATCH requires 1 or 2 inputs [D, EN?], "
                    f"got {len(input_wire_names)}: {input_wire_names}"
                )
            # Validate minimum 2 inputs for other combinational gate types (AND, OR, NAND, NOR, XOR, XNOR)
            elif not is_sequential and gate_type not in ("NOT", "MUX2", "MUX4", "DEC2X4", "DEC3X8") and len(input_wire_names) < 2:
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
                circuit.add_gate(gate_name, gate_type, input_wire_names, output_wire_name, explicit_output_names)
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
