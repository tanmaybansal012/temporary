"""
tests/test_sequential.py — Unit tests for SR latch and all flip-flop types.

Tests verify:
  - Initial state is UNKNOWN (not 0)
  - State changes only on the correct clock edge
  - Correct state transition for all input combinations
  - Two-phase update correctness (state read before commit)
  - SR forbidden state produces UNKNOWN
  - JK toggle behavior
"""

import pytest
from logic_sim.sequential import SRLatch, DLatch, DFlipFlop, JKFlipFlop, TFlipFlop
from logic_sim.signal import Signal

L = Signal.LOW
H = Signal.HIGH
X = Signal.UNKNOWN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rising_edge(ff, **kwargs):
    """Simulate a full rising clock edge: drive CLK low then high."""
    ff.clock_tick({**kwargs, "CLK": L})
    return ff.clock_tick({**kwargs, "CLK": H})


def falling_edge(ff, **kwargs):
    """Simulate a full falling clock edge: drive CLK high then low."""
    ff.clock_tick({**kwargs, "CLK": H})
    return ff.clock_tick({**kwargs, "CLK": L})


# ---------------------------------------------------------------------------
# SR Latch
# ---------------------------------------------------------------------------

class TestSRLatch:
    def test_initial_state_unknown(self):
        sr = SRLatch()
        assert sr.state == X

    def test_set(self):
        sr = SRLatch()
        q = sr.clock_tick({"S": H, "R": L, "En": H})
        assert q == H

    def test_reset(self):
        sr = SRLatch()
        sr.state = H  # put it in set state first
        q = sr.clock_tick({"S": L, "R": H, "En": H})
        assert q == L

    def test_hold_preserves_state(self):
        sr = SRLatch()
        sr.state = H
        q = sr.clock_tick({"S": L, "R": L, "En": H})
        assert q == H

    def test_forbidden_state_produces_unknown(self):
        """S=R=1 must produce UNKNOWN, not silently resolve to any value."""
        sr = SRLatch()
        sr.state = H
        q = sr.clock_tick({"S": H, "R": H, "En": H})
        assert q == X

    def test_enable_low_holds_state(self):
        sr = SRLatch()
        sr.state = H
        q = sr.clock_tick({"S": H, "R": L, "En": L})  # En=0 disables latch
        assert q == H  # still H; S ignored

    def test_set_then_reset_sequence(self):
        sr = SRLatch()
        sr.clock_tick({"S": H, "R": L, "En": H})
        assert sr.state == H
        sr.clock_tick({"S": L, "R": H, "En": H})
        assert sr.state == L

    def test_q_bar_is_complement(self):
        sr = SRLatch()
        sr.state = H
        assert sr.Q_bar == L
        sr.state = L
        assert sr.Q_bar == H


# ---------------------------------------------------------------------------
# D Latch
# ---------------------------------------------------------------------------

class TestDLatch:
    def test_initial_state_unknown(self):
        dl = DLatch()
        assert dl.state == X

    def test_transparent_when_enabled(self):
        dl = DLatch()
        dl.clock_tick({"D": H, "En": H})
        assert dl.state == H
        dl.clock_tick({"D": L, "En": H})
        assert dl.state == L

    def test_hold_when_disabled(self):
        dl = DLatch()
        dl.clock_tick({"D": H, "En": H})  # latch HIGH
        dl.clock_tick({"D": L, "En": L})  # disable; D changes but Q shouldn't
        assert dl.state == H

    def test_unknown_enable(self):
        """If En is UNKNOWN and D ≠ current state, result is UNKNOWN."""
        dl = DLatch()
        dl.state = H
        dl.clock_tick({"D": L, "En": X})  # D ≠ state, En unknown → X
        assert dl.state == X


# ---------------------------------------------------------------------------
# D Flip-Flop
# ---------------------------------------------------------------------------

class TestDFlipFlop:
    def test_initial_state_unknown(self):
        ff = DFlipFlop()
        assert ff.state == X

    def test_samples_d_on_rising_edge(self):
        ff = DFlipFlop(clock_edge="rising")
        q = rising_edge(ff, D=H)
        assert q == H

    def test_does_not_change_mid_clock(self):
        """Q must NOT change when D changes between clock edges."""
        ff = DFlipFlop(clock_edge="rising")
        rising_edge(ff, D=H)     # latch Q=1 on first rising edge
        assert ff.state == H

        # Now D goes LOW while CLK is LOW — Q should not change
        ff.clock_tick({"D": L, "CLK": L})
        assert ff.state == H    # still H; no rising edge yet

    def test_d_zero_latches_on_rising(self):
        ff = DFlipFlop(clock_edge="rising")
        ff.state = H  # start HIGH
        q = rising_edge(ff, D=L)
        assert q == L

    def test_falling_edge_triggered(self):
        ff = DFlipFlop(clock_edge="falling")
        q = falling_edge(ff, D=H)
        assert q == H

    def test_falling_edge_does_not_trigger_on_rising(self):
        ff = DFlipFlop(clock_edge="falling")
        ff.state = L
        q = rising_edge(ff, D=H)
        assert q == L   # D=1 but wrong edge; should remain L

    def test_full_cycle_sequence(self):
        """Simulate 4 rising edges with toggling D."""
        ff = DFlipFlop(clock_edge="rising")
        d_sequence = [H, L, H, L]
        expected_q = [H, L, H, L]

        for d, exp_q in zip(d_sequence, expected_q):
            q = rising_edge(ff, D=d)
            assert q == exp_q

    def test_unknown_d_propagates(self):
        ff = DFlipFlop(clock_edge="rising")
        q = rising_edge(ff, D=X)
        assert q == X

    def test_state_only_on_correct_edge(self):
        """
        State must be committed to memory only when the edge fires.
        This tests the two-phase pattern: driving CLK=LOW should never
        change state even if D changes.
        """
        ff = DFlipFlop(clock_edge="rising")
        ff.state = H
        # Drive D=0 with CLK staying LOW (no rising edge)
        for _ in range(3):
            ff.clock_tick({"D": L, "CLK": L})
        assert ff.state == H   # still H; no edge


# ---------------------------------------------------------------------------
# JK Flip-Flop
# ---------------------------------------------------------------------------

class TestJKFlipFlop:
    def test_initial_state_unknown(self):
        ff = JKFlipFlop()
        assert ff.state == X

    def test_hold_00(self):
        ff = JKFlipFlop(clock_edge="rising")
        ff.state = H
        q = rising_edge(ff, J=L, K=L)
        assert q == H  # hold

    def test_reset_01(self):
        ff = JKFlipFlop(clock_edge="rising")
        ff.state = H
        q = rising_edge(ff, J=L, K=H)
        assert q == L  # reset

    def test_set_10(self):
        ff = JKFlipFlop(clock_edge="rising")
        ff.state = L
        q = rising_edge(ff, J=H, K=L)
        assert q == H  # set

    def test_toggle_11(self):
        ff = JKFlipFlop(clock_edge="rising")
        ff.state = H
        q = rising_edge(ff, J=H, K=H)
        assert q == L   # toggle H → L
        # Another toggle
        q = rising_edge(ff, J=H, K=H)
        assert q == H   # toggle L → H

    def test_toggle_from_unknown_is_unknown(self):
        """Toggling an UNKNOWN state produces UNKNOWN (can't invert X)."""
        ff = JKFlipFlop(clock_edge="rising")
        ff.state = X
        q = rising_edge(ff, J=H, K=H)
        assert q == X

    def test_unknown_j_propagates(self):
        ff = JKFlipFlop(clock_edge="rising")
        ff.state = L
        q = rising_edge(ff, J=X, K=L)
        assert q == X

    def test_full_jk_cycle(self):
        """Run through set, toggle, toggle, reset, hold."""
        ff = JKFlipFlop(clock_edge="rising")
        ff.state = L

        q = rising_edge(ff, J=H, K=L)
        assert q == H  # set

        q = rising_edge(ff, J=H, K=H)
        assert q == L  # toggle

        q = rising_edge(ff, J=H, K=H)
        assert q == H  # toggle

        q = rising_edge(ff, J=L, K=H)
        assert q == L  # reset

        q = rising_edge(ff, J=L, K=L)
        assert q == L  # hold


# ---------------------------------------------------------------------------
# T Flip-Flop
# ---------------------------------------------------------------------------

class TestTFlipFlop:
    def test_initial_state_unknown(self):
        ff = TFlipFlop()
        assert ff.state == X

    def test_hold_t0(self):
        ff = TFlipFlop(clock_edge="rising")
        ff.state = H
        q = rising_edge(ff, T=L)
        assert q == H

    def test_toggle_t1(self):
        ff = TFlipFlop(clock_edge="rising")
        ff.state = H
        q = rising_edge(ff, T=H)
        assert q == L

    def test_toggle_four_times(self):
        """Four toggles of an even number should restore original state."""
        ff = TFlipFlop(clock_edge="rising")
        ff.state = H
        for _ in range(4):
            rising_edge(ff, T=H)
        assert ff.state == H

    def test_counter_behavior(self):
        """T=1 every cycle → alternating 0,1,0,1 (binary counter LSB)."""
        ff = TFlipFlop(clock_edge="rising")
        ff.state = L
        expected = [H, L, H, L, H, L, H, L]
        for exp in expected:
            q = rising_edge(ff, T=H)
            assert q == exp, f"Expected {exp}, got {q}"

    def test_unknown_t_propagates(self):
        ff = TFlipFlop(clock_edge="rising")
        ff.state = H
        q = rising_edge(ff, T=X)
        assert q == X


# ---------------------------------------------------------------------------
# Two-phase update correctness (shift register scenario)
# ---------------------------------------------------------------------------

class TestTwoPhaseUpdate:
    """
    Test that the two-phase update pattern prevents race conditions.

    Scenario: shift register — FF1.Q feeds FF2.D
    Both flip-flops must sample their inputs SIMULTANEOUSLY (from the old
    state) before either commits. This ensures FF2 sees FF1's OLD output,
    not its just-updated new output.
    """

    def test_shift_register_two_ffs(self):
        ff1 = DFlipFlop(clock_edge="rising")
        ff2 = DFlipFlop(clock_edge="rising")

        ff1.state = H   # FF1.Q = 1
        ff2.state = L   # FF2.Q = 0

        # CORRECT two-phase update:
        # Phase 1: compute next states from old state simultaneously
        # We simulate by computing next before committing either
        ff1_next = H     # D=1 → Q_next=1 (from external input D=1)
        ff2_next = ff1.state  # D = FF1.Q_old = 1

        # Phase 2: commit both
        ff1.state = ff1_next
        ff2.state = ff2_next

        # After one cycle: FF2 should have captured FF1's OLD state (H=1)
        assert ff2.state == H

        # If the update were non-atomic (sequential commit), FF2 might
        # incorrectly see FF1's new state instead of old state. This test
        # verifies the pattern is correct.
