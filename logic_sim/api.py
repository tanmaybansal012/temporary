"""
api.py — FastAPI backend for Digital Logic Simulator
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Union

from logic_sim.netlist_parser import parse_netlist
from logic_sim.truth_table import generate_truth_table
from logic_sim.simulation import simulate
from logic_sim.signal import Signal

app = FastAPI(title="Digital Logic Simulator API")

class ParseRequest(BaseModel):
    netlist: str

class SimulateRequest(BaseModel):
    netlist: str
    steps: List[Dict[str, Union[int, str]]] # e.g. {"CLK": 1, "D": 0}

@app.post("/parse")
def api_parse(req: ParseRequest):
    try:
        c = parse_netlist(req.netlist)
        return {
            "inputs": c.input_names,
            "outputs": c.output_names,
            "gate_count": len(c.gate_names),
            "sequential_count": len(c.sequential_nodes),
            "is_sequential": c.has_sequential
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/truth_table")
def api_truth_table(req: ParseRequest):
    try:
        c = parse_netlist(req.netlist)
        rows = generate_truth_table(c)
        # Convert Signal to string/int for JSON serialization
        json_rows = []
        for row in rows:
            j_row = {}
            for k, v in row.items():
                if isinstance(v, Signal):
                    j_row[k] = v.name # 'HIGH', 'LOW', 'UNKNOWN'
                else:
                    j_row[k] = str(v)
            json_rows.append(j_row)
        
        # We also want to return the headers
        if c.has_sequential:
            seq_names = [n.name for n in c.sequential_nodes]
            data_inputs = [n for n in c.input_names if n != "CLK"]
            headers = [f"{n}_state" for n in seq_names] + data_inputs + [f"{n}_next" for n in seq_names] + c.output_names
        else:
            headers = c.input_names + c.output_names
            
        return {
            "headers": headers,
            "rows": json_rows
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/simulate")
def api_simulate(req: SimulateRequest):
    try:
        c = parse_netlist(req.netlist)
        
        # Convert step values back to Signal
        sim_steps = []
        for step in req.steps:
            s_step = {}
            for k, v in step.items():
                if isinstance(v, int):
                    s_step[k] = Signal.from_int(v)
                elif isinstance(v, str):
                    s_step[k] = getattr(Signal, v.upper(), Signal.UNKNOWN)
            sim_steps.append(s_step)
            
        history = simulate(c, sim_steps)
        
        # Convert history for JSON
        json_history = []
        for state in history:
            j_state = {}
            for k, v in state.items():
                j_state[k] = v.name
            json_history.append(j_state)
            
        return {
            "signals": c.wire_names,
            "history": json_history
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
