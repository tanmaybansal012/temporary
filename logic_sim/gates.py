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
from typing import List, Union, Tuple
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

    def evaluate(self) -> Union[Signal, Tuple[Signal, ...]]:
        """Compute and return the gate's output Signal(s)."""
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
# Advanced Primitives (MUX, DECODER)
# ---------------------------------------------------------------------------

def _and(*signals: Signal) -> Signal:
    g = ANDGate()
    g.inputs = list(signals)
    return g.evaluate()

def _or(*signals: Signal) -> Signal:
    g = ORGate()
    g.inputs = list(signals)
    return g.evaluate()

def _not(s: Signal) -> Signal:
    g = NOTGate()
    g.inputs = [s]
    return g.evaluate()


class MUX2Gate(Gate):
    """
    2-to-1 Multiplexer composed from primitives.
    Inputs: [A, B, SEL]
    Output: (A AND NOT SEL) OR (B AND SEL)
    """

    def evaluate(self) -> Signal:
        if len(self.inputs) != 3:
            raise ValueError(f"MUX2Gate expects exactly 3 inputs [A, B, SEL], got {len(self.inputs)}.")
        a, b, sel = self.inputs
        
        not_sel = _not(sel)
        a_and_not_sel = _and(a, not_sel)
        b_and_sel = _and(b, sel)
        return _or(a_and_not_sel, b_and_sel)


class MUX4Gate(Gate):
    """
    4-to-1 Multiplexer composed from primitives.
    Inputs: [D0, D1, D2, D3, S0, S1]
    """

    def evaluate(self) -> Signal:
        if len(self.inputs) != 6:
            raise ValueError(f"MUX4Gate expects exactly 6 inputs [D0..D3, S0, S1], got {len(self.inputs)}.")
        d0, d1, d2, d3, s0, s1 = self.inputs
        
        not_s0 = _not(s0)
        not_s1 = _not(s1)
        
        y0 = _and(d0, not_s1, not_s0)
        y1 = _and(d1, not_s1, s0)
        y2 = _and(d2, s1, not_s0)
        y3 = _and(d3, s1, s0)
        
        return _or(y0, y1, y2, y3)


class DEC2X4Gate(Gate):
    """
    2-to-4 Decoder composed from primitives.
    Inputs: [A0, A1, EN]
    Outputs: Tuple of 4 Signals (Y0, Y1, Y2, Y3)
    """

    def evaluate(self) -> Tuple[Signal, Signal, Signal, Signal]:
        if len(self.inputs) != 3:
            raise ValueError(f"DEC2X4Gate expects exactly 3 inputs [A0, A1, EN], got {len(self.inputs)}.")
        a0, a1, en = self.inputs
        
        not_a0 = _not(a0)
        not_a1 = _not(a1)
        
        y0 = _and(en, not_a1, not_a0)
        y1 = _and(en, not_a1, a0)
        y2 = _and(en, a1, not_a0)
        y3 = _and(en, a1, a0)
        
        return (y0, y1, y2, y3)


class DEC3X8Gate(Gate):
    """
    3-to-8 Decoder composed from primitives.
    Inputs: [A0, A1, A2, EN]
    Outputs: Tuple of 8 Signals (Y0..Y7)
    """

    def evaluate(self) -> Tuple[Signal, Signal, Signal, Signal, Signal, Signal, Signal, Signal]:
        if len(self.inputs) != 4:
            raise ValueError(f"DEC3X8Gate expects exactly 4 inputs [A0, A1, A2, EN], got {len(self.inputs)}.")
        a0, a1, a2, en = self.inputs
        
        not_a0 = _not(a0)
        not_a1 = _not(a1)
        not_a2 = _not(a2)
        
        y0 = _and(en, not_a2, not_a1, not_a0)
        y1 = _and(en, not_a2, not_a1, a0)
        y2 = _and(en, not_a2, a1, not_a0)
        y3 = _and(en, not_a2, a1, a0)
        y4 = _and(en, a2, not_a1, not_a0)
        y5 = _and(en, a2, not_a1, a0)
        y6 = _and(en, a2, a1, not_a0)
        y7 = _and(en, a2, a1, a0)
        
        return (y0, y1, y2, y3, y4, y5, y6, y7)


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
    "MUX2": MUX2Gate,
    "MUX4": MUX4Gate,
    "DEC2X4": DEC2X4Gate,
    "DEC3X8": DEC3X8Gate,
}
