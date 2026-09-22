import pytest
from logic_sim.signal import Signal
from logic_sim.plotly_waveform import plot_waveform_plotly

def test_plotly_waveform():
    try:
        import plotly.graph_objects as go
    except ImportError:
        pytest.skip("plotly is not installed")
        
    signals = {
        "CLK": [Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH],
        "D":   [Signal.LOW, Signal.LOW, Signal.HIGH, Signal.HIGH],
        "Q":   [Signal.UNKNOWN, Signal.LOW, Signal.LOW, Signal.HIGH]
    }
    
    fig = plot_waveform_plotly(signals, title="Test Waveform")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 3 # 3 signals
    
    # Check trace names match signal names
    trace_names = [trace.name for trace in fig.data]
    assert "CLK" in trace_names
    assert "D" in trace_names
    assert "Q" in trace_names
