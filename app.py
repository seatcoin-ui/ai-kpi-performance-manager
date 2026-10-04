
import os
import json
import pandas as pd
import streamlit as st

st.set_page_config(page_title="AI KPI Performance Manager", layout="wide")

REQUIRED_COLUMNS = [
    "Week", "Company", "Volume", "Actual_Hours", "Target_Rate",
    "Errors", "OTD_pct", "Cost_Actual", "Cost_Budget", "Safety_Incidents"
]

def rag(value, green, amber, higher_is_better=True):
    if higher_is_better:
        if value >= green:
            return "GREEN"
        if value >= amber:
            return "AMBER"
        return "RED"
    else:
        if value <= green:
            return "GREEN"
        if value <= amber:
            return "AMBER"
        return "RED"

def calculate_kpis(df):
    out = df.copy()
    out["Productivity"] = out["Volume"] / out["Actual_Hours"].replace(0, pd.NA)
    out["Productivity_pct"] = (out["Productivity"] / out["Target_Rate"].replace(0, pd.NA)) * 100
    out["Quality_pct"] = (1 - (out["Errors"] / out["Volume"].replace(0, pd.NA))) * 100
    out["Cost_pct"] = (out["Cost_Budget"] / out["Cost_Actual"].replace(0, pd.NA)) * 100

    out["Productivity_Status"] = out["Productivity_pct"].apply(lambda x: rag(x, 100, 95))
    out["Quality_Status"] = out["Quality_pct"].apply(lambda x: rag(x, 99.5, 99.0))
    out["OTD_Status"] = out["OTD_pct"].apply(lambda x: rag(x, 98, 95))
    out["Cost_Status"] = out["Cost_pct"].apply(lambda x: rag(x, 100, 95))
    out["Safety_Status"] = out["Safety_Incidents"].apply(lambda x: rag(x, 0, 1, higher_is_better=False))

    weights = {
        "Productivity_pct": 0.30,
        "Quality_pct": 0.20,
        "OTD_pct": 0.20,
        "Cost_pct": 0.20,
    }
    weighted = sum(out[k].clip(upper=120).fillna(0) * w for k, w in weights.items())
    safety_score = out["Safety_Incidents"].map(lambda x: 100 if x == 0 else (85 if x == 1 else 65))
    out["Overall_Score"] = weighted + safety_score * 0.10
    out["Overall_Status"] = out["Overall_Score"].apply(lambda x: rag(x, 98, 93))
    return out

def rules_analysis(row):
    findings = []
    actions = []

    if row["Productivity_pct"] < 95:
        findings.append(f"Productivity is {row['Productivity_pct']:.1f}% of target.")
        actions.append("Review staffing versus forecast and identify activities causing excess hours.")
    elif row["Productivity_pct"] < 100:
        findings.append(f"Productivity is slightly below target at {row['Productivity_pct']:.1f}%.")

    if row["Quality_pct"] < 99.5:
        findings.append(f"Quality is below target at {row['Quality_pct']:.2f}%.")
        actions.append("Run a Pareto on errors and complete RCA on the largest error category.")

    if row["OTD_pct"] < 98:
        findings.append(f"On-time delivery is below target at {row['OTD_pct']:.1f}%.")
        actions.append("Review late orders by root cause: capacity, planning, picking, loading or carrier.")

    if row["Cost_pct"] < 100:
        findings.append(f"Cost performance is {row['Cost_pct']:.1f}% versus budget.")
        actions.append("Separate cost variance into labor, overtime, transport and consumables.")

    if row["Safety_Incidents"] > 0:
        findings.append(f"{int(row['Safety_Incidents'])} safety incident(s) were recorded.")
        actions.append("Complete incident review and verify corrective actions before next review.")

    if not findings:
        findings.append("All primary KPIs are on or above target.")
        actions.append("Maintain current controls and focus on sustaining performance.")

    return " ".join(findings), actions[:3]

def ai_analysis(row):
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    if not api_key or not model:
        summary, actions = rules_analysis(row)
        return summary, actions, "Rule-based mode"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        payload = {
            "company": row["Company"],
            "week": int(row["Week"]),
            "overall_score": round(float(row["Overall_Score"]), 1),
            "productivity_pct": round(float(row["Productivity_pct"]), 1),
            "quality_pct": round(float(row["Quality_pct"]), 2),
            "otd_pct": round(float(row["OTD_pct"]), 1),
            "cost_pct": round(float(row["Cost_pct"]), 1),
            "safety_incidents": int(row["Safety_Incidents"]),
        }

        prompt = f"""
You are a senior operations performance manager.
Analyze this KPI record:
{json.dumps(payload)}

Return concise management output in exactly this structure:
SUMMARY: <2-4 sentences>
ACTIONS:
1. <action>
2. <action>
3. <action>

Focus on operational causes, priorities, and measurable next steps.
Do not invent facts that are not in the data.
"""
        response = client.responses.create(
            model=model,
            input=prompt,
        )
        text = response.output_text.strip()

        summary = text
        actions = []
        if "ACTIONS:" in text:
            summary, action_text = text.split("ACTIONS:", 1)
            summary = summary.replace("SUMMARY:", "").strip()
            for line in action_text.splitlines():
                clean = line.strip()
                if clean[:2] in {"1.", "2.", "3."}:
                    actions.append(clean[2:].strip())
        if not actions:
            _, actions = rules_analysis(row)
        return summary, actions[:3], f"AI mode ({model})"
    except Exception as exc:
        summary, actions = rules_analysis(row)
        return summary + f" AI connection failed, so rule-based analysis was used.", actions, "Fallback mode"

st.title("AI KPI Performance Manager")
st.caption("Version 1 — Logistics / Warehouse Performance")

with st.sidebar:
    st.header("Input")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    st.markdown("Required columns:")
    st.code(", ".join(REQUIRED_COLUMNS), language=None)

if uploaded:
    df = pd.read_csv(uploaded)
else:
    df = pd.read_csv("sample_kpi_data.csv")
    st.info("Demo data is loaded. Upload your own CSV from the sidebar.")

missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
if missing:
    st.error(f"Missing columns: {', '.join(missing)}")
    st.stop()

numeric_cols = [c for c in REQUIRED_COLUMNS if c not in ["Company"]]
for c in numeric_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce")

kpi = calculate_kpis(df)

latest_week = int(kpi["Week"].max())
latest = kpi[kpi["Week"] == latest_week].copy()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest week", latest_week)
c2.metric("Companies", latest["Company"].nunique())
c3.metric("Average overall", f"{latest['Overall_Score'].mean():.1f}%")
c4.metric("Red accounts", int((latest["Overall_Status"] == "RED").sum()))

st.subheader("Company Performance")
show_cols = [
    "Company", "Week", "Productivity_pct", "Quality_pct", "OTD_pct",
    "Cost_pct", "Safety_Incidents", "Overall_Score", "Overall_Status"
]
display = latest[show_cols].sort_values("Overall_Score", ascending=False).copy()
display.columns = [
    "Company", "Week", "Productivity %", "Quality %", "OTD %",
    "Cost %", "Safety incidents", "Overall score", "Status"
]
st.dataframe(
    display.style.format({
        "Productivity %": "{:.1f}",
        "Quality %": "{:.2f}",
        "OTD %": "{:.1f}",
        "Cost %": "{:.1f}",
        "Overall score": "{:.1f}",
    }),
    use_container_width=True,
    hide_index=True
)

st.subheader("Trend")
company = st.selectbox("Select company", sorted(kpi["Company"].unique()))
trend = kpi[kpi["Company"] == company].sort_values("Week")
st.line_chart(
    trend.set_index("Week")[["Productivity_pct", "Quality_pct", "OTD_pct", "Cost_pct", "Overall_Score"]]
)

st.subheader("AI Management Analysis")
selected_week = st.selectbox("Select week", sorted(kpi[kpi["Company"] == company]["Week"].unique(), reverse=True))
row = kpi[(kpi["Company"] == company) & (kpi["Week"] == selected_week)].iloc[0]

summary, actions, mode = ai_analysis(row)

st.markdown(f"### {company} — Week {int(selected_week)}")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Overall", f"{row['Overall_Score']:.1f}%", row["Overall_Status"])
m2.metric("Productivity", f"{row['Productivity_pct']:.1f}%", row["Productivity_Status"])
m3.metric("Quality", f"{row['Quality_pct']:.2f}%", row["Quality_Status"])
m4.metric("OTD", f"{row['OTD_pct']:.1f}%", row["OTD_Status"])
m5.metric("Cost", f"{row['Cost_pct']:.1f}%", row["Cost_Status"])

st.write(summary)
st.markdown("**Top actions**")
for i, action in enumerate(actions, 1):
    st.write(f"{i}. {action}")

st.caption(mode)

st.subheader("Download Calculated KPI Data")
csv = kpi.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download KPI results",
    data=csv,
    file_name="kpi_results.csv",
    mime="text/csv"
)
