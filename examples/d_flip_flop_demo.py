"""
d_flip_flop_demo.py — Demonstrates D flip-flop edge-triggered behavior.

Shows that Q only changes on rising clock edges, not when D changes
between clock edges. This is the fundamental property of edge-triggered
storage elements.

Run:
    python examples/d_flip_flop_demo.py
"""

import sys
from pathlib import Path

# Add project root to sys.path if running directly
repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from logic_sim.sequential import DFlipFlop
from logic_sim.signal import Signal
from logic_sim.waveform import plot_waveform

def main() -> None:
    ff = DFlipFlop(clock_edge="rising")

    # CLK: 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1
    # D  : 0 0 1 1 1 1 0 0 1 1 0 0 1 0 1 1
    clk_pattern = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
    d_pattern   = [0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0, 1, 1]

    clk_trace, d_trace, q_trace = [], [], []

    print("=== D Flip-Flop Demo (Rising Edge Triggered) ===\n")
    print(f"{'Step':^6} {'CLK':^5} {'D':^4} {'Q':^4}  Note")
    print("-" * 45)

    for i, (clk_val, d_val) in enumerate(zip(clk_pattern, d_pattern)):
        clk = Signal.from_int(clk_val)
        d   = Signal.from_int(d_val)
        q   = ff.clock_tick({"CLK": clk, "D": d})

        clk_trace.append(clk)
        d_trace.append(d)
        q_trace.append(q)

        # Detect rising edge
        note = ""
        if i > 0 and clk_pattern[i-1] == 0 and clk_val == 1:
            note = f"<- rising edge: Q latches D={d_val}"

        print(f"{i:^6} {str(clk):^5} {str(d):^4} {str(q):^4}  {note}")

    print("\nObserve: Q only changes on rising clock edges (0->1 transitions)")

    signals = {"CLK": clk_trace, "D": d_trace, "Q": q_trace}
    path = plot_waveform(signals, title="D Flip-Flop Timing Diagram",
                         output_path="d_flipflop_waveform.png")
    print(f"\nWaveform saved to: {path}")

if __name__ == "__main__":
    main()
