"""
sr_latch_demo.py — Demonstrates SR latch behavior including the forbidden state.

Run:
    python examples/sr_latch_demo.py
"""

from logic_sim.sequential import SRLatch
from logic_sim.signal import Signal
from logic_sim.waveform import plot_waveform

def main() -> None:
    latch = SRLatch()

    # Sequence: set, hold, reset, hold, forbidden (S=R=1), hold
    test_cases = [
        {"S": Signal.HIGH, "R": Signal.LOW,  "En": Signal.HIGH},  # Set
        {"S": Signal.LOW,  "R": Signal.LOW,  "En": Signal.HIGH},  # Hold
        {"S": Signal.LOW,  "R": Signal.HIGH, "En": Signal.HIGH},  # Reset
        {"S": Signal.LOW,  "R": Signal.LOW,  "En": Signal.HIGH},  # Hold
        {"S": Signal.HIGH, "R": Signal.HIGH, "En": Signal.HIGH},  # FORBIDDEN → X
        {"S": Signal.LOW,  "R": Signal.LOW,  "En": Signal.HIGH},  # Hold (still X)
        {"S": Signal.LOW,  "R": Signal.HIGH, "En": Signal.HIGH},  # Reset → 0
        {"S": Signal.LOW,  "R": Signal.LOW,  "En": Signal.HIGH},  # Hold
    ]

    s_trace, r_trace, en_trace, q_trace = [], [], [], []

    print("=== SR Latch Demo ===\n")
    print(f"{'Step':^6} {'S':^4} {'R':^4} {'En':^4} {'Q':^4}")
    print("-" * 30)

    for i, inp in enumerate(test_cases):
        q = latch.clock_tick(inp)
        s_trace.append(inp["S"])
        r_trace.append(inp["R"])
        en_trace.append(inp["En"])
        q_trace.append(q)
        print(f"{i:^6} {str(inp['S']):^4} {str(inp['R']):^4} {str(inp['En']):^4} {str(q):^4}")

    print("\nNote: Step 4 (S=R=1) is the forbidden state → Q = X (UNKNOWN)")

    # Plot waveform
    signals = {"S": s_trace, "R": r_trace, "En": en_trace, "Q": q_trace}
    path = plot_waveform(signals, title="SR Latch Timing Diagram",
                         output_path="sr_latch_waveform.png")
    print(f"\nWaveform saved to: {path}")

if __name__ == "__main__":
    main()
