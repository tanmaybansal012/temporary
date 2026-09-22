import pytest
from logic_sim.netlist_parser import parse_netlist
from logic_sim.truth_table import generate_truth_table
from logic_sim.signal import Signal

def test_circuit_state_transition_table():
    netlist = """
    INPUT D CLK
    GATE FF1 DFF D CLK -> Q
    OUTPUT Q
    """
    c = parse_netlist(netlist)
    rows = generate_truth_table(c)
    # 1 flip-flop (2 states) * 1 data input D (2 states) = 4 rows
    assert len(rows) == 4
    for row in rows:
        d = row["D"].value
        q_current = row["FF1_state"].value
        q_next = row["FF1_next"].value
        # For DFF, Q_next should equal D, regardless of current state
        assert q_next == d
