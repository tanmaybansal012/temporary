"""
sequential.py — Stateful sequential elements: latches and flip-flops.

Two-Phase Clock-Tick Pattern
============================
All edge-triggered elements (DFlipFlop, JKFlipFlop, TFlipFlop) implement a
two-phase update protocol via clock_tick():

  Phase 1 — Compute next state:
      Calculate what the next state *would be* based on current inputs and
      the current state. Store this in self._next_state. Do NOT update
      self.state yet.

  Phase 2 — Commit if clock edge matches:
      Only after all flip-flops in the system have computed their next states
      should any of them commit. In this simulator, clock_tick() handles both
      phases internally, but the key insight is that next_state is computed
      from the OLD self.state, not from a partially-updated one.

Why this matters:
  Consider a shift register: FF1.Q → FF2.D → FF3.D. If FF1 commits its new
  state before FF2 reads FF1.Q, FF2 sees the NEW value of FF1.Q instead of
  the old one — a race condition. The two-phase pattern ensures all FFs sample
  inputs while the old state is intact, then all commit simultaneously.

  In hardware, this is enforced by the setup/hold time of the flip-flop and
  the fact that state changes only propagate after the clock edge settles.
  In software simulation, we replicate this by separating "compute" from
  "commit" and processing all FFs in two distinct sweeps.

Level-Sensitive vs Edge-Triggered:
  - SRLatch and DLatch are level-sensitive: they respond to signal levels, not
    transitions. Their clock_tick() simply checks the enable/clock level.
  - DFlipFlop, JKFlipFlop, TFlipFlop are edge-triggered: they sample inputs
    only on the rising or falling edge of the clock.
"""

from __future__ import annotations
from typing import Dict, Literal

from logic_sim.signal import Signal


ClockEdge = Literal["rising", "falling"]


class SRLatch:
    """
    SR (Set-Reset) Latch — level-sensitive.

    Inputs:
        S (Set):   When HIGH and R is LOW, output Q is forced HIGH.
        R (Reset): When HIGH and S is LOW, output Q is forced LOW.
        En (Enable): When LOW, latch holds its current state.

    Invalid condition:
        S=1, R=1 is the forbidden state for an SR latch. The behavior is
        undefined in real hardware (both outputs would be HIGH in an NOR-latch,
        then race to an unpredictable state when inputs are released). We
        explicitly flag this as UNKNOWN rather than silently resolving it —
        this matches the behavior of formal HDL simulators.

    State table:
        S  R  | Q_next
        ------+-------
        0  0  | Q (hold)
        0  1  | 0 (reset)
        1  0  | 1 (set)
        1  1  | X (invalid/forbidden)
    """

    def __init__(self) -> None:
        self.state: Signal = Signal.UNKNOWN   # uninitialized before first tick

    def clock_tick(self, inputs: Dict[str, Signal]) -> Signal:
        """
        Evaluate the latch for one time step.

        Args:
            inputs: Dict with keys 'S', 'R', and optional 'En' (default HIGH).
                    If 'En' is LOW, the latch is transparent-disabled (holds state).

        Returns:
            Current Q output after this tick.
        """
        S = inputs.get("S", Signal.UNKNOWN)
        R = inputs.get("R", Signal.UNKNOWN)
        En = inputs.get("En", Signal.HIGH)

        if En == Signal.LOW:
            # Latch is disabled — hold current state
            return self.state
        if En == Signal.UNKNOWN:
            # Cannot determine if latch is enabled; output is unknown
            self.state = Signal.UNKNOWN
            return self.state

        # Latch is enabled; apply SR logic
        if S == Signal.HIGH and R == Signal.HIGH:
            # Forbidden state — explicitly mark as UNKNOWN, not silently resolved
            self.state = Signal.UNKNOWN
        elif S == Signal.HIGH and R == Signal.LOW:
            self.state = Signal.HIGH
        elif S == Signal.LOW and R == Signal.HIGH:
            self.state = Signal.LOW
        elif S == Signal.LOW and R == Signal.LOW:
            pass  # hold — state unchanged
        else:
            # Any UNKNOWN input with non-trivial enable
            self.state = Signal.UNKNOWN

        return self.state

    @property
    def Q(self) -> Signal:
        """Current Q output."""
        return self.state

    @property
    def Q_bar(self) -> Signal:
        """Complement output (NOT Q)."""
        return self.state.invert()

    def __repr__(self) -> str:
        return f"SRLatch(Q={self.state})"


class DLatch:
    """
    D (Data) Latch — level-sensitive, transparent when enable is HIGH.

    When En=1: Q follows D (transparent mode).
    When En=0: Q holds its last value (opaque/latched mode).

    State table:
        En  D  | Q_next
        -------+-------
        0   x  | Q (hold)
        1   0  | 0
        1   1  | 1
    """

    def __init__(self) -> None:
        self.state: Signal = Signal.UNKNOWN

    def clock_tick(self, inputs: Dict[str, Signal]) -> Signal:
        """
        Evaluate the D latch for one time step.

        Args:
            inputs: Dict with keys 'D' and 'En'.

        Returns:
            Current Q output after this tick.
        """
        D = inputs.get("D", Signal.UNKNOWN)
        En = inputs.get("En", Signal.UNKNOWN)

        if En == Signal.LOW:
            return self.state   # hold
        if En == Signal.HIGH:
            self.state = D      # transparent: Q = D
        else:
            # En is UNKNOWN — if D equals current state, it doesn't matter
            if D != self.state:
                self.state = Signal.UNKNOWN

        return self.state

    @property
    def Q(self) -> Signal:
        return self.state

    @property
    def Q_bar(self) -> Signal:
        return self.state.invert()

    def __repr__(self) -> str:
        return f"DLatch(Q={self.state})"


class DFlipFlop:
    """
    D (Data) Flip-Flop — edge-triggered.

    Samples D on the specified clock edge and transfers it to Q.
    Between clock edges, Q holds its last value regardless of D changes.

    Two-phase update: next_state is computed from D at the clock edge,
    then committed. The _prev_clk attribute tracks the previous clock
    value to detect edge transitions.

    State table (at the triggering clock edge):
        D  | Q_next
        ---+-------
        0  | 0
        1  | 1
        X  | X
    """

    def __init__(self, clock_edge: ClockEdge = "rising") -> None:
        self.state: Signal = Signal.UNKNOWN
        self.clock_edge: ClockEdge = clock_edge
        self._prev_clk: Signal = Signal.UNKNOWN  # tracks previous clock value

    def _is_triggering_edge(self, clk: Signal) -> bool:
        """
        Return True if the CLK transition from _prev_clk to clk matches
        the configured clock_edge.
        """
        if self.clock_edge == "rising":
            return self._prev_clk == Signal.LOW and clk == Signal.HIGH
        else:  # "falling"
            return self._prev_clk == Signal.HIGH and clk == Signal.LOW

    def clock_tick(self, inputs: Dict[str, Signal]) -> Signal:
        """
        Evaluate one clock cycle.

        Two-phase update pattern (see module docstring):
          Phase 1: Compute _next_state from D sampled at the CURRENT inputs.
                   This uses self.state (the OLD state), not a partially-updated one.
          Phase 2: Commit _next_state to self.state only if a triggering edge occurred.

        Args:
            inputs: Dict with keys 'D' and 'CLK'.

        Returns:
            Current Q output (committed state after this tick).
        """
        D = inputs.get("D", Signal.UNKNOWN)
        clk = inputs.get("CLK", Signal.UNKNOWN)

        # Phase 1: compute next state (but don't commit yet)
        _next_state = D   # D flip-flop: next state = D at the triggering edge

        # Phase 2: commit only on triggering edge
        if self._is_triggering_edge(clk):
            self.state = _next_state

        self._prev_clk = clk
        return self.state

    @property
    def Q(self) -> Signal:
        return self.state

    @property
    def Q_bar(self) -> Signal:
        return self.state.invert()

    def __repr__(self) -> str:
        return f"DFlipFlop(clock_edge={self.clock_edge!r}, Q={self.state})"


class JKFlipFlop:
    """
    JK Flip-Flop — edge-triggered.

    The JK flip-flop is an improvement over SR: the J=1, K=1 condition is no
    longer forbidden — it toggles the output. This makes JK the most general
    single-bit storage element.

    State table (at the triggering clock edge):
        J  K  | Q_next
        ------+-------
        0  0  | Q (hold)
        0  1  | 0 (reset)
        1  0  | 1 (set)
        1  1  | NOT Q (toggle)
        X  x  | X (unknown — any unknown control input → unknown output)
    """

    def __init__(self, clock_edge: ClockEdge = "rising") -> None:
        self.state: Signal = Signal.UNKNOWN
        self.clock_edge: ClockEdge = clock_edge
        self._prev_clk: Signal = Signal.UNKNOWN

    def _is_triggering_edge(self, clk: Signal) -> bool:
        if self.clock_edge == "rising":
            return self._prev_clk == Signal.LOW and clk == Signal.HIGH
        else:
            return self._prev_clk == Signal.HIGH and clk == Signal.LOW

    def _next_state_from_jk(self, J: Signal, K: Signal) -> Signal:
        """
        Compute the next state given J, K, and current state.

        This is Phase 1 of the two-phase update — it reads self.state (old)
        and returns the prospective next state without modifying self.state.
        """
        if J == Signal.UNKNOWN or K == Signal.UNKNOWN:
            return Signal.UNKNOWN
        if J == Signal.LOW and K == Signal.LOW:
            return self.state          # hold
        if J == Signal.LOW and K == Signal.HIGH:
            return Signal.LOW          # reset
        if J == Signal.HIGH and K == Signal.LOW:
            return Signal.HIGH         # set
        # J=1, K=1: toggle
        return self.state.invert()

    def clock_tick(self, inputs: Dict[str, Signal]) -> Signal:
        """
        Evaluate one clock cycle.

        Args:
            inputs: Dict with keys 'J', 'K', and 'CLK'.

        Returns:
            Current Q output (committed state after this tick).
        """
        J = inputs.get("J", Signal.UNKNOWN)
        K = inputs.get("K", Signal.UNKNOWN)
        clk = inputs.get("CLK", Signal.UNKNOWN)

        # Phase 1: compute next state using the CURRENT (old) self.state
        _next_state = self._next_state_from_jk(J, K)

        # Phase 2: commit only on triggering edge
        if self._is_triggering_edge(clk):
            self.state = _next_state

        self._prev_clk = clk
        return self.state

    @property
    def Q(self) -> Signal:
        return self.state

    @property
    def Q_bar(self) -> Signal:
        return self.state.invert()

    def __repr__(self) -> str:
        return f"JKFlipFlop(clock_edge={self.clock_edge!r}, Q={self.state})"


class TFlipFlop:
    """
    T (Toggle) Flip-Flop — edge-triggered.

    A simplified JK with J and K tied together. When T=1, the output toggles
    on every triggering clock edge. When T=0, the output holds.

    Commonly used to build binary counters (chain of T flip-flops).

    State table (at the triggering clock edge):
        T  | Q_next
        ---+-------
        0  | Q (hold)
        1  | NOT Q (toggle)
        X  | X (unknown)
    """

    def __init__(self, clock_edge: ClockEdge = "rising") -> None:
        self.state: Signal = Signal.UNKNOWN
        self.clock_edge: ClockEdge = clock_edge
        self._prev_clk: Signal = Signal.UNKNOWN

    def _is_triggering_edge(self, clk: Signal) -> bool:
        if self.clock_edge == "rising":
            return self._prev_clk == Signal.LOW and clk == Signal.HIGH
        else:
            return self._prev_clk == Signal.HIGH and clk == Signal.LOW

    def clock_tick(self, inputs: Dict[str, Signal]) -> Signal:
        """
        Evaluate one clock cycle.

        Args:
            inputs: Dict with keys 'T' and 'CLK'.

        Returns:
            Current Q output (committed state after this tick).
        """
        T = inputs.get("T", Signal.UNKNOWN)
        clk = inputs.get("CLK", Signal.UNKNOWN)

        # Phase 1: compute next state from CURRENT (old) self.state
        if T == Signal.UNKNOWN:
            _next_state = Signal.UNKNOWN
        elif T == Signal.LOW:
            _next_state = self.state           # hold
        else:  # T == HIGH
            _next_state = self.state.invert()  # toggle

        # Phase 2: commit only on triggering edge
        if self._is_triggering_edge(clk):
            self.state = _next_state

        self._prev_clk = clk
        return self.state

    @property
    def Q(self) -> Signal:
        return self.state

    @property
    def Q_bar(self) -> Signal:
        return self.state.invert()

    def __repr__(self) -> str:
        return f"TFlipFlop(clock_edge={self.clock_edge!r}, Q={self.state})"


SEQUENTIAL_REGISTRY = {
    "DFF": DFlipFlop,
    "JKFF": JKFlipFlop,
    "TFF": TFlipFlop,
    "SRLATCH": SRLatch,
    "DLATCH": DLatch,
}
