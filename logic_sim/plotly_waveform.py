"""
plotly_waveform.py — Interactive timing diagram plotting via Plotly.

Generates digital waveform diagrams for use in Streamlit:
  - Each signal occupies its own horizontal track (row).
  - Transitions are drawn as step functions.
  - Interactive hovering shows exact cycle and signal state.
"""

from typing import Dict, List, Any

from logic_sim.signal import Signal

def _signal_to_float(s: Signal) -> float:
    """Convert a Signal to a float for plotting."""
    if s == Signal.HIGH:
        return 1.0
    elif s == Signal.LOW:
        return 0.0
    else:
        return 0.5  # UNKNOWN -> mid-rail

def _signal_to_label(s: Signal) -> str:
    """Convert a Signal to a string label for tooltips."""
    if s == Signal.HIGH:
        return "1 (HIGH)"
    elif s == Signal.LOW:
        return "0 (LOW)"
    else:
        return "X (UNKNOWN)"

def plot_waveform_plotly(
    signals: Dict[str, List[Signal]],
    title: str = "Digital Timing Diagram",
    time_unit: str = "Cycle",
) -> Any:
    """
    Plot an interactive digital timing diagram using Plotly.

    Args:
        signals:   Ordered dict of signal_name -> list of Signal values.
        title:     Plot title.
        time_unit: Label for the x-axis.

    Returns:
        A plotly.graph_objects.Figure instance.
    """
    try:
        import plotly.graph_objects as go
    except ImportError as e:
        raise ImportError(
            "plotly is required for waveform plotting. "
            "Install it with: pip install plotly"
        ) from e
        
    if not signals:
        raise ValueError("Cannot plot an empty signals dictionary.")

    lengths = {name: len(vals) for name, vals in signals.items()}
    if len(set(lengths.values())) > 1:
        raise ValueError(
            f"All signal traces must have equal length. Got: {lengths}"
        )
    n_steps = next(iter(lengths.values()))
    
    if n_steps == 0:
        return go.Figure()

    signal_names = list(signals.keys())
    n_signals = len(signal_names)

    fig = go.Figure()

    # Colors
    HIGH_COLOR = "#00d4aa"
    UNKNOWN_COLOR = "#ff6b35"
    
    # We plot signals from top to bottom.
    # To do this, we assign a vertical offset to each signal.
    # Signal 0 (first in dict) gets offset (n_signals - 1) * 2
    # Signal i gets offset (n_signals - 1 - i) * 2
    
    # Build y-axis ticks
    tickvals = []
    ticktext = []

    for i, name in enumerate(signal_names):
        offset = (n_signals - 1 - i) * 1.5
        tickvals.append(offset + 0.5)
        ticktext.append(name)
        
        trace_vals = signals[name]
        
        # We want to draw step functions. For n_steps, we have n_steps intervals.
        # So for step j, the value holds from time j to j+1.
        x_pts = []
        y_pts = []
        text_pts = []
        
        for j, val in enumerate(trace_vals):
            num_val = _signal_to_float(val)
            label = _signal_to_label(val)
            
            # Start of interval
            x_pts.append(j)
            y_pts.append(offset + num_val)
            text_pts.append(label)
            
            # End of interval
            x_pts.append(j + 1)
            y_pts.append(offset + num_val)
            text_pts.append(label)
            
            # For UNKNOWN signals, we could draw a hatched box, but in Plotly a simple 
            # line at 0.5 with a different color is easier.
            
        fig.add_trace(go.Scatter(
            x=x_pts,
            y=y_pts,
            mode='lines',
            line=dict(color=HIGH_COLOR, width=2, shape='linear'),
            name=name,
            text=text_pts,
            hovertemplate=f"<b>{name}</b><br>{time_unit}: %{{x}}<br>State: %{{text}}<extra></extra>"
        ))

    fig.update_layout(
        title=title,
        xaxis_title=time_unit,
        yaxis=dict(
            tickmode='array',
            tickvals=tickvals,
            ticktext=ticktext,
            showgrid=True,
            zeroline=False,
        ),
        xaxis=dict(
            tickmode='linear',
            tick0=0,
            dtick=1,
            range=[0, n_steps],
            showgrid=True,
        ),
        plot_bgcolor="#0f0f23",
        paper_bgcolor="#0f0f23",
        font=dict(color="#e0e0e0"),
        showlegend=False,
        margin=dict(l=80, r=20, t=50, b=50),
        height=max(300, n_signals * 80 + 100),
    )

    return fig
