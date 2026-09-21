import pytest
from logic_sim.signal import Signal
from logic_sim.gates import MUX2Gate, MUX4Gate, DEC2X4Gate, DEC3X8Gate

L = Signal.LOW
H = Signal.HIGH
X = Signal.UNKNOWN

class TestMUX2Gate:
    def test_mux2_select_0(self):
        g = MUX2Gate()
        g.inputs = [H, L, L]  # A=H, B=L, SEL=L -> A (H)
        assert g.evaluate() == H

        g.inputs = [L, H, L]  # A=L, B=H, SEL=L -> A (L)
        assert g.evaluate() == L

    def test_mux2_select_1(self):
        g = MUX2Gate()
        g.inputs = [H, L, H]  # A=H, B=L, SEL=H -> B (L)
        assert g.evaluate() == L

        g.inputs = [L, H, H]  # A=L, B=H, SEL=H -> B (H)
        assert g.evaluate() == H

    def test_mux2_select_x(self):
        g = MUX2Gate()
        g.inputs = [H, L, X]
        assert g.evaluate() == X

class TestDEC2X4Gate:
    def test_dec2x4_enable_0(self):
        g = DEC2X4Gate()
        g.inputs = [H, H, L] # EN=0
        assert g.evaluate() == (L, L, L, L)

    def test_dec2x4_enable_1(self):
        g = DEC2X4Gate()
        g.inputs = [L, L, H] # A0=0, A1=0, EN=1
        assert g.evaluate() == (H, L, L, L)

        g.inputs = [H, L, H] # A0=1, A1=0, EN=1
        assert g.evaluate() == (L, H, L, L)

        g.inputs = [L, H, H] # A0=0, A1=1, EN=1
        assert g.evaluate() == (L, L, H, L)

        g.inputs = [H, H, H] # A0=1, A1=1, EN=1
        assert g.evaluate() == (L, L, L, H)

    def test_dec2x4_unknown(self):
        g = DEC2X4Gate()
        g.inputs = [X, L, H]
        y0, y1, y2, y3 = g.evaluate()
        assert y0 == X
        assert y1 == X
        assert y2 == L
        assert y3 == L
