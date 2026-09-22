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
from typing import Any, Dict, List, Optional, Set, Tuple

from logic_sim.gates import Gate, GATE_REGISTRY
from logic_sim.sequential import SEQUENTIAL_REGISTRY
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


class SequentialNode:
    """
    Wraps a sequential element instance (flip-flop/latch) with connectivity.
    
    Attributes:
        name: Unique identifier.
        element: The underlying sequential instance (e.g. DFlipFlop).
        input_wires: Ordered list of Wire objects feeding this element.
        output_wires: List of Wire objects driven by this element (e.g., Q, Q_bar).
        input_names_mapped: List of pin names corresponding to input_wires (e.g. ['D', 'CLK']).
    """
    def __init__(self, name: str, element: Any, input_wires: List[Wire], output_wires: List[Wire], input_names_mapped: List[str]) -> None:
        self.name: str = name
        self.element = element
        self.input_wires: List[Wire] = input_wires
        self.output_wires: List[Wire] = output_wires
        self.input_names_mapped: List[str] = input_names_mapped

    def __repr__(self) -> str:
        ins = [w.name for w in self.input_wires]
        outs = [w.name for w in self.output_wires]
        return (
            f"SequentialNode({self.name!r}, type={self.element.__class__.__name__}, "
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
        Add a gate or sequential element to the circuit.
        """
        is_sequential = gate_type in SEQUENTIAL_REGISTRY
        if not is_sequential and gate_type not in GATE_REGISTRY:
            valid_types = sorted(list(GATE_REGISTRY.keys()) + list(SEQUENTIAL_REGISTRY.keys()))
            raise ValueError(
                f"Unknown gate/component type '{gate_type}'. "
                f"Valid types: {valid_types}"
            )
        if name in self._gates:
            raise ValueError(f"Gate with name '{name}' already exists.")

        input_wires = [self._get_or_create_wire(n) for n in input_names]

        if is_sequential:
            comp_cls = SEQUENTIAL_REGISTRY[gate_type]
            comp_obj = comp_cls()
            
            # Default output is Q, and we can also have QN (Q_bar)
            num_outputs = 1
            if explicit_output_names and len(explicit_output_names) == 2:
                num_outputs = 2
            
            if explicit_output_names is not None:
                out_names_to_use = explicit_output_names
            else:
                out_names_to_use = [output_name]

            # Map inputs for sequential element based on type
            # For simplicity, we define the expected order of pins
            input_names_mapped = []
            if gate_type == "DFF":
                input_names_mapped = ["D", "CLK"]
            elif gate_type == "JKFF":
                input_names_mapped = ["J", "K", "CLK"]
            elif gate_type == "TFF":
                input_names_mapped = ["T", "CLK"]
            elif gate_type == "SRLATCH":
                input_names_mapped = ["S", "R", "En"]
            elif gate_type == "DLATCH":
                input_names_mapped = ["D", "En"]

            if len(input_names) != len(input_names_mapped):
                # Fallback if optional EN is missing for latches, though parser should enforce
                input_names_mapped = input_names_mapped[:len(input_names)]

        else:
            comp_cls = GATE_REGISTRY[gate_type]
            comp_obj = comp_cls(name=name)
            
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
            
            input_names_mapped = []

        output_wires = []
        for w_name in out_names_to_use:
            wire = self._get_or_create_wire(w_name)
            if wire.driven_by is not None:
                raise ValueError(
                    f"Wire '{w_name}' is already driven by gate "
                    f"'{wire.driven_by.name}'. Multiple drivers are illegal."
                )
            output_wires.append(wire)

        if is_sequential:
            node = SequentialNode(name, comp_obj, input_wires, output_wires, input_names_mapped)
        else:
            node = GateNode(name, comp_obj, input_wires, output_wires)

        for w in output_wires:
            w.driven_by = node
        self._gates[name] = node
        self._topo_order = None  # invalidate cache

    # ------------------------------------------------------------------
    # Topological sort (Kahn's algorithm)
    # ------------------------------------------------------------------

    def topological_sort(self) -> List[GateNode]:
        """
        Compute a valid gate evaluation order for combinational gates.
        Sequential nodes are ignored, as their outputs act as primary inputs for
        combinational logic, and their inputs act as primary outputs.
        """
        if self._topo_order is not None:
            return self._topo_order

        wire_to_consumers: Dict[str, Set[str]] = defaultdict(set)
        combinational_gates = {
            gname: gnode for gname, gnode in self._gates.items()
            if isinstance(gnode, GateNode)
        }

        for gname, gnode in combinational_gates.items():
            for w in gnode.input_wires:
                wire_to_consumers[w.name].add(gname)

        in_degree: Dict[str, int] = {}
        for gname, gnode in combinational_gates.items():
            drivers: Set[str] = set()
            for w in gnode.input_wires:
                # Treat wires driven by SequentialNodes as if they are primary inputs
                if w.driven_by is not None and isinstance(w.driven_by, GateNode):
                    drivers.add(w.driven_by.name)
            in_degree[gname] = len(drivers)

        queue: deque[str] = deque(
            gname for gname, deg in in_degree.items() if deg == 0
        )
        sorted_nodes: List[GateNode] = []

        while queue:
            gname = queue.popleft()
            node = combinational_gates[gname]
            sorted_nodes.append(node)

            for out_wire in node.output_wires:
                for consumer_name in wire_to_consumers.get(out_wire.name, set()):
                    in_degree[consumer_name] -= 1
                    if in_degree[consumer_name] == 0:
                        queue.append(consumer_name)

        if len(sorted_nodes) < len(combinational_gates):
            unresolved = [g for g, deg in in_degree.items() if deg > 0]
            raise CombinationalCycleError(
                f"Combinational cycle detected! The following gates are trapped in "
                f"a feedback loop: {unresolved}"
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

        # Reset all purely combinational non-input wires to UNKNOWN for a clean evaluation
        for wire in self._wires.values():
            if not wire.is_primary_input:
                if wire.driven_by is None or not isinstance(wire.driven_by, SequentialNode):
                    wire.value = Signal.UNKNOWN

        # Apply provided input values
        for name, value in input_values.items():
            self._wires[name].value = value

        # Default any un-provided primary inputs to UNKNOWN
        for name in self._input_names:
            if name not in input_values:
                self._wires[name].value = Signal.UNKNOWN

        # Evaluate in topological order (only visits GateNodes)
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
    def sequential_nodes(self) -> List[SequentialNode]:
        """All sequential nodes in the circuit."""
        return [node for node in self._gates.values() if isinstance(node, SequentialNode)]

    @property
    def has_sequential(self) -> bool:
        """Return True if the circuit contains any sequential elements."""
        return len(self.sequential_nodes) > 0

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

    def get_gate(self, name: str) -> GateNode:
        """Return the GateNode for a given gate name."""
        if name not in self._gates:
            raise ValueError(f"No gate named '{name}' in circuit.")
        return self._gates[name]

    def __repr__(self) -> str:
        return (
            f"Circuit(inputs={self._input_names}, outputs={self._output_names}, "
            f"gates={list(self._gates.keys())})"
        )
