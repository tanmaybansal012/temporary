

"""
exporter.py ?" Export internal Circuit DAG to Verilog code.
"""

from __future__ import annotations
from typing import List

import sys
from pathlib import Path

# Add project root to sys.path if running directly
repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from logic_sim.circuit import Circuit

def export_to_verilog(circuit: Circuit, module_name: str = "custom_module") -> str:
    """
    Generate synthesizable Verilog code for a given Circuit.
    """
    lines = []
    
    # 1. Module Declaration
    ports = circuit.input_names + circuit.output_names
    ports_str = ", ".join(ports)
    lines.append(f"module {module_name} ({ports_str});")
    lines.append("")
    
    # 2. Port Definitions
    if circuit.input_names:
        lines.append(f"    input {', '.join(circuit.input_names)};")
    if circuit.output_names:
        lines.append(f"    output {', '.join(circuit.output_names)};")
    
    # 3. Internal Wire Definitions
    internal_wires = set(circuit.wire_names) - set(circuit.input_names) - set(circuit.output_names)
    if internal_wires:
        lines.append(f"    wire {', '.join(sorted(internal_wires))};")
    lines.append("")
    
    # 4. Gate Evaluations
    for node in circuit.topological_sort():
        gate_type = node.gate.__class__.__name__
        in_names = [w.name for w in node.input_wires]
        out_names = [w.name for w in node.output_wires]
        
        # Single output gates usually drive out_names[0]
        if gate_type == "NOTGate":
            lines.append(f"    assign {out_names[0]} = ~{in_names[0]};")
        elif gate_type == "ANDGate":
            expr = " & ".join(in_names)
            lines.append(f"    assign {out_names[0]} = {expr};")
        elif gate_type == "ORGate":
            expr = " | ".join(in_names)
            lines.append(f"    assign {out_names[0]} = {expr};")
        elif gate_type == "NANDGate":
            expr = " & ".join(in_names)
            lines.append(f"    assign {out_names[0]} = ~({expr});")
        elif gate_type == "NORGate":
            expr = " | ".join(in_names)
            lines.append(f"    assign {out_names[0]} = ~({expr});")
        elif gate_type == "XORGate":
            expr = " ^ ".join(in_names)
            lines.append(f"    assign {out_names[0]} = {expr};")
        elif gate_type == "XNORGate":
            expr = " ^ ".join(in_names)
            lines.append(f"    assign {out_names[0]} = ~({expr});")
        elif gate_type in ("MUXGate", "MUX2Gate"):
            d0, d1, sel = in_names
            lines.append(f"    assign {out_names[0]} = {sel} ? {d1} : {d0};")
        elif gate_type in ("DEMUXGate", "DEMUX2Gate"):
            d, sel = in_names
            y0, y1 = out_names
            lines.append(f"    assign {y0} = {sel} ? 1'b0 : {d};")
            lines.append(f"    assign {y1} = {sel} ? {d} : 1'b0;")
        elif gate_type in ("DECODERGate", "DEC2X4Gate"):
            a0, a1 = in_names
            y0, y1, y2, y3 = out_names
            lines.append(f"    assign {y0} = (~{a1}) & (~{a0});")
            lines.append(f"    assign {y1} = (~{a1}) & {a0};")
            lines.append(f"    assign {y2} = {a1} & (~{a0});")
            lines.append(f"    assign {y3} = {a1} & {a0};")
        else:
            lines.append(f"    // WARNING: Unsupported gate type {gate_type}")
            
    lines.append("")
    lines.append("endmodule")
    
    return "\n".join(lines)


if __name__ == "__main__":
    from logic_sim.netlist_parser import parse_netlist
    sample = """
    INPUT A B
    GATE SUM XOR A B
    GATE COUT AND A B
    OUTPUT SUM COUT
    """
    circuit = parse_netlist(sample)
    print("// Synthesizable Verilog Export Demo (Half Adder):")
    print(export_to_verilog(circuit, module_name="half_adder"))
