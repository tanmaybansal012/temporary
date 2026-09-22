"""
simulation.py — Cycle-by-cycle sequential simulation.
"""

from typing import Any, Dict, List, Union
from logic_sim.circuit import Circuit
from logic_sim.signal import Signal

def simulate(circuit: Circuit, steps: List[Dict[str, Union[int, Signal]]]) -> List[Dict[str, Signal]]:
    """
    Run a cycle-by-cycle simulation of the circuit over a series of time steps.
    
    Args:
        circuit: The Circuit to simulate.
        steps: A list of dictionaries. Each dictionary provides the primary input values
               for that time step. If an input is omitted, it defaults to its previous 
               value, or Signal.UNKNOWN if no previous value exists.

    Returns:
        A list of dictionaries containing the state of every wire in the circuit
        at each time step.
    """
    history: List[Dict[str, Signal]] = []
    
    # Reset all sequential elements and wires to UNKNOWN at start
    for node in circuit.sequential_nodes:
        node.element.state = Signal.UNKNOWN
        if hasattr(node.element, "_prev_clk"):
            node.element._prev_clk = Signal.UNKNOWN
    
    for wire in circuit._wires.values():
        wire.value = Signal.UNKNOWN

    current_inputs: Dict[str, Signal] = {
        name: Signal.UNKNOWN for name in circuit.input_names
    }

    for step_idx, step_inputs in enumerate(steps):
        # Update inputs for this step
        for name, val in step_inputs.items():
            if name in current_inputs:
                if isinstance(val, int):
                    current_inputs[name] = Signal.from_int(val)
                else:
                    current_inputs[name] = val
                    
        # Apply current inputs to the circuit wires
        for name, val in current_inputs.items():
            circuit._wires[name].value = val

        # First, evaluate combinational logic to propagate primary inputs and 
        # the current outputs of sequential elements to the sequential inputs.
        # This handles the propagation of the state to the inputs of the next state logic.
        circuit.evaluate(current_inputs)

        # Record wire values for the history AFTER combinational propagation
        # but BEFORE sequential elements commit their next state.
        # Wait, the history step usually represents the stable state.
        # So we evaluate combinational logic, THEN we clock the sequential elements,
        # THEN we might need to re-evaluate combinational logic if the sequential 
        # outputs changed, BUT sequential outputs only change ON the clock edge, 
        # which means their new output values belong to the NEXT time step if we 
        # think of a step as "time between edges". 
        # However, a more standard approach for discrete time simulation:
        # 1. Apply inputs
        # 2. Evaluate combinational logic
        # 3. Capture all wire values (this is the state of the circuit at this step)
        # 4. Tick sequential elements to compute next state
        # 5. Commit next state to sequential element outputs
        
        # Capture current state of all wires
        step_state = {name: wire.value for name, wire in circuit._wires.items()}
        history.append(step_state)
        
        # Now, tick sequential elements using the inputs that arrived at their pins
        next_states = {}
        for node in circuit.sequential_nodes:
            elem_inputs = {}
            for pin_name, wire in zip(node.input_names_mapped, node.input_wires):
                elem_inputs[pin_name] = wire.value
            
            # clock_tick computes phase 1 and phase 2 internally
            q_next = node.element.clock_tick(elem_inputs)
            next_states[node.name] = q_next

        # Commit next states to the output wires of sequential elements
        for node in circuit.sequential_nodes:
            new_state = next_states[node.name]
            if len(node.output_wires) > 0:
                node.output_wires[0].value = new_state
            if len(node.output_wires) > 1:
                node.output_wires[1].value = new_state.invert()

    return history
