"""
gate_conversion.py — Universal gate implementations: NAND-only and NOR-only.

Universal Gates
===============
NAND and NOR are called "universal" gates because any boolean function can be
implemented using only one of them. This is practically significant:
  - In CMOS technology, NAND gates are often preferred (simpler, faster, less area)
  - Understanding these constructions demonstrates mastery of boolean algebra
    and De Morgan's laws

Standard textbook constructions implemented here:

NAND-only:
  NOT(A)     = NAND(A, A)
  AND(A, B)  = NOT(NAND(A, B)) = NAND(NAND(A,B), NAND(A,B))
  OR(A, B)   = NAND(NOT(A), NOT(B)) = NAND(NAND(A,A), NAND(B,B))
  XOR(A, B)  = NAND(NAND(A, NAND(A,B)), NAND(B, NAND(A,B)))

NOR-only:
  NOT(A)     = NOR(A, A)
  OR(A, B)   = NOT(NOR(A, B)) = NOR(NOR(A,B), NOR(A,B))
  AND(A, B)  = NOR(NOT(A), NOT(B)) = NOR(NOR(A,A), NOR(B,B))
  XOR(A, B)  = NOR(NOR(A, NOR(A,B)), NOR(B, NOR(A,B)))

Each function returns the Signal output for given Signal inputs, using our
actual Gate instances — not hardcoded boolean math. This means UNKNOWN
propagation is handled correctly throughout.
"""

from __future__ import annotations
from logic_sim.gates import NANDGate, NORGate
from logic_sim.signal import Signal


# ---------------------------------------------------------------------------
# Helper: evaluate a gate with given inputs in one line
# ---------------------------------------------------------------------------

def _nand(*signals: Signal) -> Signal:
    """Evaluate a NAND gate with the given Signal inputs."""
    g = NANDGate()
    g.inputs = list(signals)
    return g.evaluate()


def _nor(*signals: Signal) -> Signal:
    """Evaluate a NOR gate with the given Signal inputs."""
    g = NORGate()
    g.inputs = list(signals)
    return g.evaluate()


# ---------------------------------------------------------------------------
# NAND-only implementations
# ---------------------------------------------------------------------------

def nand_not(a: Signal) -> Signal:
    """
    NOT using only NAND: NOT(A) = NAND(A, A).

    Tying both inputs of a NAND together inverts the single input.
    """
    return _nand(a, a)


def nand_and(a: Signal, b: Signal) -> Signal:
    """
    AND using only NAND: AND(A,B) = NAND(NAND(A,B), NAND(A,B)).

    Double-inversion: NAND then NAND(result, result) = NOT(NOT(AND)) = AND.
    """
    nab = _nand(a, b)
    return _nand(nab, nab)


def nand_or(a: Signal, b: Signal) -> Signal:
    """
    OR using only NAND: OR(A,B) = NAND(NAND(A,A), NAND(B,B)).

    By De Morgan's law: A OR B = NOT(NOT(A) AND NOT(B))
    NOT(A) = NAND(A,A), NOT(B) = NAND(B,B)
    AND of NOT(A) and NOT(B) wrapped in outer NAND gives OR.
    """
    na = _nand(a, a)   # NOT A
    nb = _nand(b, b)   # NOT B
    return _nand(na, nb)


def nand_xor(a: Signal, b: Signal) -> Signal:
    """
    XOR using only NAND (4-NAND construction).

    XOR(A,B) = NAND(NAND(A, NAND(A,B)), NAND(B, NAND(A,B)))

    Derivation:
      Let W = NAND(A, B)
      Then: NOT(A AND NOT(A OR B)) AND NOT(B AND NOT(A OR B))
      Simplifies to the standard 4-NAND XOR topology.
    """
    w = _nand(a, b)                # W = NAND(A,B)
    x = _nand(a, w)                # X = NAND(A, W)
    y = _nand(b, w)                # Y = NAND(B, W)
    return _nand(x, y)             # XOR = NAND(X, Y)


# ---------------------------------------------------------------------------
# NOR-only implementations
# ---------------------------------------------------------------------------

def nor_not(a: Signal) -> Signal:
    """
    NOT using only NOR: NOT(A) = NOR(A, A).

    Tying both inputs of a NOR together inverts the single input.
    (Dual of the NAND-NOT construction.)
    """
    return _nor(a, a)


def nor_or(a: Signal, b: Signal) -> Signal:
    """
    OR using only NOR: OR(A,B) = NOR(NOR(A,B), NOR(A,B)).

    Double-inversion: NOR then NOR(result, result) = NOT(NOT(OR)) = OR.
    """
    nab = _nor(a, b)
    return _nor(nab, nab)


def nor_and(a: Signal, b: Signal) -> Signal:
    """
    AND using only NOR: AND(A,B) = NOR(NOR(A,A), NOR(B,B)).

    By De Morgan's law: A AND B = NOT(NOT(A) OR NOT(B))
    NOT(A) = NOR(A,A), NOT(B) = NOR(B,B)
    OR of NOT(A) and NOT(B) wrapped in outer NOR gives AND.
    """
    na = _nor(a, a)    # NOT A
    nb = _nor(b, b)    # NOT B
    return _nor(na, nb)


def nor_xor(a: Signal, b: Signal) -> Signal:
    """
    XOR using only NOR (5-NOR construction).

    Algebraic derivation:
      Let W = NOR(A, B) = (A + B)'

      NOR(A, W) = (A + W)' = (A + (A+B)')' = A'·(A+B) = A'B
      NOR(B, W) = (B + W)' = (B + (A+B)')' = B'·(A+B) = AB'

      NOR(NOR(A,W), NOR(B,W)) = NOR(A'B, AB')
                               = (A'B + AB')' = XNOR(A, B)

    So the symmetric 4-NOR topology produces XNOR, not XOR!
    One additional NOR (self-inversion) converts XNOR → XOR:

      NOT(XNOR) = NOR(XNOR, XNOR) = XOR

    Total: 5 NOR gates.
    """
    w    = _nor(a, b)              # W    = NOR(A, B) = (A+B)'
    x    = _nor(a, w)              # X    = NOR(A, W) = A'B
    y    = _nor(b, w)              # Y    = NOR(B, W) = AB'
    xnor = _nor(x, y)             # XNOR = NOR(A'B, AB') = XNOR(A,B)
    return _nor(xnor, xnor)        # XOR  = NOT(XNOR) = NOR(XNOR, XNOR)


# ---------------------------------------------------------------------------
# Registry for CLI use
# ---------------------------------------------------------------------------

# Maps (gate_name, universal_gate) -> function(a, b) -> Signal
# NOT is special-cased (single input) in cli.py
CONVERSION_REGISTRY: dict[tuple[str, str], object] = {
    ("and",  "nand"): nand_and,
    ("or",   "nand"): nand_or,
    ("not",  "nand"): nand_not,
    ("xor",  "nand"): nand_xor,
    ("and",  "nor"):  nor_and,
    ("or",   "nor"):  nor_or,
    ("not",  "nor"):  nor_not,
    ("xor",  "nor"):  nor_xor,
}
