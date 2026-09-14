"""
gates.py — Logic gate primitives for the digital logic simulator.

Each gate is a class with:
  - inputs: list of Signal values (set before evaluation)
  - evaluate() -> Signal: computes the gate's boolean function

UNKNOWN propagation rules implemented here follow the standard three-valued
(ternary) logic semantics used in formal verification and HDL simulators:

  AND: if any input is LOW → LOW (absorbing element; X doesn't matter)
       if all inputs are HIGH → HIGH
       otherwise (mix of HIGH and UNKNOWN) → UNKNOWN

  OR:  if any input is HIGH → HIGH (absorbing element; X doesn't matter)
       if all inputs are LOW → LOW
       otherwise (mix of LOW and UNKNOWN) → UNKNOWN

  NOT: UNKNOWN → UNKNOWN

  NAND/NOR/XOR/XNOR: derived from the above by composition.
"""

from __future__ import annotations
from typing import List
from logic_sim.signal import Signal


class Gate:
    """
    Abstract base class for all logic gates.

    Attributes:
        name:   Optional human-readable identifier (useful for debug output).
        inputs: List of Signal values feeding this gate. Caller must populate
                this list before calling evaluate().
    """

    def __init__(self, name: str = "") -> None:
        self.name: str = name
        self.inputs: List[Signal] = []

    def evaluate(self) -> Signal:
        """Compute and return the gate's output Signal."""
        raise NotImplementedError("Subclasses must implement evaluate().")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, inputs={self.inputs})"


# ---------------------------------------------------------------------------
# Primitive gates
# ---------------------------------------------------------------------------

class NOTGate(Gate):
    """
    Single-input inverter.

    Truth table:
        A  | NOT A
        ---|------
        0  |  1
        1  |  0
        X  |  X
    """

    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self.inputs: List[Signal] = [Signal.UNKNOWN]  # exactly one input

    def evaluate(self) -> Signal:
        if len(self.inputs) != 1:
            raise ValueError(
                f"NOTGate expects exactly 1 input, got {len(self.inputs)}."
            )
        return self.inputs[0].invert()


class ANDGate(Gate):
    """
    N-input AND gate (N ≥ 2).

    UNKNOWN propagation:
        AND(0, X) = 0   — zero dominates (absorbing element)
        AND(1, X) = X   — cannot determine output without knowing X
        AND(X, X) = X
    """

    def evaluate(self) -> Signal:
        if len(self.inputs) < 2:
            raise ValueError(
                f"ANDGate expects at least 2 inputs, got {len(self.inputs)}."
            )
        has_unknown = False
        for inp in self.inputs:
            if inp == Signal.LOW:
                return Signal.LOW          # 0 dominates regardless of unknowns
            if inp == Signal.UNKNOWN:
                has_unknown = True
        return Signal.UNKNOWN if has_unknown else Signal.HIGH


class ORGate(Gate):
    """
    N-input OR gate (N ≥ 2).

    UNKNOWN propagation:
        OR(1, X) = 1    — one dominates (absorbing element)
        OR(0, X) = X    — cannot determine output without knowing X
        OR(X, X) = X
    """

    def evaluate(self) -> Signal:
        if len(self.inputs) < 2:
            raise ValueError(
                f"ORGate expects at least 2 inputs, got {len(self.inputs)}."
            )
        has_unknown = False
        for inp in self.inputs:
            if inp == Signal.HIGH:
                return Signal.HIGH         # 1 dominates regardless of unknowns
            if inp == Signal.UNKNOWN:
                has_unknown = True
        return Signal.UNKNOWN if has_unknown else Signal.LOW


class NANDGate(Gate):
    """
    N-input NAND gate (N ≥ 2).

    Implemented as NOT(AND(inputs)), so UNKNOWN propagation is consistent
    with ANDGate rules followed by inversion.
    """

    def evaluate(self) -> Signal:
        if len(self.inputs) < 2:
            raise ValueError(
                f"NANDGate expects at least 2 inputs, got {len(self.inputs)}."
            )
        and_gate = ANDGate()
        and_gate.inputs = self.inputs
        return and_gate.evaluate().invert()


class NORGate(Gate):
    """
    N-input NOR gate (N ≥ 2).

    Implemented as NOT(OR(inputs)), so UNKNOWN propagation is consistent
    with ORGate rules followed by inversion.
    """

    def evaluate(self) -> Signal:
        if len(self.inputs) < 2:
            raise ValueError(
                f"NORGate expects at least 2 inputs, got {len(self.inputs)}."
            )
        or_gate = ORGate()
        or_gate.inputs = self.inputs
        return or_gate.evaluate().invert()


class XORGate(Gate):
    """
    N-input XOR gate (N ≥ 2).

    For N > 2 inputs: output is HIGH if an odd number of inputs are HIGH.

    UNKNOWN propagation:
        XOR(X, anything) = X  — if any input is unknown the parity is unknown.

    Note: Unlike AND/OR, there is no absorbing element for XOR, so any UNKNOWN
    input propagates to the output.
    """

    def evaluate(self) -> Signal:
        if len(self.inputs) < 2:
            raise ValueError(
                f"XORGate expects at least 2 inputs, got {len(self.inputs)}."
            )
        for inp in self.inputs:
            if inp == Signal.UNKNOWN:
                return Signal.UNKNOWN      # no absorbing element; X propagates
        # All inputs are known; count HIGH inputs
        high_count = sum(1 for inp in self.inputs if inp == Signal.HIGH)
        return Signal.HIGH if (high_count % 2 == 1) else Signal.LOW


class XNORGate(Gate):
    """
    N-input XNOR gate (N ≥ 2).

    Implemented as NOT(XOR(inputs)).

    UNKNOWN propagation is identical to XOR: any unknown input → UNKNOWN output.
    """

    def evaluate(self) -> Signal:
        if len(self.inputs) < 2:
            raise ValueError(
                f"XNORGate expects at least 2 inputs, got {len(self.inputs)}."
            )
        xor_gate = XORGate()
        xor_gate.inputs = self.inputs
        return xor_gate.evaluate().invert()


# ---------------------------------------------------------------------------
# Registry: map type-name strings to gate classes (used by parser + CLI)
# ---------------------------------------------------------------------------

GATE_REGISTRY: dict[str, type[Gate]] = {
    "NOT":  NOTGate,
    "AND":  ANDGate,
    "OR":   ORGate,
    "NAND": NANDGate,
    "NOR":  NORGate,
    "XOR":  XORGate,
    "XNOR": XNORGate,
}
