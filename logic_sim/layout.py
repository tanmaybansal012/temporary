"""
layout.py — Compute a layered layout for circuit visualization.

Reuses the existing topological sort machinery from circuit.py for gate
ordering and cycle detection. Assigns each gate to a layer based on its
dependency depth: primary inputs are at layer 0, and each gate's layer
is 1 + max(layer of its input sources).

Within each layer, gates are ordered by their original declaration order
for a stable, non-crossing-optimized y-coordinate.
"""

from __future__ import annotations
from typing import Dict, List, Tuple

from logic_sim.circuit import Circuit


def compute_layout(circuit: Circuit) -> Dict[str, Tuple[int, int]]:
    """
    Compute a simple layered layout for circuit visualization.

    Algorithm:
      1. Call circuit.topological_sort() (reuses Kahn's algorithm —
         no duplication of cycle detection).
      2. Assign each primary input to layer 0.
      3. For each gate in topological order:
         layer = 1 + max(layer of its input sources)
         where an input source's layer is 0 if it's a primary input,
         or the layer of the gate that drives it.
      4. Within each layer, order by original declaration order for
         stable y-coordinates.

    Args:
        circuit: A fully constructed Circuit with declared inputs and outputs.

    Returns:
        Dict mapping each element name (inputs + gates + outputs) to (x, y)
        where x = layer index, y = position within layer.

    Raises:
        CombinationalCycleError: If the circuit has feedback loops.
    """
    layout: Dict[str, Tuple[int, int]] = {}

    # Wire-to-layer mapping: tracks the layer of each wire's source
    wire_layer: Dict[str, int] = {}

    # Primary inputs are at layer 0
    for i, inp_name in enumerate(circuit.input_names):
        wire_layer[inp_name] = 0

    # Walk gates in topological order to compute layers
    gate_layers: Dict[int, List[str]] = {}  # layer → list of gate names

    for node in circuit.topological_sort():
        # Compute this gate's layer: 1 + max of all input wire layers
        max_input_layer = 0
        for w in node.input_wires:
            max_input_layer = max(max_input_layer, wire_layer.get(w.name, 0))
        gate_layer = max_input_layer + 1

        # Record the layer for this gate's output wire(s)
        for w in node.output_wires:
            wire_layer[w.name] = gate_layer

        # Group by layer
        if gate_layer not in gate_layers:
            gate_layers[gate_layer] = []
        gate_layers[gate_layer].append(node.name)

    # Assign coordinates: primary inputs at layer 0
    for i, inp_name in enumerate(circuit.input_names):
        layout[inp_name] = (0, i)

    # Assign coordinates: gates at their computed layers
    for layer, names in sorted(gate_layers.items()):
        for y_pos, name in enumerate(names):
            layout[name] = (layer, y_pos)

    return layout
