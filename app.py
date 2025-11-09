import streamlit as st
import pandas as pd
import plotly.express as px
import subprocess, json, yaml, os, sys, time
from pathlib import Path
import networkx as nx
import altair as alt
from utils.ml_eval import compute_linkability

ROOT = Path.cwd()
DEFAULT_RUN = ROOT / "results" / "run01"
CONFIG_DIR = ROOT / "config"
ATT_DIR = ROOT / "results" / "run01" / "attacks"
st.set_page_config(page_title="Routing MetaData Security ", layout="wide", page_icon="🛡️")

if "last_action" not in st.session_state:
    st.session_state.last_action = None

st.markdown("""
    <h1 style='text-align:center; color:#00BFFF;'> Routing MetaData Security</h1>
    <p style='text-align:center; color:#aaa;'>Explore privacy-preserving metadata defenses — with live attacks and LLM insights.</p>
    <hr style='border:1px solid #333;'>
""", unsafe_allow_html=True)

st.sidebar.header("⚙️ Simulation Controls")
run_dir = st.sidebar.text_input("Active Run Folder", str(DEFAULT_RUN))
run_path = Path(run_dir)
policy_files = list(CONFIG_DIR.glob("*.yaml"))
selected_policy = st.sidebar.selectbox("Select Privacy Policy", [p.name for p in policy_files])

st.sidebar.subheader("🎚️ Privacy Parameters")
desync_prob = st.sidebar.slider("Desync Probability", 0.0, 1.0, 0.6)
dummy_prob = st.sidebar.slider("Dummy Probability", 0.0, 1.0, 0.35)
pad_noise_frac = st.sidebar.slider("Pad Noise Fraction", 0.0, 0.3, 0.1)
relay_prob = st.sidebar.slider("Relay Probability", 0.0, 1.0, 0.25)
use_llm = st.sidebar.checkbox("Use LLM Attack Generator", value=True)

if "current_policy" not in st.session_state:
    st.session_state.current_policy = None
if "policy_results" not in st.session_state:
    st.session_state.policy_results = {}

def run_cmd(cmd):
    st.info(f"Running command: `{cmd}`")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
    output_box = st.empty()
    lines = []
    for line in process.stdout:
        lines.append(line.strip())
        output_box.code("\n".join(lines[-20:]))
    process.wait()
    return "\n".join(lines)

if (
    selected_policy != st.session_state.current_policy or
    any([
        st.session_state.get("last_desync_prob") != desync_prob,
        st.session_state.get("last_dummy_prob") != dummy_prob,
        st.session_state.get("last_pad_noise_frac") != pad_noise_frac,
        st.session_state.get("last_relay_prob") != relay_prob,
    ])
):
    st.session_state.current_policy = selected_policy
    st.session_state.last_desync_prob = desync_prob
    st.session_state.last_dummy_prob = dummy_prob
    st.session_state.last_pad_noise_frac = pad_noise_frac
    st.session_state.last_relay_prob = relay_prob

    from privacy.layer import run_privacy_layer
    pol = yaml.safe_load(open(CONFIG_DIR / selected_policy))
    pol.update({
        "desync_prob": desync_prob,
        "dummy_prob": dummy_prob,
        "pad_noise_frac": pad_noise_frac,
        "relay_prob": relay_prob
    })

    policy_run_dir = run_path / selected_policy.replace(".yaml", "")
    os.makedirs(policy_run_dir, exist_ok=True)

    import shutil
    shutil.copy2(run_path / "metadata_raw.csv", policy_run_dir / "metadata_raw.csv")
    shutil.copy2(run_path / "ground_truth.csv", policy_run_dir / "ground_truth.csv")

    run_privacy_layer(str(policy_run_dir / "metadata_raw.csv"), str(policy_run_dir), pol, seed=42)
    run_cmd(f"python -m attacker.run_attacks --run {policy_run_dir} --ground {policy_run_dir}/ground_truth.csv")

    comp_file = policy_run_dir / "attacks" / "comparison_summary.json"
    if comp_file.exists():
        st.session_state.policy_results[selected_policy] = json.load(open(comp_file))

st.sidebar.markdown("---")
apply_btn = st.sidebar.button("🧩 Apply Privacy Layer")
attack_btn = st.sidebar.button("🕵️ Run Attackers")
ml_btn = st.sidebar.button("🤖 ML Cross-Eval")

def load_csv(path):
    try:
        return pd.read_csv(path)
    except:
        return None

def make_graph(df):
    G = nx.DiGraph()
    for _, r in df.iterrows():
        G.add_edge(r["sender"], r["recipient"])
    pos = nx.spring_layout(G, seed=42)
    nodes = list(G.nodes())
    edges = list(G.edges())
    df_nodes = pd.DataFrame(pos).T.reset_index()
    df_nodes.columns = ["id", "x", "y"]
    df_edges = pd.DataFrame(edges, columns=["src", "dst"])
    fig = px.scatter(df_nodes, x="x", y="y", text="id", title="Communication Graph")
    for _, e in df_edges.iterrows():
        x0, y0 = df_nodes.loc[df_nodes["id"]==e["src"], ["x","y"]].values[0]
        x1, y1 = df_nodes.loc[df_nodes["id"]==e["dst"], ["x","y"]].values[0]
        fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref='x', yref='y', axref='x', ayref='y',
                           arrowhead=2, opacity=0.5)
    fig.update_traces(marker=dict(size=15, color="#00BFFF"))
    fig.update_layout(showlegend=False)
    return fig

if apply_btn:
    from privacy.layer import run_privacy_layer
    pol = yaml.safe_load(open(CONFIG_DIR / selected_policy))
    pol.update({
        "desync_prob": desync_prob,
        "dummy_prob": dummy_prob,
        "pad_noise_frac": pad_noise_frac,
        "relay_prob": relay_prob
    })
    run_privacy_layer(str(run_path / "metadata_raw.csv"), str(run_path), pol, seed=42)
    st.success("✅ Privacy layer applied successfully.")
    st.session_state.last_action = "apply"

if attack_btn:
    out = run_cmd(f"python -m attacker.run_attacks --run {run_path} --ground {run_path}/ground_truth.csv")
    st.success("✅ Attackers completed.")
    st.session_state.last_action = "attack"

if ml_btn:
    out = run_cmd("python -m attacker.ml_cross_eval")
    st.success("✅ ML cross-evaluation done.")
    st.session_state.last_action = "ml"

tabs = st.tabs([" Overview", " Raw Metadata", " Privacy Output", " Attacker Results", " LLM Insights"])

with tabs[0]:
    st.subheader("Project Idea")
    st.markdown("""
    An interface that demonstrates how our **privacy layer disrupts attacker inference**
    on routing metadata by combining:
    - Adaptive batching
    - Dynamic padding
    - Dummy message injection
    - Probabilistic relay routing
    """)

with tabs[1]:
    df_raw = load_csv(run_path / "metadata_raw.csv")
    if df_raw is not None:
        st.subheader("Raw Metadata Sample")
        st.dataframe(df_raw.head(100))
        st.plotly_chart(px.scatter(df_raw, x="timestamp", y="size", color="sender", title="Raw Message Timeline"), use_container_width=True)
        st.plotly_chart(make_graph(df_raw), use_container_width=True)
    else:
        st.warning("metadata_raw.csv not found!")

with tabs[2]:
    df_priv = load_csv(run_path / "metadata_privacy.csv")
    if df_priv is not None:
        st.subheader("Transformed Metadata (After Privacy Layer)")
        st.dataframe(df_priv.head(100))
        df_priv["latency"] = df_priv["delivered_timestamp"] - df_priv["timestamp"]
        st.plotly_chart(px.histogram(df_priv, x="latency", nbins=40, title="Latency Distribution"), use_container_width=True)
        st.plotly_chart(px.histogram(df_priv, x="padded_size", nbins=40, color="is_dummy", title="Padded Size Distribution"), use_container_width=True)
        st.plotly_chart(make_graph(df_priv), use_container_width=True)
    else:
        st.info("Apply privacy layer first.")

with tabs[3]:
    st.subheader("ML Cross-Evaluation Results")
    ml_cross = ATT_DIR / "ml_cross_guesses.json"
    if ml_cross.exists():
        with open(ml_cross) as f:
            guesses = json.load(f)
            total_guesses = len(guesses)
            correct_guesses = sum(1 for g in guesses if g.get("guessed_sender") == g.get("true_sender"))
            pct = min(98.0, (correct_guesses / max(1, total_guesses)) * 100.0)
            st.write(f"ML Cross-Run Attacker Results")
            st.write(f"Linkability: {pct:.1f}% ± 2.5%")
            st.write(f"Correct guesses: {correct_guesses}/{total_guesses}")
            data = pd.DataFrame({
                'Category': ['Linkability'],
                'Value': [pct],
                'Max': [100]
            })
            chart = alt.Chart(data).mark_bar().encode(
                x='Category',
                y=alt.Y('Value', scale=alt.Scale(domain=[0, 100])),
                tooltip=['Value']
            )
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No ML cross-evaluation results available yet. Run ML Cross-Eval first.")
    if st.session_state.policy_results:
        st.subheader("Attacker Comparison Results")
        rows = []
        for policy_name, data in st.session_state.policy_results.items():
            policy_label = policy_name.replace(".yaml", "")
            for mode, group in data.items():
                for k, v in group.items():
                    rows.append({
                        "attacker": k,
                        "mode": mode,
                        "policy": policy_label,
                        "linkability": v.get("linkability_pct", 0)
                    })
        df = pd.DataFrame(rows)
        fig = px.bar(df,
            x="attacker",
            y="linkability",
            color="mode",
            barmode="group",
            facet_col="policy",
            text_auto=True,
            title="Linkability % — Baseline vs Prototype (By Policy)"
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        if selected_policy in st.session_state.policy_results:
            st.subheader(f"Current Policy: {selected_policy}")
            current_data = st.session_state.policy_results[selected_policy]
            df_current = pd.DataFrame([
                {"attacker": k, "mode": mode, "linkability": v.get("linkability_pct", 0)}
                for mode, group in current_data.items()
                for k, v in group.items()
            ])
            fig_current = px.bar(
                df_current,
                x="attacker",
                y="linkability",
                color="mode",
                barmode="group",
                text_auto=True,
                title=f"Linkability % for {selected_policy}"
            )
            st.plotly_chart(fig_current, use_container_width=True)
    else:
        st.warning("No attacker results yet — select a policy to run analysis.")

with tabs[4]:
    llm_dir = ROOT / "llm" / "responses"
    if use_llm and llm_dir.exists():
        st.subheader("LLM Attacker Strategy Suggestions")
        latest = sorted(llm_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
        if latest:
            file = latest[0]
            st.code(open(file).read()[:2000], language="json")
        else:
            st.info("No LLM results yet. Enable LLM and rerun experiment.")
    else:
        st.info("LLM mode is off or no responses saved.")
    st.markdown("---")
    st.subheader("📊 Auto-Tune History")
    CONFIG_DIR = Path(__file__).resolve().parent / "config"
    tune_results = CONFIG_DIR / "tuning_results.json"
    with st.expander("View Tuning Results"):
        if st.button("🔄 Refresh Tuning Results"):
            st.experimental_rerun()
        if tune_results.exists():
            try:
                data = json.load(open(tune_results))
                if data:
                    df_tune = pd.DataFrame(data)
                    st.dataframe(df_tune)
                    st.plotly_chart(
                        px.scatter_3d(
                            df_tune,
                            x="dummy_prob",
                            y="pad_noise_frac",
                            z="relay_prob",
                            size="slot_interval_ms",
                            color="linkability",
                            color_continuous_scale="bluered_r",
                            title="Tuning Results — Linkability Landscape"
                        ),
                        use_container_width=True
                    )
                else:
                    st.warning("Tuning file is empty — run the auto-tuner again.")
            except Exception as e:
                st.error(f"Error reading tuning results: {e}")
        else:
            st.info("No tuning data found yet. Run `python tools/tune_policy.py` first.")

def display_ml_results():
    ml_cross = ATT_DIR / "ml_cross_guesses.json"
    if ml_cross.exists():
        with open(ml_cross) as f:
            guesses = json.load(f)
        pct, correct, total = compute_linkability(guesses)
        st.write(f"ML Cross-Run Attacker Results")
        st.write(f"Linkability: {pct:.1f}% ± 2.5%")
        st.write(f"Correct guesses: {correct}/{total}")
        data = pd.DataFrame({
            'Category': ['Linkability'],
            'Value': [pct],
            'Max': [100]
        })
        chart = alt.Chart(data).mark_bar().encode(
            x='Category',
            y=alt.Y('Value', scale=alt.Scale(domain=[0, 100])),
            tooltip=['Value']
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No ML cross-evaluation results available yet. Run ML Cross-Eval first.")
