"""
circuit.py — Circuit graph, topological sort, and combinational evaluator.

Architecture:
  - A Circuit holds a directed acyclic graph (DAG) of Gate instances connected
    by named wires (nets).
  - Primary inputs are named wire sources with no driving gate.
  - Gate outputs drive wires; gate inputs read from wires.
  - Topological sort determines the gate evaluation order so that every gate's
    inputs are resolved before that gate is evaluated.

Design decision — topological sort vs. iterative settling:
  We use an explicit Kahn's-algorithm topological sort rather than iterative
  relaxation (simulate until stable). This has two advantages:
    1. O(V + E) deterministic runtime — no oscillation or cycle-detection races.
    2. Combinational cycles (feedback without registers) are detected immediately
       and raise a clear error rather than silently looping forever.
  Real HDL simulators (Verilog/VHDL) do the same for combinational processes;
  sequential feedback is handled separately in sequential.py.
"""

from __future__ import annotations
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from logic_sim.gates import Gate, GATE_REGISTRY
from logic_sim.signal import Signal


class Wire:
    """
    Represents a named net/wire in the circuit.

    Attributes:
        name:         The wire's identifier string.
        value:        Current Signal value on this wire.
        driven_by:    The GateNode whose output drives this wire, or None if it
                      is a primary input.
        is_primary_input:  True if this wire is declared as a circuit input.
        is_primary_output: True if this wire is declared as a circuit output.
    """

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.value: Signal = Signal.UNKNOWN
        self.driven_by: Optional["GateNode"] = None
        self.is_primary_input: bool = False
        self.is_primary_output: bool = False

    def __repr__(self) -> str:
        return f"Wire({self.name!r}, value={self.value})"


class GateNode:
    """
    Wraps a Gate instance with connectivity information.

    Attributes:
        name:       Unique identifier for this gate in the circuit.
        gate:       The underlying Gate instance.
        input_wires:  Ordered list of Wire objects feeding this gate.
        output_wires: List of Wire objects driven by this gate's output(s).
    """

    def __init__(self, name: str, gate: Gate, input_wires: List[Wire], output_wires: List[Wire]) -> None:
        self.name: str = name
        self.gate: Gate = gate
        self.input_wires: List[Wire] = input_wires
        self.output_wires: List[Wire] = output_wires

    def evaluate(self) -> None:
        """
        Push current input wire values into the gate, evaluate, and write
        the result to the output wire(s).
        """
        self.gate.inputs = [w.value for w in self.input_wires]
        result = self.gate.evaluate()
        if isinstance(result, tuple):
            for i, val in enumerate(result):
                self.output_wires[i].value = val
        else:
            self.output_wires[0].value = result

    def __repr__(self) -> str:
        ins = [w.name for w in self.input_wires]
        outs = [w.name for w in self.output_wires]
        return (
            f"GateNode({self.name!r}, type={self.gate.__class__.__name__}, "
            f"inputs={ins}, outputs={outs})"
        )


class CombinationalCycleError(Exception):
    """
    Raised when a combinational feedback cycle is detected during
    topological sort. Combinational cycles are illegal — they represent
    circuits with no stable logic state and cannot be statically evaluated.
    """


class Circuit:
    """
    A directed acyclic graph of logic gates connected by named wires.

    Usage example::

        c = Circuit()
        c.add_input("A")
        c.add_input("B")
        c.add_gate("G1", "AND", ["A", "B"], "Y")
        c.add_output("Y")
        result = c.evaluate({"A": Signal.HIGH, "B": Signal.LOW})
        # result == {"Y": Signal.LOW}
    """

    def __init__(self) -> None:
        self._wires: Dict[str, Wire] = {}
        self._gates: Dict[str, GateNode] = {}
        self._input_names: List[str] = []
        self._output_names: List[str] = []
        self._topo_order: Optional[List[GateNode]] = None  # cached sort result

    # ------------------------------------------------------------------
    # Circuit construction API
    # ------------------------------------------------------------------

    def _get_or_create_wire(self, name: str) -> Wire:
        """Return existing wire or create a new one with UNKNOWN value."""
        if name not in self._wires:
            self._wires[name] = Wire(name)
        return self._wires[name]

    def add_input(self, name: str) -> None:
        """
        Declare a primary input wire.

        Args:
            name: Wire identifier. Must be unique.

        Raises:
            ValueError: If a wire with this name already exists as a gate output.
        """
        wire = self._get_or_create_wire(name)
        if wire.driven_by is not None:
            raise ValueError(
                f"Cannot declare '{name}' as a primary input: it is already "
                f"driven by gate '{wire.driven_by.name}'."
            )
        wire.is_primary_input = True
        if name not in self._input_names:
            self._input_names.append(name)
        self._topo_order = None  # invalidate cache

    def add_output(self, name: str) -> None:
        """
        Mark an existing wire as a primary output.

        Args:
            name: Wire identifier. The wire must already exist (driven by a
                  gate or declared as an input).

        Raises:
            ValueError: If the wire name has not been declared.
        """
        if name not in self._wires:
            self._wires[name] = Wire(name)
        self._wires[name].is_primary_output = True
        if name not in self._output_names:
            self._output_names.append(name)

    def add_gate(
        self,
        name: str,
        gate_type: str,
        input_names: List[str],
        output_name: str,
        explicit_output_names: Optional[List[str]] = None,
    ) -> None:
        """
        Add a gate to the circuit.

        Args:
            name:         Unique name for this gate node (e.g. "G1", "XOR1").
            gate_type:    Gate type string, must be a key in GATE_REGISTRY.
            input_names:  Ordered list of wire names feeding this gate.
            output_name:  Base name of the wire this gate drives. For multi-output
                          gates, this will create wires like `output_name_0`, `output_name_1`
                          unless explicit_output_names are provided.
            explicit_output_names: Optional list of explicit wire names for the outputs.

        Raises:
            ValueError: If gate_type is unknown, name is duplicate, or output_name
                        is already driven by another gate.
        """
        if gate_type not in GATE_REGISTRY:
            raise ValueError(
                f"Unknown gate type '{gate_type}'. "
                f"Valid types: {sorted(GATE_REGISTRY.keys())}"
            )
        if name in self._gates:
            raise ValueError(f"Gate with name '{name}' already exists.")

        gate_cls = GATE_REGISTRY[gate_type]
        gate_obj = gate_cls(name=name)

        input_wires = [self._get_or_create_wire(n) for n in input_names]
        
        # Determine number of outputs for this gate type
        if gate_type == "DEC2X4":
            num_outputs = 4
        elif gate_type == "DEC3X8":
            num_outputs = 8
        else:
            num_outputs = 1
            
        if explicit_output_names is not None:
            if len(explicit_output_names) != num_outputs:
                raise ValueError(
                    f"Gate {gate_type} requires {num_outputs} outputs, but {len(explicit_output_names)} were provided."
                )
            out_names_to_use = explicit_output_names
        else:
            out_names_to_use = []
            for i in range(num_outputs):
                out_names_to_use.append(f"{output_name}_{i}" if num_outputs > 1 else output_name)
            
        output_wires = []
        for w_name in out_names_to_use:
            wire = self._get_or_create_wire(w_name)
            if wire.driven_by is not None:
                raise ValueError(
                    f"Wire '{w_name}' is already driven by gate "
                    f"'{wire.driven_by.name}'. Multiple drivers are illegal."
                )
            output_wires.append(wire)

        node = GateNode(name, gate_obj, input_wires, output_wires)
        for w in output_wires:
            w.driven_by = node
        self._gates[name] = node
        self._topo_order = None  # invalidate cache

    # ------------------------------------------------------------------
    # Topological sort (Kahn's algorithm)
    # ------------------------------------------------------------------

    def topological_sort(self) -> List[GateNode]:
        """
        Compute a valid gate evaluation order using Kahn's algorithm.

        Kahn's algorithm maintains in-degree counts for each gate and processes
        gates whose in-degree drops to zero (all inputs resolved). This naturally
        detects cycles: if we cannot empty the queue while gates remain, a cycle exists.

        Returns:
            Ordered list of GateNode instances; evaluating in this order guarantees
            each gate's inputs are ready before it runs.

        Raises:
            CombinationalCycleError: If any combinational feedback cycle is detected.
        """
        if self._topo_order is not None:
            return self._topo_order

        # Build a map: wire_name → set of gate names that read from this wire
        wire_to_consumers: Dict[str, Set[str]] = defaultdict(set)
        for gname, gnode in self._gates.items():
            for w in gnode.input_wires:
                wire_to_consumers[w.name].add(gname)

        # in_degree[gate_name] = number of gate-driven input wires not yet resolved
        in_degree: Dict[str, int] = {}
        for gname, gnode in self._gates.items():
            count = 0
            for w in gnode.input_wires:
                # A wire contributes to in-degree only if it is driven by a gate
                # (primary inputs are always "ready")
                if w.driven_by is not None:
                    count += 1
            in_degree[gname] = count

        # Seed the queue with gates whose inputs are all primary inputs
        queue: deque[str] = deque(
            gname for gname, deg in in_degree.items() if deg == 0
        )
        sorted_nodes: List[GateNode] = []

        while queue:
            gname = queue.popleft()
            node = self._gates[gname]
            sorted_nodes.append(node)

            # "Resolve" this gate's output wire(s): decrement in-degree for consumers
            for out_wire in node.output_wires:
                for consumer_name in wire_to_consumers.get(out_wire.name, set()):
                    in_degree[consumer_name] -= 1
                    if in_degree[consumer_name] == 0:
                        queue.append(consumer_name)

        if len(sorted_nodes) != len(self._gates):
            # Some gates were never dequeued — they are part of a cycle
            remaining = set(self._gates) - {n.name for n in sorted_nodes}
            raise CombinationalCycleError(
                f"Combinational cycle detected! The following gates form a cycle "
                f"(or depend on one): {sorted(remaining)}. "
                f"Add registers to break feedback loops."
            )

        self._topo_order = sorted_nodes
        return self._topo_order

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, input_values: Dict[str, Signal]) -> Dict[str, Signal]:
        """
        Evaluate the circuit for a given set of primary input values.

        Steps:
          1. Set all primary input wires to the provided values.
          2. Evaluate gates in topological order.
          3. Return the values of all primary output wires.

        Args:
            input_values: Mapping of primary input name → Signal value.
                          Any undeclared input wire defaults to UNKNOWN.

        Returns:
            Mapping of primary output name → Signal value.

        Raises:
            ValueError:              If an unknown input name is provided.
            CombinationalCycleError: If the circuit contains a feedback loop.
        """
        for name in input_values:
            if name not in self._wires or not self._wires[name].is_primary_input:
                raise ValueError(
                    f"'{name}' is not a declared primary input of this circuit."
                )

        # Reset all non-input wires to UNKNOWN for a clean evaluation
        for wire in self._wires.values():
            if not wire.is_primary_input:
                wire.value = Signal.UNKNOWN

        # Apply provided input values
        for name, value in input_values.items():
            self._wires[name].value = value

        # Default any un-provided primary inputs to UNKNOWN
        for name in self._input_names:
            if name not in input_values:
                self._wires[name].value = Signal.UNKNOWN

        # Evaluate in topological order
        for node in self.topological_sort():
            node.evaluate()

        # Collect and return primary outputs
        return {
            name: self._wires[name].value
            for name in self._output_names
        }

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def input_names(self) -> List[str]:
        """Ordered list of primary input wire names."""
        return list(self._input_names)

    @property
    def output_names(self) -> List[str]:
        """Ordered list of primary output wire names."""
        return list(self._output_names)

    @property
    def wire_names(self) -> List[str]:
        """All wire names in the circuit."""
        return list(self._wires.keys())

    @property
    def gate_names(self) -> List[str]:
        """All gate names in the circuit."""
        return list(self._gates.keys())

    def get_wire_value(self, name: str) -> Signal:
        """Return the current value of a named wire (after evaluation)."""
        if name not in self._wires:
            raise ValueError(f"No wire named '{name}' in circuit.")
        return self._wires[name].value

    def __repr__(self) -> str:
        return (
            f"Circuit(inputs={self._input_names}, outputs={self._output_names}, "
            f"gates={list(self._gates.keys())})"
        )
