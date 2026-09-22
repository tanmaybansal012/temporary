import streamlit as st
import pandas as pd
import sys
import os

# Ensure the logic_sim package can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from logic_sim.netlist_parser import parse_netlist
from logic_sim.truth_table import generate_truth_table
from logic_sim.simulation import simulate
from logic_sim.plotly_waveform import plot_waveform_plotly

# ---------------------------------------------------------
# Page Config & Custom CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Digital Logic Simulator",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Target Design System CSS
st.markdown("""
<style>
    /* Deep navy/dark blue background for the main page */
    .stApp {
        background-color: #0A192F;
        color: #E6F1FF;
        font-family: 'Inter', sans-serif;
    }
    
    /* Typography overrides */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', sans-serif;
        color: #E6F1FF !important;
        font-weight: 600;
    }
    
    /* Section headers (muted, gray uppercase) */
    .section-header {
        font-size: 0.85rem;
        text-transform: uppercase;
        color: #8892B0;
        font-weight: 700;
        letter-spacing: 0.1em;
        margin-bottom: 16px;
    }

    /* Content cards (lighter blue-grey, soft rounded corners 12px) */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #112240 !important;
        border: 1px solid #233554 !important;
        border-radius: 12px !important;
        padding: 4px !important;
    }
    
    /* Input fields and text areas */
    .stTextArea > div > div > textarea, 
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div {
        background-color: #020C1B !important;
        color: #00E5FF !important;
        border: 1px solid #233554 !important;
        border-radius: 8px !important;
        font-family: 'Courier New', Courier, monospace !important;
    }
    
    /* Vibrant teal/cyan primary buttons */
    .stButton > button {
        background-color: #00E5FF !important;
        color: #0A192F !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        transition: all 0.2s ease !important;
        padding: 0.6rem 1rem !important;
    }
    .stButton > button:hover {
        background-color: #00B3CC !important;
        transform: translateY(-2px) !important;
    }
    
    /* Custom Navbar Flexbox */
    .custom-navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 16px;
        margin-bottom: 24px;
        border-bottom: 1px solid #233554;
    }
    .navbar-title {
        font-size: 1.5rem;
        font-weight: 800;
        color: #00E5FF;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    /* Radio buttons disguised as right-aligned nav tabs */
    div[data-testid="stRadio"] > div {
        display: flex;
        justify-content: flex-end;
        gap: 16px;
    }
    div[data-testid="stRadio"] label {
        background-color: transparent !important;
        color: #8892B0 !important;
        border: none !important;
        font-weight: 600;
    }
    div[data-testid="stRadio"] label[data-checked="true"] {
        color: #00E5FF !important;
        border-bottom: 2px solid #00E5FF !important;
        border-radius: 0;
    }

    /* Markdown text high contrast */
    p, li {
        color: #E6F1FF !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Navbar
# ---------------------------------------------------------
st.markdown("""
<div class="custom-navbar">
    <div class="navbar-title">
     Digital Logic Simulator
    </div>
</div>
""", unsafe_allow_html=True)

# Secondary navigation aligned right
nav_col1, nav_col2 = st.columns([1, 1])
with nav_col2:
    nav_selection = st.radio("Navigation", ["Simulate", "Truth Table", "Circuit Info"], horizontal=True, label_visibility="collapsed")

# ---------------------------------------------------------
# Examples
# ---------------------------------------------------------
example_combinational = """INPUT A B
GATE AND1 AND A B -> Y
OUTPUT Y"""

example_sequential = """INPUT D CLK
GATE FF1 DFF D CLK -> Q QN
OUTPUT Q QN"""

# ---------------------------------------------------------
# Two-Column Layout
# ---------------------------------------------------------
col_left, col_right = st.columns([1, 1.2], gap="large")

with col_left:
    with st.container(border=True):
        st.markdown("<div class='section-header'>CIRCUIT NETLIST</div>", unsafe_allow_html=True)
        
        example_choice = st.selectbox("Load Example (Optional)", ["None", "Combinational (AND Gate)", "Sequential (D Flip-Flop)"])
        default_netlist = ""
        if example_choice == "Combinational (AND Gate)":
            default_netlist = example_combinational
        elif example_choice == "Sequential (D Flip-Flop)":
            default_netlist = example_sequential
            
        netlist_input = st.text_area("Netlist Code", value=default_netlist, height=250, label_visibility="collapsed")
        
        st.markdown("<div class='section-header' style='margin-top: 16px;'>VARIABLES</div>", unsafe_allow_html=True)
        num_cycles = st.number_input("Simulation Clock Cycles", min_value=1, max_value=50, value=10)
        
        # Main action button
        if st.button("Simulate Circuit", use_container_width=True):
            st.session_state["netlist"] = netlist_input
            st.session_state["cycles"] = num_cycles
            st.session_state["run_sim"] = True

with col_right:
    with st.container(border=True):
        st.markdown(f"<div class='section-header'>{nav_selection.upper()} RESULTS</div>", unsafe_allow_html=True)
        
        if st.session_state.get("run_sim"):
            try:
                # Compile
                c = parse_netlist(st.session_state["netlist"])
                
                # Show chosen tab content
                if nav_selection == "Simulate":
                    st.markdown("### Outputs (Waveform)")
                    
                    data_inputs = [n for n in c.input_names if n != "CLK"]
                    has_clk = "CLK" in c.input_names
                    steps = []
                    cycles = st.session_state["cycles"]
                    for i in range(cycles):
                        step = {}
                        if has_clk:
                            step["CLK"] = i % 2
                        
                        # Generate different frequencies for different data inputs
                        # so we can see combinations like A=0, B=1.
                        for idx, data_in in enumerate(data_inputs):
                            # If there's a clock, data inputs should hold for at least 2 cycles (1 full clock period)
                            base_period = 2 if has_clk else 1
                            period = base_period * (2 ** idx)
                            step[data_in] = (i // period) % 2
                            
                        steps.append(step)
                    
                    history = simulate(c, steps)
                    signals = {name: [] for name in c.wire_names}
                    for state in history:
                        for name, sig in state.items():
                            signals[name].append(sig)
                            
                    fig = plot_waveform_plotly(signals, title="", time_unit="Cycle")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("### Inputs")
                    st.markdown(f"**Primary Inputs:** `{', '.join(c.input_names)}` *(Data inputs auto-toggled for demo)*")
                    st.markdown(f"**Total Cycles:** `{cycles}`")
                    
                elif nav_selection == "Truth Table":
                    st.markdown("### Outputs (State Transition Table)")
                    rows = generate_truth_table(c)
                    str_rows = []
                    for r in rows:
                        str_rows.append({k: getattr(v, 'name', str(v)) for k, v in r.items()})
                    df = pd.DataFrame(str_rows)
                    st.dataframe(df, use_container_width=True)
                    
                elif nav_selection == "Circuit Info":
                    st.markdown("### Inputs & Architecture")
                    st.markdown(f"- **Primary Inputs:** {', '.join(c.input_names) if c.input_names else 'None'}")
                    st.markdown(f"- **Primary Outputs:** {', '.join(c.output_names) if c.output_names else 'None'}")
                    st.markdown(f"- **Total Gates:** {len(c._gates)}")
                    st.markdown(f"- **Sequential Elements:** {len(c.sequential_nodes)}")
                    if c.has_sequential:
                        st.info("Sequential circuit detected.")
                    else:
                        st.info("Combinational circuit detected.")
                        
            except Exception as e:
                st.error(f"Error compiling/simulating: {e}")
        else:
            st.info("Enter a netlist and click **Simulate Circuit** to view results.")
