"""
test_render.py — Tests for circuit rendering module (render.py).
"""

import os
import tempfile
import pytest

from logic_sim.netlist_parser import parse_netlist, parse_netlist_file
from logic_sim.render import render_circuit


class TestRenderCircuit:
    def test_render_half_adder_png(self):
        c = parse_netlist(
            "INPUT A B\n"
            "GATE SUM XOR A B\n"
            "GATE COUT AND A B\n"
            "OUTPUT SUM COUT\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            out_path = render_circuit(c, output_path=tmp_path)
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_render_full_adder_from_file(self):
        c = parse_netlist_file("examples/full_adder.net")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            out_path = render_circuit(c, output_path=tmp_path)
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_render_svg_format(self):
        c = parse_netlist("INPUT A\nGATE OUT NOT A\nOUTPUT OUT\n")
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            out_path = render_circuit(c, output_path=tmp_path)
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
