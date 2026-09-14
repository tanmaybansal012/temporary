"""
cli.py — Command-line interface for the Digital Logic Simulator.

Subcommands:
  simulate         Evaluate a netlist for specific input values
  truth-table      Print the full truth table for a combinational netlist
  demo-flipflop    Run a flip-flop for N clock cycles, print state transition
                   table, save waveform PNG
  verify-conversion  Verify a universal gate conversion against the native gate

Usage:
  python -m logic_sim.cli simulate --netlist examples/full_adder.net --inputs "A=1,B=0,CIN=1"
  python -m logic_sim.cli truth-table --netlist examples/full_adder.net
  python -m logic_sim.cli demo-flipflop --type jk --cycles 8
  python -m logic_sim.cli verify-conversion --gate xor --using nand
"""

from __future__ import annotations
import argparse
import itertools
import os
import sys
from typing import Dict, List

from logic_sim.signal import Signal
from logic_sim.netlist_parser import parse_netlist_file
from logic_sim.truth_table import (
    generate_truth_table,
    print_truth_table,
    generate_state_transition_table,
    print_state_transition_table,
)
from logic_sim.sequential import DFlipFlop, JKFlipFlop, TFlipFlop, SRLatch
from logic_sim.gate_conversion import (
    nand_and, nand_or, nand_not, nand_xor,
    nor_and, nor_or, nor_not, nor_xor,
)
from logic_sim.gates import ANDGate, ORGate, NOTGate, XORGate
from logic_sim.waveform import plot_waveform


# ---------------------------------------------------------------------------
# Subcommand: simulate
# ---------------------------------------------------------------------------

def cmd_simulate(args: argparse.Namespace) -> None:
    """
    Load a netlist and evaluate it for specified input values.

    Example:
        python -m logic_sim.cli simulate \\
            --netlist examples/full_adder.net \\
            --inputs "A=1,B=0,CIN=1"
    """
    if not os.path.exists(args.netlist):
        print(f"Error: Netlist file not found: {args.netlist}", file=sys.stderr)
        sys.exit(1)

    try:
        circuit = parse_netlist_file(args.netlist)
    except ValueError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse --inputs "A=1,B=0,CIN=1"
    input_values: Dict[str, Signal] = {}
    if args.inputs:
        for part in args.inputs.split(","):
            part = part.strip()
            if "=" not in part:
                print(
                    f"Error: Invalid input format '{part}'. "
                    f"Expected name=value (e.g. A=1).",
                    file=sys.stderr,
                )
                sys.exit(1)
            name, val_str = part.split("=", 1)
            name = name.strip()
            val_str = val_str.strip()
            try:
                input_values[name] = Signal.from_str(val_str)
            except ValueError as e:
                print(f"Error parsing input '{part}': {e}", file=sys.stderr)
                sys.exit(1)

    # Fill any missing inputs with UNKNOWN
    for inp_name in circuit.input_names:
        if inp_name not in input_values:
            input_values[inp_name] = Signal.UNKNOWN

    try:
        outputs = circuit.evaluate(input_values)
    except Exception as e:
        print(f"Simulation error: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n=== Simulation Results ===")
    print(f"Netlist : {args.netlist}")
    print()
    print("Inputs:")
    for name in circuit.input_names:
        print(f"  {name} = {input_values[name]}")
    print()
    print("Outputs:")
    for name, val in outputs.items():
        print(f"  {name} = {val}")
    print()


# ---------------------------------------------------------------------------
# Subcommand: truth-table
# ---------------------------------------------------------------------------

def cmd_truth_table(args: argparse.Namespace) -> None:
    """
    Load a netlist and print the full truth table for all 2^n input combinations.

    Example:
        python -m logic_sim.cli truth-table --netlist examples/full_adder.net
    """
    if not os.path.exists(args.netlist):
        print(f"Error: Netlist file not found: {args.netlist}", file=sys.stderr)
        sys.exit(1)

    try:
        circuit = parse_netlist_file(args.netlist)
    except ValueError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    n_inputs = len(circuit.input_names)
    print(f"\n=== Truth Table: {args.netlist} ===")
    print(f"Inputs  : {', '.join(circuit.input_names)}")
    print(f"Outputs : {', '.join(circuit.output_names)}")
    print(f"Rows    : {2 ** n_inputs}")
    print()

    rows = generate_truth_table(circuit)
    print_truth_table(rows, circuit.input_names, circuit.output_names)
    print()


# ---------------------------------------------------------------------------
# Subcommand: demo-flipflop
# ---------------------------------------------------------------------------

_FLIPFLOP_TYPES = {
    "d":  DFlipFlop,
    "jk": JKFlipFlop,
    "t":  TFlipFlop,
    "sr": SRLatch,
}

_SAMPLE_PATTERNS: Dict[str, Dict[str, List[int]]] = {
    "d": {
        # D alternates every 2 cycles; CLK toggles every cycle
        "D":   [0, 0, 1, 1, 0, 0, 1, 1],
        "CLK": [0, 1, 0, 1, 0, 1, 0, 1],
    },
    "jk": {
        # Covers hold (0,0), reset (0,1), set (1,0), toggle (1,1) in rotation
        "J":   [0, 0, 1, 1, 0, 0, 1, 1],
        "K":   [0, 1, 0, 1, 0, 1, 0, 1],
        "CLK": [0, 1, 0, 1, 0, 1, 0, 1],
    },
    "t": {
        "T":   [0, 0, 1, 1, 0, 1, 1, 1],
        "CLK": [0, 1, 0, 1, 0, 1, 0, 1],
    },
    "sr": {
        "S":   [0, 1, 0, 0, 1, 0, 0, 1],
        "R":   [0, 0, 1, 0, 0, 0, 1, 1],  # last cycle is S=R=1 (forbidden)
        "En":  [1, 1, 1, 1, 1, 1, 1, 1],
    },
}


def cmd_demo_flipflop(args: argparse.Namespace) -> None:
    """
    Simulate a flip-flop/latch for N clock cycles with a sample input pattern.

    Prints:
      - The input/output trace table
      - The state transition table
    Saves a waveform PNG to <type>_flipflop_waveform.png.

    Example:
        python -m logic_sim.cli demo-flipflop --type jk --cycles 8
    """
    ff_type = args.type.lower()
    if ff_type not in _FLIPFLOP_TYPES:
        print(
            f"Error: Unknown flip-flop type '{args.type}'. "
            f"Valid: {list(_FLIPFLOP_TYPES.keys())}",
            file=sys.stderr,
        )
        sys.exit(1)

    cycles = args.cycles
    ff_cls = _FLIPFLOP_TYPES[ff_type]

    # For SR latch, use SRLatch (no clock_edge); others get rising-edge FF
    if ff_type == "sr":
        ff = ff_cls()
    else:
        ff = ff_cls(clock_edge="rising")

    # Get sample patterns; repeat/truncate to requested cycle count
    base_pattern = _SAMPLE_PATTERNS[ff_type]
    input_names = list(base_pattern.keys())
    extended = {}
    for name, vals in base_pattern.items():
        # Tile the pattern to cover 'cycles' steps
        tiled = (vals * ((cycles // len(vals)) + 1))[:cycles]
        extended[name] = tiled

    # Simulate
    print(f"\n=== Demo: {ff_type.upper()} {'Latch' if ff_type == 'sr' else 'Flip-Flop'} "
          f"({cycles} cycles) ===")

    q_trace: List[Signal] = []
    cycle_table: List[Dict] = []

    # Determine non-CLK input names for the table
    data_inputs = [n for n in input_names if n != "CLK"]

    for cycle_idx in range(cycles):
        inp: Dict[str, Signal] = {
            name: Signal.from_int(extended[name][cycle_idx])
            for name in input_names
        }
        q = ff.clock_tick(inp)
        q_trace.append(q)

        row = {"Cycle": cycle_idx}
        for name in input_names:
            row[name] = Signal.from_int(extended[name][cycle_idx])
        row["Q"] = q
        cycle_table.append(row)

    # Print trace table
    all_cols = ["Cycle"] + input_names + ["Q"]
    col_w = 7
    header = "".join(f"{c:^{col_w}}" for c in all_cols)
    sep = "-" * len(header)
    print(header)
    print(sep)
    for row in cycle_table:
        line = "".join(f"{str(row[c]):^{col_w}}" for c in all_cols)
        print(line)
    print()

    # Print state transition table (only for edge-triggered FF types)
    if ff_type != "sr":
        print(f"--- State Transition Table ({ff_type.upper()} FF) ---")
        ff2 = ff_cls(clock_edge="rising")
        stt_rows = generate_state_transition_table(ff2, data_inputs + ["CLK"])
        print_state_transition_table(stt_rows, data_inputs + ["CLK"])
        print()

    # Build waveform signal dict
    wf_signals: Dict[str, List[Signal]] = {}
    for name in input_names:
        wf_signals[name] = [Signal.from_int(v) for v in extended[name]]
    wf_signals["Q"] = q_trace

    output_file = f"{ff_type}_flipflop_waveform.png"
    saved = plot_waveform(
        wf_signals,
        title=f"{ff_type.upper()} {'Latch' if ff_type == 'sr' else 'Flip-Flop'} Timing Diagram",
        output_path=output_file,
    )
    print(f"Waveform saved to: {os.path.abspath(saved)}")


# ---------------------------------------------------------------------------
# Subcommand: verify-conversion
# ---------------------------------------------------------------------------

# Native gate evaluators (2-input, returning Signal)
def _native_and(a: Signal, b: Signal) -> Signal:
    g = ANDGate(); g.inputs = [a, b]; return g.evaluate()

def _native_or(a: Signal, b: Signal) -> Signal:
    g = ORGate(); g.inputs = [a, b]; return g.evaluate()

def _native_not(a: Signal) -> Signal:
    g = NOTGate(); g.inputs = [a]; return g.evaluate()

def _native_xor(a: Signal, b: Signal) -> Signal:
    g = XORGate(); g.inputs = [a, b]; return g.evaluate()


_NATIVE_GATES = {
    "and": _native_and,
    "or":  _native_or,
    "not": _native_not,
    "xor": _native_xor,
}

_CONVERSION_FNS = {
    ("and",  "nand"): nand_and,
    ("or",   "nand"): nand_or,
    ("not",  "nand"): nand_not,
    ("xor",  "nand"): nand_xor,
    ("and",  "nor"):  nor_and,
    ("or",   "nor"):  nor_or,
    ("not",  "nor"):  nor_not,
    ("xor",  "nor"):  nor_xor,
}


def cmd_verify_conversion(args: argparse.Namespace) -> None:
    """
    Build a gate from universal gates and compare its truth table to the native gate.

    Example:
        python -m logic_sim.cli verify-conversion --gate xor --using nand
    """
    gate_name = args.gate.lower()
    using = args.using.lower()

    valid_gates = ["and", "or", "not", "xor"]
    valid_using = ["nand", "nor"]

    if gate_name not in valid_gates:
        print(f"Error: --gate must be one of {valid_gates}", file=sys.stderr)
        sys.exit(1)
    if using not in valid_using:
        print(f"Error: --using must be one of {valid_using}", file=sys.stderr)
        sys.exit(1)

    key = (gate_name, using)
    if key not in _CONVERSION_FNS:
        print(f"Error: No conversion defined for {gate_name!r} using {using!r}.", file=sys.stderr)
        sys.exit(1)

    native_fn = _NATIVE_GATES[gate_name]
    conv_fn = _CONVERSION_FNS[key]
    is_unary = (gate_name == "not")

    print(f"\n=== Verify: {gate_name.upper()} built from {using.upper()} gates ===\n")

    inputs_range = [0, 1]
    combos = [(a,) for a in inputs_range] if is_unary else list(itertools.product(inputs_range, repeat=2))

    # Build both truth tables
    col_w = 10
    if is_unary:
        header = f"{'A':^{col_w}}{'Native':^{col_w}}{using.upper():^{col_w}}{'Match':^{col_w}}"
    else:
        header = f"{'A':^{col_w}}{'B':^{col_w}}{'Native':^{col_w}}{using.upper():^{col_w}}{'Match':^{col_w}}"

    sep = "-" * len(header)
    print(header)
    print(sep)

    all_match = True
    for combo in combos:
        sigs = [Signal.from_int(v) for v in combo]
        native_out = native_fn(*sigs)
        conv_out = conv_fn(*sigs)
        match = "✓" if native_out == conv_out else "✗ MISMATCH"
        if native_out != conv_out:
            all_match = False

        if is_unary:
            a_s = str(sigs[0])
            print(f"{a_s:^{col_w}}{str(native_out):^{col_w}}{str(conv_out):^{col_w}}{match:^{col_w}}")
        else:
            a_s, b_s = str(sigs[0]), str(sigs[1])
            print(f"{a_s:^{col_w}}{b_s:^{col_w}}{str(native_out):^{col_w}}{str(conv_out):^{col_w}}{match:^{col_w}}")

    print(sep)
    if all_match:
        print(f"\n✓ PASS — {using.upper()}-built {gate_name.upper()} is equivalent to native {gate_name.upper()}.")
    else:
        print(f"\n✗ FAIL — Truth tables do not match!")
    print()


# ---------------------------------------------------------------------------
# Main parser assembly
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logic_sim",
        description=(
            "Digital Logic Simulator — gate-level simulation, truth tables, "
            "flip-flop demos, and universal gate conversion verification."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m logic_sim.cli simulate --netlist examples/full_adder.net --inputs "A=1,B=0,CIN=1"
  python -m logic_sim.cli truth-table --netlist examples/full_adder.net
  python -m logic_sim.cli demo-flipflop --type jk --cycles 8
  python -m logic_sim.cli verify-conversion --gate xor --using nand
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # simulate
    p_sim = subparsers.add_parser(
        "simulate",
        help="Evaluate a netlist for specific input values.",
    )
    p_sim.add_argument(
        "--netlist", required=True,
        help="Path to the .net netlist file.",
    )
    p_sim.add_argument(
        "--inputs", default="",
        help='Comma-separated input assignments, e.g. "A=1,B=0,CIN=1".',
    )
    p_sim.set_defaults(func=cmd_simulate)

    # truth-table
    p_tt = subparsers.add_parser(
        "truth-table",
        help="Print the full truth table for a combinational netlist.",
    )
    p_tt.add_argument(
        "--netlist", required=True,
        help="Path to the .net netlist file.",
    )
    p_tt.set_defaults(func=cmd_truth_table)

    # demo-flipflop
    p_ff = subparsers.add_parser(
        "demo-flipflop",
        help="Simulate a flip-flop/latch and save a waveform PNG.",
    )
    p_ff.add_argument(
        "--type", required=True,
        choices=["d", "jk", "t", "sr"],
        help="Flip-flop type: d, jk, t, or sr.",
    )
    p_ff.add_argument(
        "--cycles", type=int, default=8,
        help="Number of clock cycles to simulate (default: 8).",
    )
    p_ff.set_defaults(func=cmd_demo_flipflop)

    # verify-conversion
    p_vc = subparsers.add_parser(
        "verify-conversion",
        help="Verify a universal gate conversion against the native gate.",
    )
    p_vc.add_argument(
        "--gate", required=True,
        choices=["and", "or", "not", "xor"],
        help="Gate to verify.",
    )
    p_vc.add_argument(
        "--using", required=True,
        choices=["nand", "nor"],
        help="Universal gate to use in the construction.",
    )
    p_vc.set_defaults(func=cmd_verify_conversion)

    return parser


def main() -> None:
    """Entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
