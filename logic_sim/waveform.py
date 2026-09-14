"""
waveform.py — Timing diagram plotting via matplotlib.

Generates digital waveform diagrams where:
  - Each signal occupies its own horizontal track (row)
  - Transitions are drawn as step functions (no slew rate — ideal digital signals)
  - Time axis is shared across all signals
  - Signals are labeled on the left
  - The diagram is saved as a PNG and optionally displayed interactively

Signal values are mapped to numeric levels for plotting:
  HIGH    (1) → 1.0
  LOW     (0) → 0.0
  UNKNOWN (X) → 0.5  (mid-rail, shown with a distinct style)
"""

from __future__ import annotations
from typing import Dict, List, Optional

from logic_sim.signal import Signal


def _signal_to_float(s: Signal) -> float:
    """Convert a Signal to a float for matplotlib plotting."""
    if s == Signal.HIGH:
        return 1.0
    elif s == Signal.LOW:
        return 0.0
    else:
        return 0.5  # UNKNOWN → mid-rail


def plot_waveform(
    signals: Dict[str, List[Signal]],
    title: str = "Digital Timing Diagram",
    output_path: Optional[str] = None,
    show: bool = False,
    time_unit: str = "Cycle",
) -> str:
    """
    Plot a digital timing diagram for a dictionary of signal traces.

    Args:
        signals:     Ordered dict of signal_name → list of Signal values.
                     All lists must have the same length (number of time steps).
        title:       Plot title displayed at the top.
        output_path: File path for the PNG output. If None, defaults to
                     "waveform.png" in the current directory.
        show:        If True, display the plot interactively (blocks until closed).
        time_unit:   Label for the x-axis (e.g. "Cycle", "ns").

    Returns:
        The absolute path to the saved PNG file.

    Raises:
        ValueError: If signal lists have different lengths.
        ImportError: If matplotlib is not installed.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend (safe for all environments)
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError as e:
        raise ImportError(
            "matplotlib is required for waveform plotting. "
            "Install it with: pip install matplotlib"
        ) from e

    if not signals:
        raise ValueError("Cannot plot an empty signals dictionary.")

    # Validate uniform length
    lengths = {name: len(vals) for name, vals in signals.items()}
    if len(set(lengths.values())) > 1:
        raise ValueError(
            f"All signal traces must have equal length. Got: {lengths}"
        )
    n_steps = next(iter(lengths.values()))

    signal_names = list(signals.keys())
    n_signals = len(signal_names)

    # Layout: each signal gets 1 unit of vertical space; signals stacked top-to-bottom
    row_height = 1.0
    padding = 0.4
    fig_height = max(3.0, n_signals * row_height + padding * 2)
    fig_width = max(8.0, n_steps * 0.8 + 2.0)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.set_facecolor("#1a1a2e")
    fig.patch.set_facecolor("#0f0f23")

    # Color scheme
    HIGH_COLOR  = "#00d4aa"   # teal-green for logic HIGH
    LOW_COLOR   = "#00d4aa"   # same line color; level distinguishes
    UNKNOWN_COLOR = "#ff6b35" # orange for UNKNOWN
    LABEL_COLOR = "#e0e0e0"   # light gray for labels
    GRID_COLOR  = "#2a2a4a"   # subtle dark grid

    # Time axis: plot signals from top to bottom
    time_steps = list(range(n_steps + 1))  # one extra point for step-plot

    for i, name in enumerate(signal_names):
        # Vertical offset: top signal at the highest y
        y_base = (n_signals - 1 - i) * row_height

        vals = signals[name]
        y_vals = [_signal_to_float(s) for s in vals]

        # Build step-plot coordinates (duplicate each point for step transition)
        # matplotlib's drawstyle='steps-post' handles this automatically
        x = list(range(n_steps))
        y = y_vals

        # Detect UNKNOWN segments for special styling
        unknown_mask = [s == Signal.UNKNOWN for s in vals]

        # Plot the waveform line using step style
        # Scale y to row height: 0 → y_base + 0.1, 1 → y_base + 0.9
        y_scaled = [y_base + 0.1 + v * 0.8 for v in y]

        # Split into known and unknown segments for separate styling
        seg_x: List[float] = []
        seg_y: List[float] = []

        for j in range(n_steps):
            seg_x.append(j)
            seg_y.append(y_scaled[j])

        # Add one more point at the end to close the last step
        seg_x.append(n_steps)
        seg_y.append(y_scaled[-1])

        # Draw UNKNOWN regions as filled orange bands
        j = 0
        while j < n_steps:
            if unknown_mask[j]:
                # Find the end of this unknown run
                k = j
                while k < n_steps and unknown_mask[k]:
                    k += 1
                ax.axvspan(j, k, ymin=(y_base + 0.05) / (n_signals * row_height),
                           ymax=(y_base + 0.95) / (n_signals * row_height),
                           alpha=0.3, color=UNKNOWN_COLOR, linewidth=0)
                # Draw X markers
                for m in range(j, k):
                    ax.text(m + 0.5, y_base + 0.5, "X",
                            ha="center", va="center",
                            color=UNKNOWN_COLOR, fontsize=8, fontweight="bold")
                j = k
            else:
                j += 1

        # Draw the waveform
        ax.step(seg_x, seg_y, where="post", color=HIGH_COLOR,
                linewidth=1.8, solid_capstyle="round")

        # Draw signal label on the left
        ax.text(-0.3, y_base + 0.5, name,
                ha="right", va="center",
                color=LABEL_COLOR, fontsize=10, fontweight="bold",
                fontfamily="monospace")

        # Draw baseline and ceiling reference lines (very subtle)
        ax.axhline(y_base + 0.1, color=GRID_COLOR, linewidth=0.5, linestyle="--")
        ax.axhline(y_base + 0.9, color=GRID_COLOR, linewidth=0.5, linestyle="--")

    # Vertical grid lines at each time step
    for t in range(n_steps + 1):
        ax.axvline(t, color=GRID_COLOR, linewidth=0.5, linestyle=":")

    # Axis configuration
    ax.set_xlim(-0.1, n_steps + 0.1)
    ax.set_ylim(-0.1, n_signals * row_height + 0.1)
    ax.set_xticks(range(n_steps))
    ax.set_xticklabels([str(i) for i in range(n_steps)],
                       color=LABEL_COLOR, fontsize=9)
    ax.set_xlabel(time_unit, color=LABEL_COLOR, fontsize=10)
    ax.set_yticks([])
    ax.tick_params(colors=LABEL_COLOR)
    for spine in ax.spines.values():
        spine.set_edgecolor("#3a3a5a")

    ax.set_title(title, color="#ffffff", fontsize=13, fontweight="bold", pad=12)

    # Legend for UNKNOWN
    unknown_patch = mpatches.Patch(
        color=UNKNOWN_COLOR, alpha=0.4, label="X = UNKNOWN/Uninitialized"
    )
    ax.legend(handles=[unknown_patch], loc="upper right",
              facecolor="#1a1a2e", edgecolor="#3a3a5a",
              labelcolor=LABEL_COLOR, fontsize=8)

    plt.tight_layout()

    if output_path is None:
        output_path = "waveform.png"

    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())

    if show:
        matplotlib.use("TkAgg")  # switch to interactive for show()
        plt.show()

    plt.close(fig)
    return output_path
