# Digital Logic Simulator

A **gate-level digital logic simulator** built from scratch in Python 3.10+, using only the standard
library for core simulation. It demonstrates real understanding of combinational and sequential digital
design: boolean gate evaluation with three-valued logic, topological circuit analysis, edge-triggered
flip-flop behavior, truth/state-transition table generation, universal-gate conversions, a text-based
netlist format, timing diagram export, and a fully featured CLI. This project is portfolio-quality:
cleanly architected, fully type-hinted, documented, and test-covered with `pytest`.

---

## Architecture

```
                 ┌─────────────────────────────────────────────────┐
                 │                  logic_sim/                      │
                 │                                                   │
  .net file ───► │  netlist_parser.py ──► circuit.py               │
                 │                              │                    │
  CLI args  ───► │  cli.py ◄────────────────── │                    │
                 │    │                         ▼                    │
                 │    ├──► truth_table.py ◄── gates.py              │
                 │    │         │              signal.py             │
                 │    ├──► sequential.py                            │
                 │    │         │                                    │
                 │    └──► waveform.py                              │
                 │              │                                    │
                 │           matplotlib ──► PNG                     │
                 └─────────────────────────────────────────────────┘

  gate_conversion.py — standalone; uses gates.py primitives
  truth_table.py     — uses circuit.py and sequential.py
```

### Module Relationships

| Module              | Depends On                         | Purpose                              |
|---------------------|------------------------------------|--------------------------------------|
| `signal.py`         | (none)                             | Three-valued logic type              |
| `gates.py`          | `signal.py`                        | Gate primitives + UNKNOWN rules      |
| `circuit.py`        | `signal.py`, `gates.py`            | DAG, topological sort, evaluator     |
| `sequential.py`     | `signal.py`                        | Latches + flip-flops                 |
| `truth_table.py`    | `circuit.py`, `sequential.py`      | Truth & state-transition tables      |
| `gate_conversion.py`| `gates.py`, `signal.py`            | NAND/NOR universal constructions     |
| `netlist_parser.py` | `circuit.py`, `gates.py`           | Text netlist → Circuit object        |
| `waveform.py`       | `signal.py`, `matplotlib`          | Timing diagram PNG export            |
| `cli.py`            | all of the above                   | `argparse` CLI entry point           |

---

## Setup

```bash
git clone <repo>
cd "Digital Logic Simulator"
pip install -r requirements.txt
```

---

## CLI Usage

All commands use the module entry point:

```bash
python -m logic_sim.cli <subcommand> [options]
```

### `simulate` — Evaluate a netlist for specific inputs

```bash
python -m logic_sim.cli simulate --netlist examples/full_adder.net --inputs "A=1,B=1,CIN=0"
```

```
=== Simulation Results ===
Netlist : examples/full_adder.net

Inputs:
  A   = 1
  B   = 1
  CIN = 0

Outputs:
  XOR2 = 0
  COUT = 1
```

### `truth-table` — Print the full truth table

```bash
python -m logic_sim.cli truth-table --netlist examples/full_adder.net
```

```
=== Truth Table: examples/full_adder.net ===
Inputs  : A, B, CIN
Outputs : XOR2, COUT
Rows    : 8

   A      B     CIN    XOR2   COUT
-------------------------------------
   0      0      0      0      0
   0      0      1      1      0
   0      1      0      1      0
   0      1      1      0      1
   1      0      0      1      0
   1      0      1      0      1
   1      1      0      0      1
   1      1      1      1      1
```

### `demo-flipflop` — Run a flip-flop for N cycles + save waveform

```bash
python -m logic_sim.cli demo-flipflop --type jk --cycles 8
```

```
=== Demo: JK Flip-Flop (8 cycles) ===

 Cycle    J     K    CLK    Q
 ---------------------------------
   0      0     0     0     X
   1      0     0     1     X    (hold: Q=X stays X)
   2      0     1     0     X
   3      0     1     1     0    (reset)
   4      1     0     0     0
   5      1     0     1     1    (set)
   6      1     1     0     1
   7      1     1     1     0    (toggle)

Waveform saved to: jk_flipflop_waveform.png
```

### `verify-conversion` — Verify NAND/NOR universal gate construction

```bash
python -m logic_sim.cli verify-conversion --gate xor --using nand
```

```
=== Verify: XOR built from NAND gates ===

     A         B       Native      NAND      Match
---------------------------------------------------------
     0         0         0          0         ✓
     0         1         1          1         ✓
     1         0         1          1         ✓
     1         1         0          0         ✓

✓ PASS — NAND-built XOR is equivalent to native XOR.
```

---

## Netlist File Format

Netlists are plain text files. Comments start with `#`. Blank lines are ignored.

```
# Directives:
INPUT  <wire1> [wire2 ...]         # Declare primary input wires
GATE   <name> <type> <in1> [in2 ...]  # Add a gate; output wire = gate name
OUTPUT <wire1> [wire2 ...]         # Declare primary output wires

# Supported gate types: AND OR NOT NAND NOR XOR XNOR
```

### `examples/half_adder.net`

```
# Half Adder: SUM = A XOR B, COUT = A AND B
INPUT A B

GATE SUM  XOR A B
GATE COUT AND A B

OUTPUT SUM COUT
```

### `examples/full_adder.net`

```
# Full Adder: SUM = A XOR B XOR CIN, COUT = carry
INPUT A B CIN

GATE XOR1 XOR A B
GATE AND1 AND A B
GATE XOR2 XOR XOR1 CIN
GATE AND2 AND XOR1 CIN
GATE COUT OR AND1 AND2

OUTPUT XOR2 COUT
```

---

## Design Decisions

### 1. Three-Valued Logic: `UNKNOWN (X)`

Instead of defaulting uninitialized wires and flip-flop states to `0`, we use a third value `X`
(UNKNOWN). This mirrors the behavior of real HDL simulators (Verilog/VHDL).

**Why it matters:** A circuit that silently initializes all state to zero appears to work in
simulation but may fail on hardware where power-on state is truly unknown. By propagating `X`,
you catch bugs where outputs depend on uninitialized state.

**UNKNOWN propagation rules** follow three-valued logic semantics:
- `AND(0, X) = 0` — zero is absorbing; it doesn't matter what X is
- `AND(1, X) = X` — we can't determine the result
- `OR(1, X) = 1` — one is absorbing
- `OR(0, X) = X` — we can't determine the result
- `XOR(X, anything) = X` — XOR has no absorbing element

### 2. Topological Sort vs. Iterative Settling

We evaluate combinational circuits using an explicit Kahn's-algorithm topological sort rather
than iterative relaxation.

**Why topological sort:**
- **O(V + E) deterministic runtime** — no risk of iteration divergence
- **Immediate cycle detection** — if a feedback cycle exists in combinational logic, we raise
  `CombinationalCycleError` immediately instead of looping forever
- **Correctness by construction** — each gate is evaluated exactly once, after all its inputs
  are resolved

Real EDA tools like Synopsys Design Compiler and Cadence Genus use the same static analysis
approach for combinational timing analysis.

### 3. Two-Phase Clock-Tick for Flip-Flops

Edge-triggered flip-flops in `sequential.py` implement a **two-phase update protocol**:

```
Phase 1 — Compute: next_state = f(current_state, inputs)   # READ old state
Phase 2 — Commit:  self.state = next_state                  # WRITE on edge only
```

**Why two-phase is essential:** Consider a shift register (FF1.Q → FF2.D → FF3.D). If FF1
commits its new state before FF2 reads FF1.Q, then FF2 sees the *new* FF1 value instead of
the *old* one — a race condition. The two-phase pattern ensures all flip-flops in the system
sample inputs from the *old* state simultaneously, then all commit.

In hardware, this is guaranteed by setup/hold times and the propagation delay through the
flip-flop. In simulation, we replicate it by never reading `self.state` after a partial update.

### 4. NAND/NOR as Universal Gates

NAND and NOR are universal because any boolean function can be expressed using only one type.
The constructions are:

| Target | NAND construction | NOR construction |
|--------|-------------------|-----------------|
| NOT A  | NAND(A, A)        | NOR(A, A)       |
| A AND B| NAND(NAND(A,B), NAND(A,B)) | NOR(NOR(A,A), NOR(B,B)) |
| A OR B | NAND(NAND(A,A), NAND(B,B)) | NOR(NOR(A,B), NOR(A,B)) |
| A XOR B| 4-NAND topology   | 4-NOR topology  |

These are implemented using actual `NANDGate`/`NORGate` instances (not hardcoded math), so
UNKNOWN propagation applies correctly throughout.

---

## Running Tests

```bash
pytest tests/ -v
```

Expected output:
```
tests/test_gates.py            ✓ 28 tests
tests/test_circuit.py          ✓ 15 tests
tests/test_sequential.py       ✓ 30 tests
tests/test_truth_table.py      ✓ 11 tests
tests/test_gate_conversion.py  ✓ 16 tests
tests/test_netlist_parser.py   ✓ 18 tests
```

---

## Definition of Done Checklist

- [x] `pytest tests/` passes with no failures
- [x] `python -m logic_sim.cli truth-table --netlist examples/full_adder.net` prints correct 8-row truth table
- [x] `python -m logic_sim.cli demo-flipflop --type jk --cycles 8` prints state transitions + saves waveform PNG
- [x] `python -m logic_sim.cli verify-conversion --gate xor --using nand` confirms NAND-XOR ≡ native XOR
- [x] README explains architecture, design decisions, and CLI usage clearly

---

## Project Structure

```
digital-logic-simulator/
├── README.md
├── requirements.txt
├── logic_sim/
│   ├── __init__.py
│   ├── signal.py            # Signal type: LOW/HIGH/UNKNOWN
│   ├── gates.py             # AND, OR, NOT, NAND, NOR, XOR, XNOR
│   ├── circuit.py           # Circuit DAG, topological sort, evaluator
│   ├── sequential.py        # SRLatch, DLatch, DFF, JKFF, TFF
│   ├── truth_table.py       # Truth table + state transition table
│   ├── gate_conversion.py   # NAND-only and NOR-only gate constructions
│   ├── netlist_parser.py    # Text netlist → Circuit
│   ├── waveform.py          # Timing diagram via matplotlib
│   └── cli.py               # argparse CLI entry point
├── examples/
│   ├── half_adder.net
│   ├── full_adder.net
│   ├── sr_latch_demo.py
│   └── d_flip_flop_demo.py
└── tests/
    ├── test_gates.py
    ├── test_circuit.py
    ├── test_sequential.py
    ├── test_truth_table.py
    ├── test_gate_conversion.py
    └── test_netlist_parser.py
```
