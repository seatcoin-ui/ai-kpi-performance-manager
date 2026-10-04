
import os
import json
import re
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="AI KPI Performance Manager",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- STYLE ----------
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {
    background: white;
    border: 1px solid #E6EAF0;
    padding: 14px;
    border-radius: 12px;
    box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
.kpi-title {font-size: 2.0rem; font-weight: 800; margin-bottom: .1rem;}
.kpi-subtitle {color:#667085; margin-bottom: 1.1rem;}
.rag-green {background:#DCFCE7; color:#166534; padding:5px 9px; border-radius:999px; font-weight:700;}
.rag-amber {background:#FEF3C7; color:#92400E; padding:5px 9px; border-radius:999px; font-weight:700;}
.rag-red {background:#FEE2E2; color:#991B1B; padding:5px 9px; border-radius:999px; font-weight:700;}
</style>
""", unsafe_allow_html=True)

DEFAULT_TARGETS = {
    "Productivity_Green_pct": 100.0, "Productivity_Amber_pct": 95.0,
    "RTR_Green_pct": 100.0, "RTR_Amber_pct": 95.0,
    "Quality_Green_pct": 99.5, "Quality_Amber_pct": 99.0,
    "OTD_Green_pct": 98.0, "OTD_Amber_pct": 95.0,
    "Forecast_Green_pct": 95.0, "Forecast_Amber_pct": 90.0,
    "Cost_Green_pct": 100.0, "Cost_Amber_pct": 95.0,
}

CORE_COLUMNS = ["Week", "Company", "Volume", "Actual_Hours", "Target_Rate"]
OPTIONAL_COLUMNS = [
    "Forecast_Volume","Budget_Hours","Errors","OTD_pct",
    "Cost_Actual","Cost_Budget","Safety_Incidents"
]

ALIASES = {
    "week": "Week", "wk": "Week",
    "company": "Company", "customer": "Company", "client": "Company", "account": "Company",
    "volume": "Volume", "actual_volume": "Volume", "output": "Volume", "lines": "Volume",
    "forecast": "Forecast_Volume", "forecast_volume": "Forecast_Volume", "planned_volume": "Forecast_Volume",
    "actual_hours": "Actual_Hours", "clocked_hours": "Actual_Hours", "hours": "Actual_Hours",
    "budget_hours": "Budget_Hours", "planned_hours": "Budget_Hours", "rtr_hours": "Budget_Hours", "norm_hours": "Budget_Hours",
    "target_rate": "Target_Rate", "target": "Target_Rate", "rate_target": "Target_Rate",
    "errors": "Errors", "error": "Errors", "picking_errors": "Errors",
    "otd_pct": "OTD_pct", "otd": "OTD_pct", "on_time_delivery": "OTD_pct",
    "cost_actual": "Cost_Actual", "actual_cost": "Cost_Actual",
    "cost_budget": "Cost_Budget", "budget_cost": "Cost_Budget",
    "safety_incidents": "Safety_Incidents", "incidents": "Safety_Incidents",
}

def normalize_name(name):
    s = str(name).strip().lower()
    s = re.sub(r"[%()]+", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s

def auto_rename(df):
    ren = {}
    for c in df.columns:
        n = normalize_name(c)
        if n in ALIASES:
            ren[c] = ALIASES[n]
    return df.rename(columns=ren)

def read_upload(uploaded):
    targets_df = None
    errors_df = None
    if uploaded.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        xls = pd.ExcelFile(uploaded)
        data_sheet = "Data" if "Data" in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=data_sheet)
        if "Targets" in xls.sheet_names:
            targets_df = pd.read_excel(xls, sheet_name="Targets")
        if "Errors" in xls.sheet_names:
            errors_df = pd.read_excel(xls, sheet_name="Errors")
    return auto_rename(df), targets_df, errors_df

def defaults_for_missing(df):
    out = df.copy()
    defaults = {
        "Forecast_Volume": np.nan,
        "Budget_Hours": np.nan,
        "Errors": 0,
        "OTD_pct": np.nan,
        "Cost_Actual": np.nan,
        "Cost_Budget": np.nan,
        "Safety_Incidents": 0,
    }
    for c, v in defaults.items():
        if c not in out.columns:
            out[c] = v
    return out

def clean_numeric(df):
    out = df.copy()
    for c in ["Week","Volume","Forecast_Volume","Actual_Hours","Budget_Hours","Target_Rate",
              "Errors","OTD_pct","Cost_Actual","Cost_Budget","Safety_Incidents"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["Week","Company","Volume","Actual_Hours","Target_Rate"])
    out["Week"] = out["Week"].astype(int)
    return out

def get_company_targets(company, targets_df):
    t = DEFAULT_TARGETS.copy()
    if targets_df is not None and not targets_df.empty and "Company" in targets_df.columns:
        hit = targets_df[targets_df["Company"].astype(str).str.strip() == str(company).strip()]
        if not hit.empty:
            row = hit.iloc[0]
            for k in DEFAULT_TARGETS:
                if k in hit.columns and pd.notna(row[k]):
                    t[k] = float(row[k])
    return t

def rag(value, green, amber, higher_is_better=True, na_label="N/A"):
    if pd.isna(value):
        return na_label
    if higher_is_better:
        if value >= green: return "GREEN"
        if value >= amber: return "AMBER"
        return "RED"
    else:
        if value <= green: return "GREEN"
        if value <= amber: return "AMBER"
        return "RED"

def compute_kpis(df, targets_df=None):
    out = df.copy()

    out["Productivity"] = out["Volume"] / out["Actual_Hours"].replace(0, np.nan)
    out["Productivity_pct"] = out["Productivity"] / out["Target_Rate"].replace(0, np.nan) * 100

    out["RTR_pct"] = out["Budget_Hours"] / out["Actual_Hours"].replace(0, np.nan) * 100
    out["Hours_Variance"] = out["Actual_Hours"] - out["Budget_Hours"]

    out["Quality_pct"] = (1 - out["Errors"] / out["Volume"].replace(0, np.nan)) * 100
    out["OTD_pct"] = out["OTD_pct"].clip(lower=0, upper=100)

    out["Forecast_Accuracy_pct"] = (
        100 - (out["Volume"] - out["Forecast_Volume"]).abs()
        / out["Forecast_Volume"].replace(0, np.nan) * 100
    ).clip(lower=0, upper=100)
    out["Volume_Variance"] = out["Volume"] - out["Forecast_Volume"]

    out["Cost_pct"] = out["Cost_Budget"] / out["Cost_Actual"].replace(0, np.nan) * 100
    out["Cost_Variance"] = out["Cost_Actual"] - out["Cost_Budget"]

    statuses = []
    overall_scores = []

    for idx, row in out.iterrows():
        t = get_company_targets(row["Company"], targets_df)

        p_s = rag(row["Productivity_pct"], t["Productivity_Green_pct"], t["Productivity_Amber_pct"])
        r_s = rag(row["RTR_pct"], t["RTR_Green_pct"], t["RTR_Amber_pct"])
        q_s = rag(row["Quality_pct"], t["Quality_Green_pct"], t["Quality_Amber_pct"])
        o_s = rag(row["OTD_pct"], t["OTD_Green_pct"], t["OTD_Amber_pct"])
        f_s = rag(row["Forecast_Accuracy_pct"], t["Forecast_Green_pct"], t["Forecast_Amber_pct"])
        c_s = rag(row["Cost_pct"], t["Cost_Green_pct"], t["Cost_Amber_pct"])
        s_s = rag(row["Safety_Incidents"], 0, 1, higher_is_better=False)

        out.at[idx, "Productivity_Status"] = p_s
        out.at[idx, "RTR_Status"] = r_s
        out.at[idx, "Quality_Status"] = q_s
        out.at[idx, "OTD_Status"] = o_s
        out.at[idx, "Forecast_Status"] = f_s
        out.at[idx, "Cost_Status"] = c_s
        out.at[idx, "Safety_Status"] = s_s

        candidates = [
            ("Productivity_pct", .24),
            ("RTR_pct", .18),
            ("Quality_pct", .16),
            ("OTD_pct", .16),
            ("Forecast_Accuracy_pct", .10),
            ("Cost_pct", .11),
        ]
        numerator = 0.0
        denom = 0.0
        for col, weight in candidates:
            value = row[col]
            if pd.notna(value):
                numerator += min(max(float(value), 0), 120) * weight
                denom += weight
        base = numerator / denom if denom else np.nan
        safety = 100 if row["Safety_Incidents"] == 0 else (85 if row["Safety_Incidents"] == 1 else 60)

        if pd.notna(base):
            overall = base * .92 + safety * .08
        else:
            overall = safety
        overall_scores.append(overall)
        statuses.append(rag(overall, 98, 93))

    out["Overall_Score"] = overall_scores
    out["Overall_Status"] = statuses
    return out

def status_icon(s):
    return {"GREEN":"🟢", "AMBER":"🟠", "RED":"🔴", "N/A":"⚪"}.get(s, "⚪")

def management_analysis(row):
    issues = []
    actions = []

    checks = [
        ("Productivity_pct","Productivity_Status","Productivity"),
        ("RTR_pct","RTR_Status","RTR / Efficiency"),
        ("Quality_pct","Quality_Status","Quality"),
        ("OTD_pct","OTD_Status","On-time delivery"),
        ("Forecast_Accuracy_pct","Forecast_Status","Forecast accuracy"),
        ("Cost_pct","Cost_Status","Cost performance"),
    ]

    for value_col, status_col, label in checks:
        if status_col in row and row[status_col] == "RED" and pd.notna(row[value_col]):
            issues.append(f"{label} is RED at {row[value_col]:.1f}%.")
        elif status_col in row and row[status_col] == "AMBER" and pd.notna(row[value_col]):
            issues.append(f"{label} is AMBER at {row[value_col]:.1f}%.")

    if row["Productivity_Status"] != "GREEN":
        actions.append("Review staffing versus volume and identify the activities causing excess clocked hours.")
    if row["RTR_Status"] != "GREEN" and pd.notna(row["RTR_pct"]):
        actions.append("Break the hours variance down by activity, shift and employee group; confirm the operational norm hours.")
    if row["Quality_Status"] != "GREEN":
        actions.append("Run a Pareto of error categories and complete RCA on the largest contributor.")
    if row["OTD_Status"] != "GREEN":
        actions.append("Review late orders by planning, picking, loading and carrier cause.")
    if row["Forecast_Status"] != "GREEN" and pd.notna(row["Forecast_Accuracy_pct"]):
        actions.append("Align forecast and staffing planning; review recurring forecast bias by week.")
    if row["Cost_Status"] != "GREEN" and pd.notna(row["Cost_pct"]):
        actions.append("Split cost variance into labor, overtime, transport and consumables.")
    if row["Safety_Incidents"] > 0:
        actions.append("Verify incident RCA and closure of corrective actions before the next performance review.")

    if not issues:
        issues = ["Primary KPI performance is on target for the selected period."]
    if not actions:
        actions = ["Maintain the current controls and focus on sustaining the result."]

    return " ".join(issues), actions[:3]

def ai_management_analysis(row, extra_context=""):
    api_key = None
    model = None

    try:
        if "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"]
        if "OPENAI_MODEL" in st.secrets:
            model = st.secrets["OPENAI_MODEL"]
    except Exception:
        pass

    api_key = api_key or os.getenv("OPENAI_API_KEY")
    model = model or os.getenv("OPENAI_MODEL") or "gpt-6-astra"

    if not api_key:
        summary, actions = management_analysis(row)
        return summary, actions, "Rule-based analysis"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        fields = [
            "Company","Week","Overall_Score","Productivity_pct","RTR_pct","Quality_pct",
            "OTD_pct","Forecast_Accuracy_pct","Cost_pct","Safety_Incidents",
            "Hours_Variance","Volume_Variance","Cost_Variance"
        ]
        payload = {}
        for f in fields:
            v = row.get(f, None)
            if pd.isna(v) if not isinstance(v, str) else False:
                v = None
            elif isinstance(v, (np.integer, np.floating)):
                v = v.item()
            payload[f] = v

        prompt = f"""
You are a senior operations performance manager for logistics and warehouse operations.
Analyze this KPI record and produce a management-ready review.

DATA:
{json.dumps(payload, default=str)}

EXTRA CONTEXT:
{extra_context}

Rules:
- Do not invent facts not present in the data.
- Prioritize the largest performance gaps.
- Distinguish facts from likely causes.
- Make actions specific and measurable.
- Maximum 120 words.

Return exactly:
SUMMARY: <short management summary>
ACTIONS:
1. <action>
2. <action>
3. <action>
"""
        response = client.responses.create(model=model, input=prompt)
        text = response.output_text.strip()

        summary = text
        actions = []
        if "ACTIONS:" in text:
            summary_part, action_part = text.split("ACTIONS:", 1)
            summary = summary_part.replace("SUMMARY:", "").strip()
            for line in action_part.splitlines():
                line = line.strip()
                if re.match(r"^[1-3]\.", line):
                    actions.append(re.sub(r"^[1-3]\.\s*", "", line))

        if not actions:
            _, actions = management_analysis(row)
        return summary, actions[:3], f"AI analysis — {model}"
    except Exception as e:
        summary, actions = management_analysis(row)
        return summary, actions, "AI unavailable — rule-based fallback"

def display_status_table(df):
    cols = [
        "Company","Week","Productivity_pct","RTR_pct","Quality_pct","OTD_pct",
        "Forecast_Accuracy_pct","Cost_pct","Safety_Incidents","Overall_Score","Overall_Status"
    ]
    view = df[cols].copy()
    view["Status"] = view["Overall_Status"].map(lambda x: f"{status_icon(x)} {x}")
    view = view.drop(columns=["Overall_Status"])
    view.columns = [
        "Company","Week","Productivity %","RTR %","Quality %","OTD %",
        "Forecast accuracy %","Cost %","Safety incidents","Overall score","Status"
    ]

    def color_status(val):
        s = str(val)
        if "GREEN" in s: return "background-color:#DCFCE7;color:#166534;font-weight:700"
        if "AMBER" in s: return "background-color:#FEF3C7;color:#92400E;font-weight:700"
        if "RED" in s: return "background-color:#FEE2E2;color:#991B1B;font-weight:700"
        return ""

    styler = (
        view.style
        .format({
            "Productivity %":"{:.1f}", "RTR %":"{:.1f}", "Quality %":"{:.2f}",
            "OTD %":"{:.1f}", "Forecast accuracy %":"{:.1f}",
            "Cost %":"{:.1f}", "Overall score":"{:.1f}"
        }, na_rep="-")
        .map(color_status, subset=["Status"])
    )
    st.dataframe(styler, use_container_width=True, hide_index=True)

# ---------- HEADER ----------
st.markdown('<div class="kpi-title">AI KPI Performance Manager</div>', unsafe_allow_html=True)
st.markdown('<div class="kpi-subtitle">Version 2 — Professional Logistics & Warehouse Performance Dashboard</div>', unsafe_allow_html=True)

# ---------- SIDEBAR / LOAD ----------
with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Upload Excel or CSV", type=["xlsx","xls","csv"])
    st.caption("Best option: use the Excel template with Data, Targets and Errors sheets.")

    st.divider()
    st.header("Filters")

if uploaded:
    raw, targets_df, errors_df = read_upload(uploaded)
    data_source = uploaded.name
else:
    raw = pd.read_excel("AI_KPI_Data_Template_v2.xlsx", sheet_name="Data")
    targets_df = pd.read_excel("AI_KPI_Data_Template_v2.xlsx", sheet_name="Targets")
    errors_df = pd.read_excel("AI_KPI_Data_Template_v2.xlsx", sheet_name="Errors")
    data_source = "Demo / template data"
    st.info("Demo data is loaded. Upload your own Excel or CSV from the sidebar.")

raw = defaults_for_missing(raw)
missing = [c for c in CORE_COLUMNS if c not in raw.columns]
if missing:
    st.error("Missing required columns: " + ", ".join(missing))
    st.stop()

df = clean_numeric(raw)
kpi = compute_kpis(df, targets_df)

all_weeks = sorted(kpi["Week"].unique(), reverse=True)
all_companies = sorted(kpi["Company"].astype(str).unique())

with st.sidebar:
    selected_week = st.selectbox("Week", all_weeks, index=0)
    selected_companies = st.multiselect("Companies", all_companies, default=all_companies)
    st.caption(f"Source: {data_source}")

filtered = kpi[(kpi["Week"] == selected_week) & (kpi["Company"].astype(str).isin(selected_companies))].copy()
if filtered.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# ---------- KPI CARDS ----------
avg_overall = filtered["Overall_Score"].mean()
red_count = (filtered["Overall_Status"] == "RED").sum()
amber_count = (filtered["Overall_Status"] == "AMBER").sum()
total_volume = filtered["Volume"].sum()
total_hours = filtered["Actual_Hours"].sum()
weighted_productivity = total_volume / total_hours if total_hours else np.nan

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Week", selected_week)
c2.metric("Companies", filtered["Company"].nunique())
c3.metric("Total volume", f"{total_volume:,.0f}")
c4.metric("Actual hours", f"{total_hours:,.1f}")
c5.metric("Avg overall", f"{avg_overall:.1f}%")
c6.metric("Red / Amber", f"{red_count} / {amber_count}")

tabs = st.tabs(["Executive Dashboard","Company Detail","Pareto","AI Review","Data"])

with tabs[0]:
    st.subheader("Company Performance")
    display_status_table(filtered.sort_values("Overall_Score", ascending=False))

    st.subheader("Performance Overview")
    chart_data = filtered.set_index("Company")[[
        "Productivity_pct","RTR_pct","Quality_pct","OTD_pct","Forecast_Accuracy_pct","Cost_pct"
    ]]
    st.bar_chart(chart_data)

    left, right = st.columns(2)
    with left:
        st.subheader("Volume: Forecast vs Actual")
        vol = filtered.set_index("Company")[["Forecast_Volume","Volume"]].rename(
            columns={"Forecast_Volume":"Forecast","Volume":"Actual"}
        )
        st.bar_chart(vol)

    with right:
        st.subheader("Hours: Budget vs Actual")
        hrs = filtered.set_index("Company")[["Budget_Hours","Actual_Hours"]].rename(
            columns={"Budget_Hours":"Budget hours","Actual_Hours":"Actual hours"}
        )
        st.bar_chart(hrs)

with tabs[1]:
    company = st.selectbox("Select company", all_companies, key="detail_company")
    history = kpi[kpi["Company"].astype(str) == company].sort_values("Week")
    latest = history[history["Week"] == selected_week]
    if latest.empty:
        st.info(f"No data for {company} in week {selected_week}. Showing latest available week.")
        row = history.iloc[-1]
    else:
        row = latest.iloc[0]

    st.markdown(f"### {company} — Week {int(row['Week'])}")
    d1,d2,d3,d4,d5,d6 = st.columns(6)
    d1.metric("Overall", f"{row['Overall_Score']:.1f}%", row["Overall_Status"])
    d2.metric("Productivity", f"{row['Productivity_pct']:.1f}%", row["Productivity_Status"])
    d3.metric("RTR", "-" if pd.isna(row["RTR_pct"]) else f"{row['RTR_pct']:.1f}%", row["RTR_Status"])
    d4.metric("Quality", f"{row['Quality_pct']:.2f}%", row["Quality_Status"])
    d5.metric("OTD", "-" if pd.isna(row["OTD_pct"]) else f"{row['OTD_pct']:.1f}%", row["OTD_Status"])
    d6.metric("Cost", "-" if pd.isna(row["Cost_pct"]) else f"{row['Cost_pct']:.1f}%", row["Cost_Status"])

    st.subheader("Weekly Trend")
    trend_cols = ["Productivity_pct","RTR_pct","Quality_pct","OTD_pct","Forecast_Accuracy_pct","Cost_pct","Overall_Score"]
    st.line_chart(history.set_index("Week")[trend_cols])

    v1,v2,v3 = st.columns(3)
    v1.metric("Volume variance", "-" if pd.isna(row["Volume_Variance"]) else f"{row['Volume_Variance']:,.0f}")
    v2.metric("Hours variance", "-" if pd.isna(row["Hours_Variance"]) else f"{row['Hours_Variance']:,.1f} h")
    v3.metric("Cost variance", "-" if pd.isna(row["Cost_Variance"]) else f"€{row['Cost_Variance']:,.0f}")

with tabs[2]:
    st.subheader("Error Pareto")
    if errors_df is None or errors_df.empty:
        st.info("Add an 'Errors' sheet to your Excel file with Week, Company, Error_Category and Errors.")
    else:
        e = errors_df.copy()
        e["Week"] = pd.to_numeric(e["Week"], errors="coerce")
        e["Errors"] = pd.to_numeric(e["Errors"], errors="coerce").fillna(0)
        e = e[
            (e["Week"] == selected_week)
            & (e["Company"].astype(str).isin(selected_companies))
        ]
        if e.empty:
            st.info("No Pareto error data for the selected week/companies.")
        else:
            pareto = e.groupby("Error_Category", as_index=False)["Errors"].sum().sort_values("Errors", ascending=False)
            pareto["Cumulative %"] = pareto["Errors"].cumsum() / pareto["Errors"].sum() * 100
            p1,p2 = st.columns([1.5,1])
            with p1:
                st.bar_chart(pareto.set_index("Error_Category")["Errors"])
            with p2:
                st.dataframe(
                    pareto.style.format({"Errors":"{:.0f}","Cumulative %":"{:.1f}%"}),
                    hide_index=True,
                    use_container_width=True
                )

with tabs[3]:
    company_ai = st.selectbox("Company for management review", all_companies, key="ai_company")
    ai_rows = kpi[(kpi["Company"].astype(str) == company_ai) & (kpi["Week"] == selected_week)]
    if ai_rows.empty:
        st.info("No KPI record for this company in the selected week.")
    else:
        row = ai_rows.iloc[0]
        extra = st.text_area(
            "Optional manager context",
            placeholder="Example: high absenteeism, urgent customer order, system downtime..."
        )

        summary, actions, mode = ai_management_analysis(row, extra)
        st.markdown(f"### {company_ai} — Management Review")
        st.write(summary)
        st.markdown("**Top 3 actions**")
        for i,a in enumerate(actions, 1):
            st.write(f"{i}. {a}")
        st.caption(mode)

with tabs[4]:
    st.subheader("Calculated KPI Data")
    st.dataframe(kpi, use_container_width=True, hide_index=True)

    csv = kpi.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download calculated KPI results (CSV)",
        data=csv,
        file_name=f"kpi_results_week_{selected_week}.csv",
        mime="text/csv"
    )
