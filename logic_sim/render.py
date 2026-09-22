"""
render.py — Render a Circuit as a schematic diagram using schemdraw.

Takes a Circuit and an optional layout from layout.py, instantiates
schemdraw logic elements (AND, OR, NOT, NAND, NOR, XOR, XNOR) at layer
coordinates, connects wires between gates, and outputs a PNG or SVG image.
"""

from __future__ import annotations
import os
from typing import Dict, Tuple, Optional

import schemdraw
import schemdraw.elements as elm
import schemdraw.logic as logic

from logic_sim.circuit import Circuit
from logic_sim.layout import compute_layout

GATE_MAP = {
    "AND": logic.And,
    "OR": logic.Or,
    "NOT": logic.Not,
    "NAND": logic.Nand,
    "NOR": logic.Nor,
    "XOR": logic.Xor,
    "XNOR": logic.Xnor,
}


def render_circuit(
    circuit: Circuit,
    layout: Optional[Dict[str, Tuple[int, int]]] = None,
    output_path: str = "circuit.png",
) -> str:
    """
    Render a circuit diagram to an image file (PNG or SVG).

    Args:
        circuit: The Circuit to render.
        layout: Optional precomputed layout mapping node names to (x_layer, y_pos).
                If None, compute_layout(circuit) will be called.
        output_path: Target filename (e.g. 'diagram.png' or 'diagram.svg').

    Returns:
        The absolute path to the generated image file.
    """
    if layout is None:
        layout = compute_layout(circuit)

    d = schemdraw.Drawing(show=False)

    x_scale = 4.5
    y_scale = 2.5

    # Track placed elements and wire output endpoints
    placed_elements: Dict[str, schemdraw.elements.Element] = {}
    wire_sources: Dict[str, Tuple[float, float]] = {}

    # 1. Place Primary Inputs
    for inp_name in circuit.input_names:
        lx, ly = layout.get(inp_name, (0, 0))
        pos = (lx * x_scale, -ly * y_scale)
        d.add(elm.Dot().at(pos).label(inp_name, loc="left"))
        wire_sources[inp_name] = pos

    # 2. Place Gates
    for gname in circuit.gate_names:
        gnode = circuit.get_gate(gname)
        raw_type = gnode.gate.__class__.__name__
        gtype = raw_type[:-4].upper() if raw_type.endswith("Gate") else raw_type.upper()
        lx, ly = layout.get(gname, (1, 0))
        pos = (lx * x_scale, -ly * y_scale)

        num_inputs = len(gnode.input_wires)
        if gtype in GATE_MAP:
            cls = GATE_MAP[gtype]
            if gtype == "NOT":
                elem = cls().at(pos).label(gname, loc="bottom")
            else:
                elem = cls(inputs=max(2, num_inputs)).at(pos).label(gname, loc="bottom")
        else:
            # Box for MUX / DEC / custom gates
            elem = logic.Box(w=2, h=1.5).at(pos).label(f"{gtype}\n{gname}")

        d.add(elem)
        placed_elements[gname] = elem

        # Output wire position
        # Obtain 'out' anchor if present, otherwise absdrop
        out_anchor = getattr(elem, "out", getattr(elem, "absdrop", pos))
        for out_w in gnode.output_wires:
            wire_sources[out_w.name] = out_anchor

    # 3. Draw Wires to Gate Inputs
    for gname in circuit.gate_names:
        gnode = circuit.get_gate(gname)
        elem = placed_elements[gname]

        for i, in_wire in enumerate(gnode.input_wires):
            if in_wire.name in wire_sources:
                src_pos = wire_sources[in_wire.name]
                # Target anchor name for input pin (in1, in2, etc.)
                in_anchor_name = f"in{i + 1}"
                if hasattr(elem, in_anchor_name):
                    target_anchor = getattr(elem, in_anchor_name)
                else:
                    target_anchor = getattr(elem, "in1", pos)

                d.add(logic.Wire("|-").at(src_pos).to(target_anchor))

    # 4. Primary Outputs
    max_x = max([coord[0] for coord in layout.values()]) if layout else 1
    out_x = (max_x + 1) * x_scale

    for out_name in circuit.output_names:
        if out_name in wire_sources:
            src_pos = wire_sources[out_name]
            # If src_pos is an anchor object with x/y, get coordinates
            if hasattr(src_pos, "x") and hasattr(src_pos, "y"):
                sy = src_pos.y
            elif isinstance(src_pos, tuple):
                sy = src_pos[1]
            else:
                sy = 0.0

            d.add(
                logic.Wire("-|")
                .at(src_pos)
                .to((out_x, sy))
                .label(out_name, loc="right")
            )

    # Save drawing
    abs_path = os.path.abspath(output_path)
    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    d.save(abs_path)
    return abs_path
