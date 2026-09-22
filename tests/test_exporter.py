"""
tests/test_exporter.py — Unit tests for Verilog export functionality.
"""

import pytest
from logic_sim.circuit import Circuit
from logic_sim.netlist_parser import parse_netlist
from logic_sim.exporter import export_to_verilog


def test_export_half_adder():
    netlist = """
    INPUT A B
    GATE SUM XOR A B
    GATE COUT AND A B
    OUTPUT SUM COUT
    """
    circuit = parse_netlist(netlist)
    verilog = export_to_verilog(circuit, module_name="half_adder")

    assert "module half_adder (A, B, SUM, COUT);" in verilog
    assert "input A, B;" in verilog
    assert "output SUM, COUT;" in verilog
    assert "assign SUM = A ^ B;" in verilog
    assert "assign COUT = A & B;" in verilog
    assert "endmodule" in verilog


def test_export_mux_demux():
    netlist = """
    INPUT D SEL
    GATE M MUX2 D D SEL -> Y
    OUTPUT Y
    """
    circuit = parse_netlist(netlist)
    verilog = export_to_verilog(circuit, module_name="mux_test")

    assert "module mux_test" in verilog
    assert "assign Y = SEL ? D : D;" in verilog
