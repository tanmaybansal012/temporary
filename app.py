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


@app.route("/api/netlist/simulate", methods=["POST"])
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


@app.route("/api/netlist/truth-table", methods=["POST"])
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


@app.route("/api/netlist/validate", methods=["POST"])
def api_netlist_validate():
    netlist_text = request.json.get("netlist", "")
    try:
        circuit = parse_netlist(netlist_text)
        circuit.topological_sort() # checks for cycles
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/schematic/to-netlist", methods=["POST"])
def api_schematic_to_netlist():
    data = request.json
    nodes = {n["id"]: n for n in data.get("nodes", [])}
    wires = data.get("wires", [])
    
    def get_signal_name(wire):
        src_node = nodes[wire["from"]]
        port = wire["fromPort"]
        if port == "out":
            return src_node["label"]
        return f"{src_node['label']}_{port}"

    incoming = {}
    for w in wires:
        dest_id = w["to"]
        if dest_id not in incoming:
            incoming[dest_id] = []
        incoming[dest_id].append((w["toPort"], get_signal_name(w)))
    
    PORT_ORDER = {
        "AND": ["in0", "in1"],
        "OR": ["in0", "in1"],
        "NAND": ["in0", "in1"],
        "NOR": ["in0", "in1"],
        "XOR": ["in0", "in1"],
        "XNOR": ["in0", "in1"],
        "NOT": ["in0"],
        "MUX2": ["a", "b", "sel"],
        "MUX4": ["d0", "d1", "d2", "d3", "s0", "s1"],
        "DEC2X4": ["a0", "a1", "en"],
        "DEC3X8": ["a0", "a1", "a2", "en"],
        "OUTPUT": ["in"]
    }
    
    lines = []
    
    input_labels = [n["label"] for n in nodes.values() if n["type"] == "INPUT"]
    if input_labels:
        lines.append("INPUT " + " ".join(input_labels))
        
    for n in nodes.values():
        if n["type"] in ("INPUT", "OUTPUT"):
            continue
        gtype = n["type"]
        label = n["label"]
        inc = incoming.get(n["id"], [])
        port_dict = {p: sig for p, sig in inc}
        
        ordered_ins = []
        for p in PORT_ORDER.get(gtype, []):
            ordered_ins.append(port_dict.get(p, "UNCONNECTED"))
            
        gate_line = f"GATE {label} {gtype} " + " ".join(ordered_ins)
        
        if gtype == "DEC2X4":
            gate_line += f" -> {label}_y0 {label}_y1 {label}_y2 {label}_y3"
        elif gtype == "DEC3X8":
            gate_line += f" -> " + " ".join(f"{label}_y{i}" for i in range(8))
            
        lines.append(gate_line)
        
    output_sigs = []
    for n in nodes.values():
        if n["type"] == "OUTPUT":
            inc = incoming.get(n["id"], [])
            if inc:
                output_sigs.append(inc[0][1])
    
    if output_sigs:
        lines.append("OUTPUT " + " ".join(output_sigs))
        
    return jsonify({"netlist": "\n".join(lines)})


@app.route("/api/netlist/to-schematic", methods=["POST"])
def api_netlist_to_schematic():
    netlist_text = request.json.get("netlist", "")
    try:
        circuit = parse_netlist(netlist_text)
        topo = circuit.topological_sort()
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    nodes = []
    wires = []
    
    depths = {}
    for name in circuit.input_names:
        depths[name] = 0
        
    for gnode in topo:
        d = 0
        for w in gnode.input_wires:
            if w.driven_by is None:
                d = max(d, 0)
            else:
                d = max(d, depths.get(w.driven_by.name, 0))
        depths[gnode.name] = d + 1
        
    node_id_map = {}
    X_SPACING = 200
    Y_SPACING = 100
    depth_counts = {}
    
    def add_node(name, type_, label, depth):
        depth_counts[depth] = depth_counts.get(depth, 0) + 1
        nid = f"n{len(nodes)}"
        node_id_map[name] = nid
        nodes.append({
            "id": nid,
            "type": type_,
            "label": label,
            "x": 50 + depth * X_SPACING,
            "y": 50 + (depth_counts[depth] - 1) * Y_SPACING
        })
        return nid

    for name in circuit.input_names:
        add_node(name, "INPUT", name, 0)
        
    for gnode in topo:
        gtype = gnode.gate.__class__.__name__.replace("Gate", "")
        add_node(gnode.name, gtype, gnode.name, depths[gnode.name])
        
    out_depth = max(depths.values()) + 1 if depths else 1
    for out_name in circuit.output_names:
        add_node(out_name + "_OUT", "OUTPUT", out_name, out_depth)
        
    PORT_ORDER = {
        "AND": ["in0", "in1"],
        "OR": ["in0", "in1"],
        "NAND": ["in0", "in1"],
        "NOR": ["in0", "in1"],
        "XOR": ["in0", "in1"],
        "XNOR": ["in0", "in1"],
        "NOT": ["in0"],
        "MUX2": ["a", "b", "sel"],
        "MUX4": ["d0", "d1", "d2", "d3", "s0", "s1"],
        "DEC2X4": ["a0", "a1", "en"],
        "DEC3X8": ["a0", "a1", "a2", "en"]
    }
    
    for gname, gnode in circuit._gates.items():
        gtype = gnode.gate.__class__.__name__.replace("Gate", "")
        ports = PORT_ORDER.get(gtype, [])
        for i, in_wire in enumerate(gnode.input_wires):
            src_node_name = in_wire.driven_by.name if in_wire.driven_by else in_wire.name
            src_id = node_id_map.get(src_node_name)
            to_id = node_id_map[gname]
            to_port = ports[i] if i < len(ports) else f"in{i}"
            
            from_port = "out"
            if in_wire.driven_by and len(in_wire.driven_by.output_wires) > 1:
                idx = in_wire.driven_by.output_wires.index(in_wire)
                from_port = f"y{idx}"
                    
            if src_id:
                wires.append({
                    "from": src_id,
                    "fromPort": from_port,
                    "to": to_id,
                    "toPort": to_port
                })
                
    for out_name in circuit.output_names:
        wire = circuit._wires[out_name]
        src_node_name = wire.driven_by.name if wire.driven_by else wire.name
        src_id = node_id_map.get(src_node_name)
        to_id = node_id_map[out_name + "_OUT"]
        
        from_port = "out"
        if wire.driven_by and len(wire.driven_by.output_wires) > 1:
            idx = wire.driven_by.output_wires.index(wire)
            from_port = f"y{idx}"
            
        if src_id:
            wires.append({
                "from": src_id,
                "fromPort": from_port,
                "to": to_id,
                "toPort": "in"
            })
            
    return jsonify({"nodes": nodes, "wires": wires})


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
