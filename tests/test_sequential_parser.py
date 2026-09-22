"""
tests/test_sequential_parser.py — Unit tests for parsing sequential components.
"""
import pytest
from logic_sim.netlist_parser import parse_netlist

def test_parse_dff():
    netlist = """
    INPUT D CLK
    GATE F1 DFF D CLK -> Q QN
    OUTPUT Q
    """
    c = parse_netlist(netlist)
    assert c.has_sequential
    assert len(c.sequential_nodes) == 1
    node = c.get_gate("F1")
    assert node.element.__class__.__name__ == "DFlipFlop"
    assert node.input_names_mapped == ["D", "CLK"]
    assert len(node.output_wires) == 2
    assert node.output_wires[0].name == "Q"
    assert node.output_wires[1].name == "QN"

def test_parse_jff_srlatch():
    netlist = """
    INPUT S R EN
    GATE LATCH1 SRLATCH S R EN -> Q
    OUTPUT Q
    """
    c = parse_netlist(netlist)
    node = c.get_gate("LATCH1")
    assert node.element.__class__.__name__ == "SRLatch"
    assert node.input_names_mapped == ["S", "R", "En"]
