from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import quote_plus

import pandas as pd
import plotly.express as px
import streamlit as st

SHEET_URL = st.secrets.get(
    "GOOGLE_SHEET_URL",
    "https://docs.google.com/spreadsheets/d/18AYYaEv450ZGQBwBOw6oODQs-qlJxVp3LetJ70-Lmt8/edit?usp=sharing",
)
SHEET_NAME = st.secrets.get("GOOGLE_SHEET_NAME", "Job Applications")

st.set_page_config(
    page_title="Job Application Tracker",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.block-container{padding-top:1.4rem;max-width:1500px}.hero{border:1px solid rgba(148,163,184,.25);border-radius:28px;padding:30px;background:radial-gradient(circle at top left,rgba(37,99,235,.18),transparent 34%),radial-gradient(circle at top right,rgba(16,185,129,.16),transparent 32%),linear-gradient(135deg,rgba(248,250,252,.96),rgba(241,245,249,.76));margin-bottom:1.2rem}.hero h1{font-size:clamp(2rem,5vw,3.4rem);letter-spacing:-.06em;margin:0;line-height:1}.hero p{color:#64748b;font-size:1.05rem;margin:.75rem 0 0}.metric-card{border:1px solid rgba(148,163,184,.25);border-radius:22px;padding:18px;background:rgba(255,255,255,.78);box-shadow:0 12px 30px rgba(15,23,42,.06);min-height:118px}.metric-label{font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:800}.metric-value{font-size:clamp(1.7rem,4vw,2.45rem);font-weight:900;letter-spacing:-.05em;margin-top:.35rem}.metric-help{font-size:.83rem;color:#64748b}.panel{border:1px solid rgba(148,163,184,.25);border-radius:22px;padding:16px;background:rgba(255,255,255,.72);box-shadow:0 10px 26px rgba(15,23,42,.045)}.pill{display:inline-block;border-radius:999px;padding:4px 10px;border:1px solid rgba(148,163,184,.3);font-size:.75rem;font-weight:800;background:#f8fafc}.muted{color:#64748b;font-size:.88rem}@media(max-width:768px){.hero{padding:22px 18px;border-radius:22px}.metric-card{min-height:104px}}
</style>
""",
    unsafe_allow_html=True,
)

STATUS_COLORS = {
    "Application Received": "#2563eb",
    "Recruiter / Follow-up": "#7c3aed",
    "Online Assessment": "#f59e0b",
    "Interview / Scheduling": "#10b981",
    "Offer / Positive Update": "#16a34a",
    "Rejected": "#ef4444",
    "Job Related": "#64748b",
    "Unknown": "#94a3b8",
}
STATUS_ORDER = list(STATUS_COLORS)
ACTION_STATUSES = {"Online Assessment", "Interview / Scheduling", "Recruiter / Follow-up", "Offer / Positive Update"}


def spreadsheet_id(value: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", str(value))
    return match.group(1) if match else str(value).strip()


def csv_url(sheet_url: str, sheet_name: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id(sheet_url)}/gviz/tq?tqx=out:csv&sheet={quote_plus(sheet_name)}"


@st.cache_data(ttl=600, show_spinner=False)
def load_data(sheet_url: str, sheet_name: str) -> pd.DataFrame:
    df = pd.read_csv(csv_url(sheet_url, sheet_name))
    df.columns = [str(c).strip() for c in df.columns]
    return df


def clean_status(value: str) -> str:
    text = str(value or "").lower()
    if any(x in text for x in ["offer", "positive"]):
        return "Offer / Positive Update"
    if any(x in text for x in ["interview", "schedule", "scheduling", "availability"]):
        return "Interview / Scheduling"
    if any(x in text for x in ["assessment", "codesignal", "hackerrank", "coding test", "test invite"]):
        return "Online Assessment"
    if any(x in text for x in ["rejected", "not selected", "unsuccessful", "not moving forward", "regret"]):
        return "Rejected"
    if any(x in text for x in ["application received", "thank you for applying", "received"]):
        return "Application Received"
    if any(x in text for x in ["recruiter", "talent", "follow"]):
        return "Recruiter / Follow-up"
    return str(value).strip() if str(value).strip() else "Unknown"


def text_of(row: pd.Series) -> str:
    cols = ["Email Type / Status", "Subject", "Notes", "Sender", "Company Name", "Job Role"]
    return " ".join(str(row.get(c, "")) for c in cols).lower()


def action_needed(row: pd.Series) -> bool:
    status = clean_status(row.get("Email Type / Status", ""))
    text = text_of(row)
    terms = ["deadline", "complete", "due", "before", "availability", "schedule", "reply", "respond", "confirm", "assessment", "interview", "next step", "next stage"]
    return status in ACTION_STATUSES or (status != "Rejected" and any(t in text for t in terms))


def priority(row: pd.Series) -> str:
    status = clean_status(row.get("Email Type / Status", ""))
    text = text_of(row)
    if status in {"Interview / Scheduling", "Offer / Positive Update"} or any(t in text for t in ["deadline", "due", "within 24", "within 48"]):
        return "High"
    if status in {"Online Assessment", "Recruiter / Follow-up"}:
        return "Medium"
    return "Normal"


def thread_type(row: pd.Series) -> str:
    status = clean_status(row.get("Email Type / Status", ""))
    text = text_of(row)
    if "referral" in text or "referred" in text:
        return "Referral"
    return {
        "Rejected": "Rejection",
        "Online Assessment": "Assessment",
        "Interview / Scheduling": "Interview",
        "Recruiter / Follow-up": "Recruiter",
        "Application Received": "Portal Application",
        "Offer / Positive Update": "Offer",
    }.get(status, "Other")


def deadline(row: pd.Series) -> str:
    text = f"{row.get('Subject','')} {row.get('Notes','')}"
    patterns = [
        r"(?:deadline|due|before|by)\s+([A-Za-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?)",
        r"(?:deadline|due|before|by)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"within\s+(\d+\s+(?:hours?|days?))",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return m.group(1).strip()
    return ""


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    defaults = {
        "Tracked At": "", "Received Date": "", "Received Time": "", "Company Name": "Unknown", "Job Role": "Unknown",
        "Email Type / Status": "Unknown", "Sender": "", "Subject": "", "Gmail Link": "", "Notes": "",
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    for col in defaults:
        df[col] = df[col].fillna(defaults[col]).astype(str).str.strip()
    df["Company Name"] = df["Company Name"].replace("", "Unknown")
    df["Job Role"] = df["Job Role"].replace("", "Unknown")
    combined = (df["Received Date"] + " " + df["Received Time"]).str.strip()
    df["Received Datetime"] = pd.to_datetime(combined, errors="coerce")
    fallback = pd.to_datetime(df["Received Date"], errors="coerce")
    df.loc[df["Received Datetime"].isna(), "Received Datetime"] = fallback
    df["Date"] = df["Received Datetime"].dt.date
    df["Time"] = df["Received Datetime"].dt.strftime("%H:%M").fillna("")
    df["Status"] = df["Email Type / Status"].apply(clean_status)
    df["Action Needed"] = df.apply(action_needed, axis=1)
    df["Priority"] = df.apply(priority, axis=1)
    df["Thread Type"] = df.apply(thread_type, axis=1)
    df["Deadline"] = df.apply(deadline, axis=1)
    return df.sort_values("Received Datetime", ascending=False, na_position="last")


def card(label: str, value: int | str, help_text: str) -> None:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div><div class='metric-help'>{help_text}</div></div>", unsafe_allow_html=True)


def filter_df(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.title("⚙️ Tracker")
    st.sidebar.caption("Google Sheet → Streamlit dashboard")
    if st.sidebar.button("Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.divider()
    st.sidebar.header("Filters")
    if df.empty:
        return df
    min_dt, max_dt = df["Received Datetime"].min(), df["Received Datetime"].max()
    min_date = min_dt.date() if pd.notna(min_dt) else date.today() - timedelta(days=30)
    max_date = max_dt.date() if pd.notna(max_dt) else date.today()
    picked = st.sidebar.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    start, end = picked if isinstance(picked, tuple) and len(picked) == 2 else (min_date, max_date)
    statuses = st.sidebar.multiselect("Status", [s for s in STATUS_ORDER if s in set(df["Status"])] + sorted(set(df["Status"]) - set(STATUS_ORDER)))
    companies = st.sidebar.multiselect("Company", sorted(df["Company Name"].unique()))
    priorities = st.sidebar.multiselect("Priority", ["High", "Medium", "Normal"])
    action = st.sidebar.radio("Action Needed", ["All", "Yes", "No"], horizontal=True)
    search = st.sidebar.text_input("Search company / role / subject")
    out = df[(df["Date"] >= start) & (df["Date"] <= end)].copy()
    if statuses:
        out = out[out["Status"].isin(statuses)]
    if companies:
        out = out[out["Company Name"].isin(companies)]
    if priorities:
        out = out[out["Priority"].isin(priorities)]
    if action == "Yes":
        out = out[out["Action Needed"]]
    if action == "No":
        out = out[~out["Action Needed"]]
    if search.strip():
        q = search.lower().strip()
        blob = (out["Company Name"] + " " + out["Job Role"] + " " + out["Subject"] + " " + out["Notes"]).str.lower()
        out = out[blob.str.contains(re.escape(q), na=False)]
    return out


def show_metrics(df: pd.DataFrame) -> None:
    cols = st.columns(7)
    values = [
        ("Total", len(df), "tracked rows"),
        ("This Week", int((df["Received Datetime"] >= pd.Timestamp.now() - pd.Timedelta(days=7)).sum()) if not df.empty else 0, "last 7 days"),
        ("Action", int(df["Action Needed"].sum()) if not df.empty else 0, "needs attention"),
        ("Assessments", int((df["Status"] == "Online Assessment").sum()) if not df.empty else 0, "tests/tasks"),
        ("Interviews", int((df["Status"] == "Interview / Scheduling").sum()) if not df.empty else 0, "calls/scheduling"),
        ("Recruiters", int((df["Status"] == "Recruiter / Follow-up").sum()) if not df.empty else 0, "follow-ups"),
        ("Rejected", int((df["Status"] == "Rejected").sum()) if not df.empty else 0, "closed"),
    ]
    for col, item in zip(cols, values):
        with col:
            card(*item)


def charts(df: pd.DataFrame) -> None:
    left, right = st.columns(2)
    with left:
        st.subheader("Status pipeline")
        if df.empty:
            st.info("No data yet.")
        else:
            x = df.groupby("Status", as_index=False).size().rename(columns={"size": "Count"}).sort_values("Count", ascending=False)
            fig = px.bar(x, x="Status", y="Count", text="Count", color="Status", color_discrete_map=STATUS_COLORS)
            fig.update_layout(height=390, margin=dict(l=10, r=10, t=20, b=10), showlegend=False, xaxis_title="", yaxis_title="Emails")
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Daily activity")
        if df.empty:
            st.info("No data yet.")
        else:
            d = df.dropna(subset=["Received Datetime"]).assign(Day=lambda z: z["Received Datetime"].dt.date).groupby(["Day", "Status"], as_index=False).size().rename(columns={"size": "Count"})
            fig = px.area(d, x="Day", y="Count", color="Status", color_discrete_map=STATUS_COLORS)
            fig.update_layout(height=390, margin=dict(l=10, r=10, t=20, b=10), xaxis_title="", yaxis_title="Emails", legend_title="")
            st.plotly_chart(fig, use_container_width=True)


def dataframe(df: pd.DataFrame, followups_only: bool = False) -> None:
    if followups_only:
        df = df[df["Action Needed"]].copy()
        df["Priority Rank"] = df["Priority"].map({"High": 0, "Medium": 1, "Normal": 2}).fillna(3)
        df = df.sort_values(["Priority Rank", "Received Datetime"], ascending=[True, False])
    cols = ["Date", "Time", "Priority", "Company Name", "Job Role", "Status", "Action Needed", "Thread Type", "Deadline", "Subject", "Gmail Link", "Notes"]
    display = df[cols].rename(columns={"Company Name": "Company", "Job Role": "Role", "Gmail Link": "Open Email"})
    st.dataframe(display, use_container_width=True, hide_index=True, height=560, column_config={"Open Email": st.column_config.LinkColumn("Open Email", display_text="Open"), "Action Needed": st.column_config.CheckboxColumn("Action Needed"), "Subject": st.column_config.TextColumn(width="large"), "Notes": st.column_config.TextColumn(width="large")})
    st.download_button("Download filtered CSV", display.to_csv(index=False).encode("utf-8"), f"job_applications_{datetime.now():%Y%m%d_%H%M}.csv", "text/csv")


def company_timeline(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No company data yet.")
        return
    summary = df.groupby("Company Name", as_index=False).agg(Emails=("Company Name", "size"), Latest=("Received Datetime", "max"), ActionNeeded=("Action Needed", "sum")).sort_values(["ActionNeeded", "Latest"], ascending=[False, False])
    left, right = st.columns([.9, 1.1])
    with left:
        fig = px.bar(summary.head(15), x="Emails", y="Company Name", orientation="h", color="ActionNeeded", text="Emails")
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=20, b=10), yaxis={"categoryorder": "total ascending"}, xaxis_title="Emails", yaxis_title="", coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        company = st.selectbox("Select company", summary["Company Name"].tolist())
        for _, row in df[df["Company Name"] == company].head(12).iterrows():
            when = row["Received Datetime"].strftime("%d %b %Y %H:%M") if pd.notna(row["Received Datetime"]) else "Unknown"
            st.markdown(f"<div class='panel' style='margin-bottom:10px'><span class='pill'>{row['Status']}</span><h4 style='margin:.5rem 0 .1rem'>{row['Job Role']}</h4><div class='muted'>{when}</div><p>{row['Subject']}</p></div>", unsafe_allow_html=True)


def analytics(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No analytics yet.")
        return
    valid = df.dropna(subset=["Received Datetime"]).copy()
    valid["Week"] = valid["Received Datetime"].dt.to_period("W").astype(str)
    weekly = valid.groupby(["Week", "Status"], as_index=False).size().rename(columns={"size": "Count"})
    fig = px.bar(weekly, x="Week", y="Count", color="Status", barmode="stack", color_discrete_map=STATUS_COLORS)
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=20, b=10), legend_title="")
    st.plotly_chart(fig, use_container_width=True)
    c1, c2, c3 = st.columns(3)
    total = max(len(valid), 1)
    c1.metric("Rejection share", f"{valid['Status'].eq('Rejected').sum()/total*100:.1f}%")
    c2.metric("Action-needed share", f"{valid['Action Needed'].sum()/total*100:.1f}%")
    c3.metric("Assessment share", f"{valid['Status'].eq('Online Assessment').sum()/total*100:.1f}%")


def main() -> None:
    try:
        df = prepare(load_data(SHEET_URL, SHEET_NAME))
    except Exception as exc:
        st.error("Google Sheet read nahi ho pa raha.")
        st.markdown("Sheet sharing **Anyone with the link → Viewer** karo aur tab name **Job Applications** rakho.")
        st.code(str(exc))
        return
    latest = df["Received Datetime"].max()
    latest_text = latest.strftime("%d %b %Y, %H:%M") if pd.notna(latest) else "No rows yet"
    st.markdown(f"<div class='hero'><h1>📬 Job Application Tracker</h1><p>Live Gmail → Google Sheet → Streamlit dashboard • Latest tracked: {latest_text}</p></div>", unsafe_allow_html=True)
    filtered = filter_df(df)
    show_metrics(filtered)
    tabs = st.tabs(["Overview", "Follow-ups", "Applications", "Company Timeline", "Analytics"])
    with tabs[0]:
        charts(filtered)
    with tabs[1]:
        st.subheader("🔥 Follow-up needed")
        if filtered[filtered["Action Needed"]].empty:
            st.success("No urgent job email needs action right now.")
        else:
            dataframe(filtered, followups_only=True)
    with tabs[2]:
        st.subheader("📋 All tracked emails")
        dataframe(filtered)
    with tabs[3]:
        st.subheader("🏢 Company timeline")
        company_timeline(filtered)
    with tabs[4]:
        st.subheader("📈 Weekly analytics")
        analytics(filtered)


if __name__ == "__main__":
    main()
