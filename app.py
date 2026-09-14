"""
app.py — Flask backend for the Digital Logic Simulator Web UI.
"""

import base64
import itertools
import os
from io import BytesIO
from typing import Dict, List, Any

from flask import Flask, request, jsonify, render_template

from logic_sim.signal import Signal
from logic_sim.netlist_parser import parse_netlist
from logic_sim.truth_table import (
    generate_truth_table,
    generate_state_transition_table,
)
from logic_sim.sequential import DFlipFlop, JKFlipFlop, TFlipFlop, SRLatch
from logic_sim.gate_conversion import (
    nand_and, nand_or, nand_not, nand_xor,
    nor_and, nor_or, nor_not, nor_xor,
)
from logic_sim.gates import ANDGate, ORGate, NOTGate, XORGate
from logic_sim.waveform import plot_waveform

app = Flask(__name__)

# Ensure scratch directory for temporary files
os.makedirs("scratch", exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    data = request.json
    netlist_text = data.get("netlist", "")
    inputs_raw = data.get("inputs", {})

    try:
        circuit = parse_netlist(netlist_text)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    input_values = {}
    for name, val_str in inputs_raw.items():
        try:
            input_values[name] = Signal.from_str(str(val_str))
        except ValueError as e:
            return jsonify({"error": f"Invalid input for {name}: {e}"}), 400

    for inp_name in circuit.input_names:
        if inp_name not in input_values:
            input_values[inp_name] = Signal.UNKNOWN

    try:
        outputs = circuit.evaluate(input_values)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "inputs": {k: str(v) for k, v in input_values.items()},
        "outputs": {k: str(v) for k, v in outputs.items()}
    })


@app.route("/api/truth-table", methods=["POST"])
def api_truth_table():
    data = request.json
    netlist_text = data.get("netlist", "")

    try:
        circuit = parse_netlist(netlist_text)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    rows = generate_truth_table(circuit)
    
    # Format for JSON
    json_rows = []
    for row in rows:
        json_rows.append({k: str(v) for k, v in row.items()})

    return jsonify({
        "input_names": circuit.input_names,
        "output_names": circuit.output_names,
        "rows": json_rows
    })


@app.route("/api/demo-flipflop", methods=["POST"])
def api_demo_flipflop():
    data = request.json
    ff_type = data.get("type", "jk").lower()
    cycles = int(data.get("cycles", 8))

    _FLIPFLOP_TYPES = {
        "d":  DFlipFlop,
        "jk": JKFlipFlop,
        "t":  TFlipFlop,
        "sr": SRLatch,
    }

    _SAMPLE_PATTERNS = {
        "d": {
            "D":   [0, 0, 1, 1, 0, 0, 1, 1],
            "CLK": [0, 1, 0, 1, 0, 1, 0, 1],
        },
        "jk": {
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
            "R":   [0, 0, 1, 0, 0, 0, 1, 1],
            "En":  [1, 1, 1, 1, 1, 1, 1, 1],
        },
    }

    if ff_type not in _FLIPFLOP_TYPES:
        return jsonify({"error": f"Unknown type {ff_type}"}), 400

    ff_cls = _FLIPFLOP_TYPES[ff_type]
    ff = ff_cls() if ff_type == "sr" else ff_cls(clock_edge="rising")
    base_pattern = _SAMPLE_PATTERNS[ff_type]
    input_names = list(base_pattern.keys())
    
    extended = {}
    for name, vals in base_pattern.items():
        extended[name] = (vals * ((cycles // len(vals)) + 1))[:cycles]

    q_trace = []
    cycle_table = []

    for cycle_idx in range(cycles):
        inp = {name: Signal.from_int(extended[name][cycle_idx]) for name in input_names}
        q = ff.clock_tick(inp)
        q_trace.append(q)

        row = {"Cycle": cycle_idx}
        for name in input_names:
            row[name] = str(Signal.from_int(extended[name][cycle_idx]))
        row["Q"] = str(q)
        cycle_table.append(row)

    # State transition table
    stt = None
    data_inputs = [n for n in input_names if n != "CLK"]
    if ff_type != "sr":
        ff2 = ff_cls(clock_edge="rising")
        stt_rows = generate_state_transition_table(ff2, data_inputs + ["CLK"])
        stt = []
        for row in stt_rows:
            stt.append({k: str(v) for k, v in row.items()})

    # Plot waveform and encode to base64
    wf_signals = {}
    for name in input_names:
        wf_signals[name] = [Signal.from_int(v) for v in extended[name]]
    wf_signals["Q"] = q_trace

    output_file = f"scratch/{ff_type}_waveform.png"
    plot_waveform(
        wf_signals,
        title=f"{ff_type.upper()} {'Latch' if ff_type == 'sr' else 'Flip-Flop'} Timing Diagram",
        output_path=output_file,
    )

    with open(output_file, "rb") as img_file:
        img_b64 = base64.b64encode(img_file.read()).decode("utf-8")

    return jsonify({
        "trace_columns": ["Cycle"] + input_names + ["Q"],
        "trace": cycle_table,
        "stt_columns": (["Q_current"] + data_inputs + ["Q_next"]) if stt else [],
        "stt": stt,
        "image_b64": f"data:image/png;base64,{img_b64}"
    })


@app.route("/api/verify-conversion", methods=["POST"])
def api_verify_conversion():
    data = request.json
    gate_name = data.get("gate", "xor").lower()
    using = data.get("using", "nand").lower()

    def _native_and(a, b): g = ANDGate(); g.inputs = [a, b]; return g.evaluate()
    def _native_or(a, b): g = ORGate(); g.inputs = [a, b]; return g.evaluate()
    def _native_not(a): g = NOTGate(); g.inputs = [a]; return g.evaluate()
    def _native_xor(a, b): g = XORGate(); g.inputs = [a, b]; return g.evaluate()

    _NATIVE_GATES = {"and": _native_and, "or": _native_or, "not": _native_not, "xor": _native_xor}
    _CONVERSION_FNS = {
        ("and", "nand"): nand_and, ("or", "nand"): nand_or,
        ("not", "nand"): nand_not, ("xor", "nand"): nand_xor,
        ("and", "nor"): nor_and, ("or", "nor"): nor_or,
        ("not", "nor"): nor_not, ("xor", "nor"): nor_xor,
    }

    if gate_name not in _NATIVE_GATES or using not in ["nand", "nor"]:
        return jsonify({"error": "Invalid gate or universal type"}), 400

    native_fn = _NATIVE_GATES[gate_name]
    conv_fn = _CONVERSION_FNS[(gate_name, using)]
    is_unary = (gate_name == "not")
    
    L, H = Signal.LOW, Signal.HIGH
    inputs_range = [L, H]
    combos = [(a,) for a in inputs_range] if is_unary else list(itertools.product(inputs_range, repeat=2))

    rows = []
    all_match = True

    for combo in combos:
        native_out = native_fn(*combo)
        conv_out = conv_fn(*combo)
        match = (native_out == conv_out)
        if not match:
            all_match = False
        
        row = {
            "A": str(combo[0]),
            "Native": str(native_out),
            "Converted": str(conv_out),
            "Match": "OK" if match else "MISMATCH"
        }
        if not is_unary:
            row["B"] = str(combo[1])
        rows.append(row)

    return jsonify({
        "is_unary": is_unary,
        "rows": rows,
        "all_match": all_match
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
