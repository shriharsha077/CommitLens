"""
app.py - CommitLens Developer Intelligence & Code Churn HUD.

A developer-centric repository intelligence dashboard inspired by modern code editors
and dev tools. Computes real-time Git telemetry, contributor distribution,
file-hotspot treemaps, and line churn dynamics.
"""

import os
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from commitlens.scanner import scan_repo
from commitlens.analytics import (
    total_commits,
    commits_by_author,
    file_change_frequency,
    lines_changed,
    code_churn,
)

# -----------------------------------------------------------------------------
# Streamlit Application Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="CommitLens // Dev Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Developer Tool Aesthetic & Typography (Deep Charcoal + Electric Lime)
# -----------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg-dark: #0B0F14;
    --surface-dark: #11161F;
    --surface-hover: #161D27;
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-active: rgba(163, 230, 53, 0.3);
    --text-primary: #E2E8F0;
    --text-muted: #8B949E;
    --accent-lime: #A3E635;
    --accent-coral: #F87171;
    --accent-cyan: #38BDF8;
    --font-mono: 'JetBrains Mono', monospace;
    --font-sans: 'Inter', sans-serif;
}

html, body, [class*="css"] {
    font-family: var(--font-sans);
    color: var(--text-primary);
}

code, pre, .mono-text {
    font-family: var(--font-mono) !important;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background-color: #0E131A;
    border-right: 1px solid var(--border-subtle);
}

section[data-testid="stSidebar"] .block-container {
    padding-top: 1.8rem;
    padding-left: 1.2rem;
    padding-right: 1.2rem;
}

/* Repository Context Header HUD */
.repo-hud-banner {
    background: linear-gradient(180deg, #121822 0%, #0E131A 100%);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 1.2rem;
    position: relative;
    overflow: hidden;
}

.repo-hud-banner::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background: var(--accent-lime);
}

.repo-hud-eyebrow {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    color: var(--accent-lime);
    text-transform: uppercase;
    margin-bottom: 0.25rem;
    display: flex;
    align-items: center;
    gap: 8px;
}

.repo-hud-title {
    font-family: var(--font-sans);
    font-size: 1.7rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #F8FAFC;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 10px;
}

.repo-hud-metadata {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    margin-top: 0.6rem;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--text-muted);
}

.repo-chip {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--border-subtle);
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-mono);
}

.pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background-color: var(--accent-lime);
    box-shadow: 0 0 8px var(--accent-lime);
    display: inline-block;
}

/* Polished Metrics Strip */
.metrics-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    background: #11161F;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    margin-bottom: 1.5rem;
    overflow: hidden;
}

.metric-strip-item {
    padding: 0.9rem 1.1rem;
    border-right: 1px solid var(--border-subtle);
    transition: background-color 0.15s ease;
}

.metric-strip-item:last-child {
    border-right: none;
}

.metric-strip-item:hover {
    background-color: rgba(255, 255, 255, 0.02);
}

.strip-label {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.3rem;
}

.strip-value {
    font-family: var(--font-mono);
    font-size: 1.55rem;
    font-weight: 700;
    color: #F8FAFC;
    line-height: 1.1;
}

.strip-val-lime { color: var(--accent-lime); }
.strip-val-coral { color: var(--accent-coral); }
.strip-val-cyan { color: var(--accent-cyan); }

/* Terminal style alert cards */
.terminal-card {
    background: #0E131A;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 1.25rem 1.4rem;
    font-family: var(--font-mono);
    font-size: 0.88rem;
    line-height: 1.5;
    margin: 1rem 0;
}

.terminal-card-err {
    border-left: 4px solid var(--accent-coral);
}

.terminal-card-warn {
    border-left: 4px solid #FBBF24;
}

.terminal-card-info {
    border-left: 4px solid var(--accent-cyan);
}

/* Tab container fine-tuning */
button[data-baseweb="tab"] {
    font-family: var(--font-mono) !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.02em;
    padding-top: 0.6rem !important;
    padding-bottom: 0.6rem !important;
}

div[data-baseweb="tab-highlight"] {
    background-color: var(--accent-lime) !important;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Formatting Helpers (Ensures consistent sign formatting, strictly preventing -0)
# -----------------------------------------------------------------------------
def format_additions(val: int) -> str:
    """Format additions: positive shows +N, zero shows 0."""
    return f"+{val:,}" if val > 0 else "0"


def format_deletions(val: int) -> str:
    """Format deletions: positive shows -N, zero shows 0 (never -0)."""
    return f"-{val:,}" if val > 0 else "0"


def format_delta(val: int) -> str:
    """Format net change: positive +N, negative -N, zero 0."""
    if val > 0:
        return f"+{val:,}"
    elif val < 0:
        return f"{val:,}"
    return "0"


# -----------------------------------------------------------------------------
# Data Processing & Repository Scan
# -----------------------------------------------------------------------------
def analyze_repository(repo_path: str):
    """
    Extract commit telemetry and compute repository metrics using CommitLens core modules.

    Args:
        repo_path (str): Path to local Git repository.

    Returns:
        dict: Processed repository data containing commits, line_stats,
              author_counts, file_freq, churn_data, and enriched DataFrame.
    """
    raw_commits = scan_repo(repo_path)
    total_commit_count = total_commits(raw_commits)
    author_counts = commits_by_author(raw_commits)
    file_freq = file_change_frequency(repo_path)
    line_stats = lines_changed(repo_path)
    churn_data = code_churn(line_stats)

    df_commits = pd.DataFrame(raw_commits)

    if not df_commits.empty:
        line_stats_map = {
            item["hash"]: (item["lines_added"], item["lines_deleted"])
            for item in line_stats
        }

        df_commits["lines_added"] = df_commits["hash"].map(
            lambda h: line_stats_map.get(h, (0, 0))[0]
        )
        df_commits["lines_deleted"] = df_commits["hash"].map(
            lambda h: line_stats_map.get(h, (0, 0))[1]
        )
        df_commits["churn"] = df_commits["lines_added"] + df_commits["lines_deleted"]
        df_commits["short_hash"] = df_commits["hash"].str[:7]

        # Datetime processing
        df_commits["datetime"] = pd.to_datetime(df_commits["date"], utc=True)
        df_commits["formatted_date"] = df_commits["datetime"].dt.tz_convert(None).dt.strftime("%Y-%m-%d %H:%M")
        df_commits["date_only"] = df_commits["datetime"].dt.tz_convert(None).dt.date
    else:
        df_commits = pd.DataFrame(
            columns=[
                "hash", "author", "date", "message",
                "lines_added", "lines_deleted", "churn",
                "short_hash", "datetime", "formatted_date", "date_only"
            ]
        )

    return {
        "raw_commits": raw_commits,
        "total_commits": total_commit_count,
        "author_counts": author_counts,
        "file_freq": file_freq,
        "line_stats": line_stats,
        "churn_data": churn_data,
        "df_commits": df_commits,
    }


def style_plot(fig, title: str = "", height: int = 360):
    """Apply consistent developer dark-mode styling across all Plotly charts."""
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(family="JetBrains Mono, monospace", size=13, color="#E2E8F0"),
            x=0.01,
            y=0.96,
        ),
        margin=dict(l=20, r=20, t=45, b=25),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono, monospace", size=11, color="#8B949E"),
        hoverlabel=dict(
            bgcolor="#161D27",
            bordercolor="rgba(163, 230, 53, 0.4)",
            font=dict(family="JetBrains Mono, monospace", size=11, color="#F8FAFC"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            title_text="",
            font=dict(size=10, color="#8B949E"),
        ),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255, 255, 255, 0.05)",
        linecolor="rgba(255, 255, 255, 0.12)",
        zerolinecolor="rgba(255, 255, 255, 0.15)",
        tickfont=dict(family="JetBrains Mono, monospace", size=10, color="#8B949E"),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255, 255, 255, 0.05)",
        linecolor="rgba(255, 255, 255, 0.12)",
        zerolinecolor="rgba(255, 255, 255, 0.15)",
        tickfont=dict(family="JetBrains Mono, monospace", size=10, color="#8B949E"),
    )
    return fig


# -----------------------------------------------------------------------------
# Sidebar: Control Panel
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 0.3rem;">
            <span style="font-size: 1.35rem;">⚡</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 1.15rem; color: #F8FAFC; letter-spacing: -0.01em;">CommitLens</span>
        </div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #8B949E; margin-bottom: 1.2rem; text-transform: uppercase; letter-spacing: 0.06em;">
            Git Intelligence Engine v0.3
        </div>
        """,
        unsafe_allow_html=True,
    )

    default_workspace_path = os.path.abspath(".")
    repo_input = st.text_input(
        "REPOSITORY PATH",
        value=default_workspace_path,
        help="Provide the local filesystem path containing a .git repository.",
    )

    c_btn1, c_btn2 = st.columns([1, 1])
    with c_btn1:
        trigger_analyze = st.button("EXECUTE", use_container_width=True, type="primary")
    with c_btn2:
        reset_current = st.button("RESET", use_container_width=True)
        if reset_current:
            repo_input = default_workspace_path

    st.markdown("<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 1.2rem 0;'>", unsafe_allow_html=True)
    
    st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.72rem; color: #8B949E; margin-bottom: 0.4rem; text-transform: uppercase;'>DISPLAY PARAMS</div>", unsafe_allow_html=True)
    top_n_hotspots = st.slider("Top Hotspots Limit", min_value=5, max_value=40, value=15, step=5)
    
    st.markdown("<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 1.2rem 0;'>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #64748B; line-height: 1.6;">
            <div>● DIRECT GIT REPO PARSER</div>
            <div>● ZERO EXTERNAL TELEMETRY</div>
            <div>● PURE LOCAL COMPUTATION</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Repository Validation & Execution
# -----------------------------------------------------------------------------
target_path = repo_input.strip() if repo_input else ""

if not target_path:
    st.markdown(
        """
        <div class="terminal-card terminal-card-info">
            <span style="color: var(--accent-cyan);">[INFO]</span> No repository path specified. Enter a path in the sidebar to run analysis.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

try:
    with st.spinner("Analyzing Git repository history..."):
        repo_data = analyze_repository(target_path)
except FileNotFoundError as fnf_err:
    st.markdown(
        f"""
        <div class="terminal-card terminal-card-err">
            <span style="color: var(--accent-coral);">[ERROR: PATH_NOT_FOUND]</span> {fnf_err}<br><br>
            <span style="color: var(--text-muted);">→ Verify the path exists on disk. Use <code>.</code> for current working directory.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()
except ValueError as val_err:
    st.markdown(
        f"""
        <div class="terminal-card terminal-card-warn">
            <span style="color: #FBBF24;">[WARNING: INVALID_GIT_REPO]</span> {val_err}<br><br>
            <span style="color: var(--text-muted);">→ Ensure this directory contains a valid <code>.git</code> folder initialized via <code>git init</code>.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()
except Exception as unk_err:
    st.markdown(
        f"""
        <div class="terminal-card terminal-card-err">
            <span style="color: var(--accent-coral);">[CRITICAL_FAILURE]</span> {unk_err}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# Unpack verified data
raw_commits = repo_data["raw_commits"]
total_c = repo_data["total_commits"]
author_counts = repo_data["author_counts"]
file_freq = repo_data["file_freq"]
line_stats = repo_data["line_stats"]
churn_data = repo_data["churn_data"]
df_commits = repo_data["df_commits"]

abs_repo_path = os.path.abspath(target_path)
repo_folder_name = os.path.basename(abs_repo_path) or "root"
head_hash = df_commits.iloc[0]["short_hash"] if not df_commits.empty else "NONE"
latest_commit_date = df_commits.iloc[0]["formatted_date"] if not df_commits.empty else "N/A"
status_dot = '<span class="pulse-dot"></span>' if total_c > 0 else '<span style="color: #FBBF24; font-size: 0.8rem;">●</span>'
status_label = "ONLINE" if total_c > 0 else "EMPTY REPO"

# -----------------------------------------------------------------------------
# Distinctive Repository Context Header HUD
# -----------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="repo-hud-banner">
        <div class="repo-hud-eyebrow">
            {status_dot}
            COMMITLENS // REPOSITORY TELEMETRY // {status_label}
        </div>
        <div class="repo-hud-title">
            <span>📦</span> {repo_folder_name}
        </div>
        <div class="repo-hud-metadata">
            <span class="repo-chip">📁 <code>{abs_repo_path}</code></span>
            <span class="repo-chip">HEAD: <code>{head_hash}</code></span>
            <span class="repo-chip">LAST COMMIT: <code>{latest_commit_date}</code></span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Empty Repository State
# -----------------------------------------------------------------------------
if total_c == 0:
    st.markdown(
        """
        <div class="terminal-card terminal-card-warn">
            <span style="color: #FBBF24;">[EMPTY_REPOSITORY]</span> Repository initialized, but contains 0 commits on HEAD.<br><br>
            <span style="color: var(--text-muted);">Create your initial commit (<code>git add . && git commit -m "Initial commit"</code>) to view analysis.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # Render compact empty metrics strip with proper zeros (never -0 or +0)
    st.markdown(
        """
        <div class="metrics-strip">
            <div class="metric-strip-item"><div class="strip-label">TOTAL COMMITS</div><div class="strip-value">0</div></div>
            <div class="metric-strip-item"><div class="strip-label">AUTHORS</div><div class="strip-value">0</div></div>
            <div class="metric-strip-item"><div class="strip-label">FILES TOUCHED</div><div class="strip-value">0</div></div>
            <div class="metric-strip-item"><div class="strip-label">LINES ADDED</div><div class="strip-value">0</div></div>
            <div class="metric-strip-item"><div class="strip-label">LINES DELETED</div><div class="strip-value">0</div></div>
            <div class="metric-strip-item"><div class="strip-label">TOTAL CHURN</div><div class="strip-value">0</div></div>
            <div class="metric-strip-item"><div class="strip-label">NET CODE DELTA</div><div class="strip-value">0</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# -----------------------------------------------------------------------------
# Polished Metrics Strip (Strictly prevents negative zero)
# -----------------------------------------------------------------------------
additions_formatted = format_additions(churn_data["total_lines_added"])
deletions_formatted = format_deletions(churn_data["total_lines_deleted"])

net_delta = churn_data["total_lines_added"] - churn_data["total_lines_deleted"]
net_delta_str = format_delta(net_delta)

add_class = "strip-val-lime" if churn_data["total_lines_added"] > 0 else ""
del_class = "strip-val-coral" if churn_data["total_lines_deleted"] > 0 else ""
net_class = "strip-val-lime" if net_delta > 0 else ("strip-val-coral" if net_delta < 0 else "")

st.markdown(
    f"""
    <div class="metrics-strip">
        <div class="metric-strip-item">
            <div class="strip-label">TOTAL COMMITS</div>
            <div class="strip-value">{total_c:,}</div>
        </div>
        <div class="metric-strip-item">
            <div class="strip-label">AUTHORS</div>
            <div class="strip-value">{len(author_counts):,}</div>
        </div>
        <div class="metric-strip-item">
            <div class="strip-label">FILES TOUCHED</div>
            <div class="strip-value">{len(file_freq):,}</div>
        </div>
        <div class="metric-strip-item">
            <div class="strip-label">LINES ADDED</div>
            <div class="strip-value {add_class}">{additions_formatted}</div>
        </div>
        <div class="metric-strip-item">
            <div class="strip-label">LINES DELETED</div>
            <div class="strip-value {del_class}">{deletions_formatted}</div>
        </div>
        <div class="metric-strip-item">
            <div class="strip-label">TOTAL CHURN</div>
            <div class="strip-value">{churn_data['total_churn']:,}</div>
        </div>
        <div class="metric-strip-item">
            <div class="strip-label">NET CODE DELTA</div>
            <div class="strip-value {net_class}">{net_delta_str}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Developer Tabs: Engineering Intelligence Modules
# -----------------------------------------------------------------------------
tab_activity, tab_authors, tab_hotspots, tab_churn, tab_commits = st.tabs(
    [
        "CADENCE // ACTIVITY",
        "CONTRIBUTORS // SHARE",
        "HOTSPOTS // FILES",
        "CHURN // DYNAMICS",
        "COMMITS // EXPLORER",
    ]
)

# -----------------------------------------------------------------------------
# Tab 1: Cadence // Activity
# -----------------------------------------------------------------------------
with tab_activity:
    col_act_left, col_act_right = st.columns([1.1, 0.9])

    with col_act_left:
        st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-bottom: 0.5rem;'>COMMIT CADENCE TIMELINE</div>", unsafe_allow_html=True)
        if not df_commits.empty:
            daily_commits = (
                df_commits.groupby("date_only")
                .size()
                .reset_index(name="commit_count")
                .sort_values("date_only")
            )
            daily_commits["date_str"] = daily_commits["date_only"].astype(str)

            fig_cadence = px.bar(
                daily_commits,
                x="date_str",
                y="commit_count",
                labels={"date_str": "Date", "commit_count": "Commits"},
                color_discrete_sequence=["#A3E635"],
            )
            fig_cadence.update_traces(
                marker_line_width=0,
                hovertemplate="<b>Date:</b> %{x}<br><b>Commits:</b> %{y}<extra></extra>",
            )
            # Avoid oversized bars when few dates exist
            if len(daily_commits) <= 3:
                fig_cadence.update_layout(bargap=0.65)
            style_plot(fig_cadence, "Daily Commit Velocity", height=320)
            st.plotly_chart(fig_cadence, use_container_width=True)
        else:
            st.info("No commit activity available.")

    with col_act_right:
        st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-bottom: 0.5rem;'>AUTHOR COMMIT SUMMARY</div>", unsafe_allow_html=True)
        if author_counts:
            df_top_authors = (
                pd.DataFrame(list(author_counts.items()), columns=["Author", "Commits"])
                .sort_values(by="Commits", ascending=True)
                .tail(10)
            )
            fig_authors_bar = px.bar(
                df_top_authors,
                x="Commits",
                y="Author",
                orientation="h",
                color="Commits",
                color_continuous_scale=[[0, "#1F2937"], [1, "#A3E635"]],
            )
            fig_authors_bar.update_layout(coloraxis_showscale=False)
            if len(df_top_authors) <= 3:
                fig_authors_bar.update_layout(bargap=0.6)
            fig_authors_bar.update_traces(
                hovertemplate="<b>%{y}</b><br>Commits: %{x}<extra></extra>"
            )
            style_plot(fig_authors_bar, "Top Authors by Commit Volume", height=320)
            st.plotly_chart(fig_authors_bar, use_container_width=True)

    # Cumulative Growth Telemetry
    st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-top: 0.6rem; margin-bottom: 0.4rem;'>CUMULATIVE CODEBASE VELOCITY</div>", unsafe_allow_html=True)
    if len(df_commits) > 1:
        df_chrono = df_commits.sort_values("datetime").copy()
        df_chrono["cumulative_commits"] = range(1, len(df_chrono) + 1)
        df_chrono["cumulative_churn"] = df_chrono["churn"].cumsum()

        fig_cum = go.Figure()
        fig_cum.add_trace(
            go.Scatter(
                x=df_chrono["datetime"],
                y=df_chrono["cumulative_commits"],
                name="Cumulative Commits",
                mode="lines+markers",
                line=dict(color="#A3E635", width=2.5),
                marker=dict(size=5, color="#A3E635"),
                hovertemplate="<b>Commits:</b> %{y}<br><b>Timestamp:</b> %{x|%Y-%m-%d %H:%M}<extra></extra>",
            )
        )
        style_plot(fig_cum, "Cumulative Commits Trajectory", height=280)
        st.plotly_chart(fig_cum, use_container_width=True)
    else:
        st.caption("ℹ️ Trajectory curve requires at least 2 commits to plot velocity trends.")


# -----------------------------------------------------------------------------
# Tab 2: Contributors // Share
# -----------------------------------------------------------------------------
with tab_authors:
    col_c1, col_c2 = st.columns([1, 1.2])

    with col_c1:
        st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-bottom: 0.5rem;'>COMMIT CONTRIBUTION BREAKDOWN</div>", unsafe_allow_html=True)
        df_authors_all = pd.DataFrame(
            list(author_counts.items()), columns=["Author", "Commits"]
        ).sort_values(by="Commits", ascending=False)
        df_authors_all["Share (%)"] = ((df_authors_all["Commits"] / total_c) * 100).round(1)

        # Developer palette for pie/donut
        color_palette = ["#A3E635", "#38BDF8", "#818CF8", "#FBBF24", "#F472B6", "#9CA3AF"]

        fig_donut = px.pie(
            df_authors_all,
            names="Author",
            values="Commits",
            hole=0.55,
            color_discrete_sequence=color_palette,
        )
        fig_donut.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Commits: %{value} (%{percent})<extra></extra>",
        )
        style_plot(fig_donut, "Author Commit Share", height=340)
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_c2:
        st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-bottom: 0.5rem;'>CONTRIBUTOR LEADERBOARD</div>", unsafe_allow_html=True)
        st.dataframe(
            df_authors_all.style.format({"Share (%)": "{:.1f}%"}),
            use_container_width=True,
            hide_index=True,
            height=340,
        )

    # Per-author lines added vs deleted
    if not df_commits.empty:
        st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-top: 0.8rem; margin-bottom: 0.4rem;'>CODE VOLUME MODIFIED BY CONTRIBUTOR</div>", unsafe_allow_html=True)
        author_churn = (
            df_commits.groupby("author")[["lines_added", "lines_deleted", "churn"]]
            .sum()
            .reset_index()
            .sort_values(by="churn", ascending=False)
        )

        author_churn["added_label"] = author_churn["lines_added"].apply(format_additions)
        author_churn["deleted_label"] = author_churn["lines_deleted"].apply(format_deletions)

        fig_auth_churn = go.Figure()
        fig_auth_churn.add_trace(
            go.Bar(
                name="Lines Added (+)",
                x=author_churn["author"],
                y=author_churn["lines_added"],
                marker_color="#A3E635",
                customdata=author_churn["added_label"],
                hovertemplate="<b>%{x}</b><br>Added: %{customdata}<extra></extra>",
            )
        )
        fig_auth_churn.add_trace(
            go.Bar(
                name="Lines Deleted (-)",
                x=author_churn["author"],
                y=author_churn["lines_deleted"],
                marker_color="#F87171",
                customdata=author_churn["deleted_label"],
                hovertemplate="<b>%{x}</b><br>Deleted: %{customdata}<extra></extra>",
            )
        )
        fig_auth_churn.update_layout(barmode="group")
        if len(author_churn) <= 3:
            fig_auth_churn.update_layout(bargap=0.6)
        style_plot(fig_auth_churn, "Code Additions vs Deletions by Contributor", height=320)
        st.plotly_chart(fig_auth_churn, use_container_width=True)


# -----------------------------------------------------------------------------
# Tab 3: Hotspots // Files
# -----------------------------------------------------------------------------
with tab_hotspots:
    st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-bottom: 0.5rem;'>FREQUENTLY MODIFIED CODE FILES</div>", unsafe_allow_html=True)

    if file_freq:
        df_files = pd.DataFrame(
            list(file_freq.items()), columns=["File Path", "Commits Touched"]
        ).sort_values(by="Commits Touched", ascending=False)

        top_files = df_files.head(top_n_hotspots)

        view_mode = st.radio(
            "Visualization Mode:",
            options=["Treemap Footprint", "Ranked Hotspot Bars"],
            horizontal=True,
        )

        if view_mode == "Treemap Footprint":
            fig_treemap = px.treemap(
                top_files,
                path=["File Path"],
                values="Commits Touched",
                color="Commits Touched",
                color_continuous_scale=[[0, "#1E293B"], [0.5, "#0D9488"], [1, "#A3E635"]],
            )
            fig_treemap.update_layout(coloraxis_showscale=True)
            fig_treemap.update_traces(
                hovertemplate="<b>%{label}</b><br>Modified in %{value} commits<extra></extra>"
            )
            style_plot(fig_treemap, f"Hotspot Treemap (Top {len(top_files)} Files)", height=380)
            st.plotly_chart(fig_treemap, use_container_width=True)
        else:
            fig_hotspots = px.bar(
                top_files.sort_values("Commits Touched", ascending=True),
                x="Commits Touched",
                y="File Path",
                orientation="h",
                color="Commits Touched",
                color_continuous_scale=[[0, "#1E293B"], [1, "#A3E635"]],
                labels={"Commits Touched": "Commits", "File Path": "Path"},
            )
            fig_hotspots.update_layout(coloraxis_showscale=False)
            if len(top_files) <= 3:
                fig_hotspots.update_layout(bargap=0.55)
            fig_hotspots.update_traces(
                hovertemplate="<b>%{y}</b><br>Commits: %{x}<extra></extra>"
            )
            style_plot(
                fig_hotspots,
                f"Ranked File Hotspots (Top {len(top_files)})",
                height=max(360, len(top_files) * 26),
            )
            st.plotly_chart(fig_hotspots, use_container_width=True)

        st.markdown("<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 1.2rem 0;'>", unsafe_allow_html=True)
        
        # Interactive Hotspot Inspector
        st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-bottom: 0.4rem;'>INSPECT HOTSPOT FILE FREQUENCY</div>", unsafe_allow_html=True)
        hotspot_file_list = sorted(list(file_freq.keys()))
        selected_hotspot = st.selectbox(
            "SELECT FILE TO INSPECT",
            options=hotspot_file_list,
            help="Select any modified file to inspect its exact commit touch count.",
        )
        if selected_hotspot:
            touch_count = file_freq[selected_hotspot]
            touch_pct = (touch_count / total_c) * 100 if total_c > 0 else 0
            st.markdown(
                f"""
                <div style="background: #11161F; border: 1px solid var(--border-subtle); border-radius: 6px; padding: 0.85rem 1.1rem; font-family: var(--font-mono); font-size: 0.84rem; margin-bottom: 1.2rem;">
                    <div><span style="color: var(--text-muted);">FILE:</span> <code>{selected_hotspot}</code></div>
                    <div style="margin-top: 0.35rem;"><span style="color: var(--text-muted);">COMMITS TOUCHED:</span> <span style="color: var(--accent-lime); font-weight: 700;">{touch_count}</span> of {total_c} commits ({touch_pct:.1f}% frequency)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Searchable full file inventory
        st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-bottom: 0.4rem;'>TOUCHED FILES REPOSITORY INVENTORY</div>", unsafe_allow_html=True)
        file_search = st.text_input("FILTER FILE PATH", "", placeholder="e.g. scanner.py or .github")
        filtered_files = df_files
        if file_search:
            filtered_files = df_files[
                df_files["File Path"].str.contains(file_search, case=False, na=False)
            ]

        st.dataframe(
            filtered_files,
            use_container_width=True,
            hide_index=True,
            height=280,
        )
    else:
        st.info("No file modifications recorded.")


# -----------------------------------------------------------------------------
# Tab 4: Churn // Dynamics
# -----------------------------------------------------------------------------
with tab_churn:
    st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-bottom: 0.5rem;'>LINE CHURN DYNAMICS PER COMMIT</div>", unsafe_allow_html=True)

    if not df_commits.empty:
        df_commits_sorted = df_commits.sort_values("datetime").copy()
        df_commits_sorted["added_str"] = df_commits_sorted["lines_added"].apply(format_additions)
        df_commits_sorted["deleted_str"] = df_commits_sorted["lines_deleted"].apply(format_deletions)

        custom_hover_added = list(zip(df_commits_sorted["message"], df_commits_sorted["added_str"]))
        custom_hover_deleted = list(zip(df_commits_sorted["message"], df_commits_sorted["deleted_str"]))

        fig_diverging = go.Figure()
        fig_diverging.add_trace(
            go.Bar(
                x=df_commits_sorted["short_hash"],
                y=df_commits_sorted["lines_added"],
                name="Additions (+)",
                marker_color="#A3E635",
                customdata=custom_hover_added,
                hovertemplate="<b>Commit %{x}</b><br>Added: %{customdata[1]}<br>%{customdata[0]}<extra></extra>",
            )
        )
        fig_diverging.add_trace(
            go.Bar(
                x=df_commits_sorted["short_hash"],
                y=-df_commits_sorted["lines_deleted"],
                name="Deletions (-)",
                marker_color="#F87171",
                customdata=custom_hover_deleted,
                hovertemplate="<b>Commit %{x}</b><br>Deleted: %{customdata[1]}<br>%{customdata[0]}<extra></extra>",
            )
        )
        fig_diverging.update_layout(
            barmode="relative",
            xaxis_title="Commit Hash",
            yaxis_title="Lines Delta",
        )
        if len(df_commits_sorted) <= 3:
            fig_diverging.update_layout(bargap=0.65)
        style_plot(fig_diverging, "Diverging Code Additions (+) vs Deletions (-) per Commit", height=340)
        st.plotly_chart(fig_diverging, use_container_width=True)

        # Churn scale scatter
        st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-top: 0.8rem; margin-bottom: 0.4rem;'>COMMIT MAGNITUDE DISTRIBUTION</div>", unsafe_allow_html=True)
        if len(df_commits) == 1:
            st.caption("ℹ️ Commit magnitude scatter currently displays a single commit anchor point.")

        fig_scatter = px.scatter(
            df_commits,
            x="lines_added",
            y="lines_deleted",
            size="churn",
            color="author",
            hover_name="short_hash",
            hover_data=["author", "formatted_date", "message"],
            labels={"lines_added": "Lines Added", "lines_deleted": "Lines Deleted"},
            color_discrete_sequence=["#A3E635", "#38BDF8", "#818CF8", "#FBBF24", "#F472B6"],
        )
        style_plot(fig_scatter, "Commit Impact Scale (Additions vs Deletions)", height=320)
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("No churn telemetry available.")


# -----------------------------------------------------------------------------
# Tab 5: Commits // Explorer
# -----------------------------------------------------------------------------
with tab_commits:
    st.markdown("<div style='font-family: JetBrains Mono; font-size: 0.8rem; color: #8B949E; margin-bottom: 0.5rem;'>GIT COMMIT LOG TELEMETRY</div>", unsafe_allow_html=True)

    if not df_commits.empty:
        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            all_auth = sorted(list(author_counts.keys()))
            selected_auth = st.multiselect(
                "FILTER AUTHOR",
                options=all_auth,
                default=all_auth,
            )
        with col_f2:
            commit_query = st.text_input("SEARCH MESSAGES / HASHES", "", placeholder="Search query...")

        filtered_commits = df_commits[df_commits["author"].isin(selected_auth)]
        if commit_query:
            filtered_commits = filtered_commits[
                filtered_commits["message"].str.contains(commit_query, case=False, na=False)
                | filtered_commits["hash"].str.contains(commit_query, case=False, na=False)
            ]

        cols_display = [
            "short_hash",
            "author",
            "formatted_date",
            "message",
            "lines_added",
            "lines_deleted",
            "churn",
        ]
        rename_map = {
            "short_hash": "HASH",
            "author": "AUTHOR",
            "formatted_date": "TIMESTAMP",
            "message": "MESSAGE",
            "lines_added": "+ ADDED",
            "lines_deleted": "- DELETED",
            "churn": "CHURN",
        }

        st.dataframe(
            filtered_commits[cols_display].rename(columns=rename_map),
            use_container_width=True,
            hide_index=True,
            height=340,
        )

        st.caption(f"Displaying **{len(filtered_commits)}** of **{len(df_commits)}** commits.")

        # Export Telemetry
        csv_payload = filtered_commits[
            ["hash", "author", "date", "message", "lines_added", "lines_deleted", "churn"]
        ].to_csv(index=False)

        st.download_button(
            label="DOWNLOAD TELEMETRY CSV",
            data=csv_payload,
            file_name=f"commitlens_{repo_folder_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

        # Inspector Expander
        with st.expander("INSPECT COMMIT TELEMETRY"):
            commit_hashes = filtered_commits["hash"].tolist()
            if commit_hashes:
                selected_hash = st.selectbox(
                    "Select commit to inspect",
                    options=commit_hashes,
                    format_func=lambda h: f"{h[:7]} - {filtered_commits.loc[filtered_commits['hash'] == h, 'message'].values[0][:60]}",
                )
                commit_spec = filtered_commits[filtered_commits["hash"] == selected_hash].iloc[0]

                i_col1, i_col2 = st.columns([1.2, 0.8])
                with i_col1:
                    st.markdown(f"**HASH:** `{commit_spec['hash']}`")
                    st.markdown(f"**AUTHOR:** `{commit_spec['author']}`")
                    st.markdown(f"**TIMESTAMP:** `{commit_spec['formatted_date']}`")
                with i_col2:
                    st.markdown(f"**LINES ADDED:** `{format_additions(commit_spec['lines_added'])}`")
                    st.markdown(f"**LINES DELETED:** `{format_deletions(commit_spec['lines_deleted'])}`")
                    st.markdown(f"**TOTAL CHURN:** `{commit_spec['churn']:,}`")

                st.markdown("**COMMIT MESSAGE:**")
                st.code(commit_spec["message"], language="text")
    else:
        st.info("No commits found.")
