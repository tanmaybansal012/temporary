import pytest
from logic_sim.netlist_parser import parse_netlist
from logic_sim.simulation import simulate
from logic_sim.signal import Signal

def test_simulate_dff():
    netlist = """
    INPUT D CLK
    GATE FF1 DFF D CLK -> Q QN
    OUTPUT Q QN
    """
    c = parse_netlist(netlist)
    steps = [
        {"CLK": 0, "D": 0}, # initial state, D=0
        {"CLK": 1, "D": 0}, # rising edge, Q should become 0
        {"CLK": 0, "D": 1}, # falling edge, Q holds 0, D changes to 1
        {"CLK": 1, "D": 1}, # rising edge, Q should become 1
        {"CLK": 0, "D": 0}, # falling edge, Q holds 1, D changes to 0
    ]
    history = simulate(c, steps)
    
    assert len(history) == 5
    
    # Step 0: CLK=0, D=0. Q is UNKNOWN before the first rising edge
    assert history[0]["CLK"] == Signal.LOW
    assert history[0]["Q"] == Signal.UNKNOWN
    
    # Step 1: CLK=1, D=0. This step *causes* the rising edge. The history 
    # captures the state *during* this step's combinational propagation 
    # (before the DFF commits). Wait, if DFF commits at the end of the step,
    # then during step 1, Q is still UNKNOWN.
    # Actually, in our simulate(), Q gets updated AT THE END of the step.
    # So history[1]["Q"] is UNKNOWN.
    # history[2]["Q"] will be LOW because it captures the state at the start of step 2.
    assert history[1]["Q"] == Signal.UNKNOWN
    
    # Step 2: CLK=0, Q is now LOW from previous edge
    assert history[2]["Q"] == Signal.LOW
    
    # Step 3: CLK=1, D=1. Rising edge. Q becomes HIGH *after* this step.
    assert history[3]["Q"] == Signal.LOW
    
    # Step 4: CLK=0, D=0. Q is HIGH from previous edge.
    assert history[4]["Q"] == Signal.HIGH
    assert history[4]["QN"] == Signal.LOW
