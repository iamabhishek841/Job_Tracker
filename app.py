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
    "Application Applied": "#2563eb",
    "Application Update": "#64748b",
    "Recruiter / Follow-up": "#7c3aed",
    "Online Assessment": "#f59e0b",
    "Interview / Next Stage": "#10b981",
    "Rejected": "#ef4444",
}
STATUS_ORDER = list(STATUS_COLORS)
ACTION_STATUSES = {"Recruiter / Follow-up", "Online Assessment", "Interview / Next Stage"}

NOISE_TERMS = [
    "who's hiring",
    "whos hiring",
    "top employers",
    "company spotlights",
    "job alert",
    "jobs alert",
    "recommended jobs",
    "jobs you may be interested",
    "newsletter",
    "discover your path",
    "leetcode contest",
    "join leetcode contest",
    "get ready for interview",
    "interest in etsy",
    "unsubscribe",
]

GENERIC_COMPANIES = {"mail", "comms", "leetcode", "unknown", "workday@myworkday.com"}


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


def combined_text(row: pd.Series) -> str:
    cols = ["Email Type / Status", "Subject", "Notes", "Sender", "Company Name", "Job Role"]
    return " ".join(str(row.get(c, "")) for c in cols).lower()


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def classify_status(row: pd.Series) -> str:
    text = combined_text(row)
    raw_status = str(row.get("Email Type / Status", "")).lower()

    if has_any(text, ["not selected", "not moving forward", "unsuccessful", "regret to inform", "unfortunately"]):
        return "Rejected"
    if has_any(text, ["online assessment", "assessment", "codesignal", "hackerrank", "coding test", "test invite"]):
        return "Online Assessment"
    if has_any(text, ["interview", "schedule a call", "availability", "calendar", "next stage", "next step", "final round", "technical screen"]):
        return "Interview / Next Stage"
    if has_any(text, ["recruiter", "talent acquisition", "hiring team", "follow-up", "follow up"]):
        return "Recruiter / Follow-up"
    if has_any(text, ["thank you for applying", "thanks for applying", "application received", "has been received", "we received your application", "your application to"]):
        return "Application Applied"
    if "application" in text or "portal" in text or "workday" in text or "greenhouse" in text or "lever" in text:
        return "Application Update"
    if "job related" in raw_status:
        return "Application Update"
    return "Application Update"


def is_relevant(row: pd.Series) -> bool:
    text = combined_text(row)
    company = str(row.get("Company Name", "")).strip().lower()
    subject = str(row.get("Subject", "")).strip().lower()

    strong_terms = [
        "thank you for applying",
        "thanks for applying",
        "application received",
        "has been received",
        "we received your application",
        "your application to",
        "online assessment",
        "assessment",
        "codesignal",
        "hackerrank",
        "coding test",
        "interview",
        "next stage",
        "not selected",
        "not moving forward",
        "unsuccessful",
        "regret to inform",
        "recruiter",
        "talent acquisition",
        "hiring team",
    ]

    if has_any(text, NOISE_TERMS):
        return False
    if subject in {"keep track of your application", "thank you for applying!"} and company in GENERIC_COMPANIES:
        return False
    return has_any(text, strong_terms)


def extract_role(row: pd.Series) -> str:
    current = str(row.get("Job Role", "")).strip()
    subject = str(row.get("Subject", "")).strip()
    if current and current.lower() not in {"unknown", "latest", "role. in the"}:
        return current
    patterns = [
        r"role of\s+(.+?)(?:$|\.|,|\-| at )",
        r"for the role of\s+(.+?)(?:$|\.|,|\-| at )",
        r"for the\s+(.+?)\s+(?:role|position)",
        r"application for\s+(.+?)(?:$|\.|,| at )",
    ]
    for pattern in patterns:
        match = re.search(pattern, subject, flags=re.I)
        if match:
            role = match.group(1).strip(" .,-")
            if 3 <= len(role) <= 90:
                return role
    return "Unknown"


def action_needed(row: pd.Series) -> bool:
    status = str(row.get("Status", ""))
    text = combined_text(row)
    action_terms = ["deadline", "complete", "due", "before", "availability", "schedule", "reply", "respond", "confirm", "assessment", "interview", "next step", "next stage"]
    return status in ACTION_STATUSES or (status != "Rejected" and has_any(text, action_terms))


def priority(row: pd.Series) -> str:
    status = str(row.get("Status", ""))
    text = combined_text(row)
    if status == "Interview / Next Stage" or has_any(text, ["deadline", "due", "within 24", "within 48"]):
        return "High"
    if status in {"Online Assessment", "Recruiter / Follow-up"}:
        return "Medium"
    return "Normal"


def thread_type(row: pd.Series) -> str:
    status = str(row.get("Status", ""))
    return {
        "Rejected": "Rejection",
        "Online Assessment": "Assessment",
        "Interview / Next Stage": "Interview",
        "Recruiter / Follow-up": "Recruiter",
        "Application Applied": "Applied",
        "Application Update": "Update",
    }.get(status, "Update")


def deadline(row: pd.Series) -> str:
    text = f"{row.get('Subject','')} {row.get('Notes','')}"
    patterns = [
        r"(?:deadline|due|before|by)\s+([A-Za-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?)",
        r"(?:deadline|due|before|by)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"within\s+(\d+\s+(?:hours?|days?))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).strip()
    return ""


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    defaults = {
        "Tracked At": "",
        "Received Date": "",
        "Received Time": "",
        "Company Name": "Unknown",
        "Job Role": "Unknown",
        "Email Type / Status": "Unknown",
        "Sender": "",
        "Subject": "",
        "Gmail Link": "",
        "Notes": "",
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].fillna(default).astype(str).str.strip()

    df["Company Name"] = df["Company Name"].replace("", "Unknown")
    df["Job Role"] = df.apply(extract_role, axis=1)
    combined = (df["Received Date"] + " " + df["Received Time"]).str.strip()
    df["Received Datetime"] = pd.to_datetime(combined, errors="coerce")
    fallback = pd.to_datetime(df["Received Date"], errors="coerce")
    df.loc[df["Received Datetime"].isna(), "Received Datetime"] = fallback
    df["Date"] = df["Received Datetime"].dt.date
    df["Time"] = df["Received Datetime"].dt.strftime("%H:%M").fillna("")
    df = df[df.apply(is_relevant, axis=1)].copy()
    df["Status"] = df.apply(classify_status, axis=1)
    df["Action Needed"] = df.apply(action_needed, axis=1)
    df["Priority"] = df.apply(priority, axis=1)
    df["Thread Type"] = df.apply(thread_type, axis=1)
    df["Deadline"] = df.apply(deadline, axis=1)
    return df.sort_values("Received Datetime", ascending=False, na_position="last")


def card(label: str, value: int | str, help_text: str) -> None:
    st.markdown(
        f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div><div class='metric-help'>{help_text}</div></div>",
        unsafe_allow_html=True,
    )


def filter_df(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.title("⚙️ Tracker")
    st.sidebar.caption("Only applied jobs, updates, assessments, interviews and rejections")
    if st.sidebar.button("Refresh now", use_container_width=True, key="refresh_now_sidebar"):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.divider()
    st.sidebar.header("Filters")
    if df.empty:
        return df
    min_dt, max_dt = df["Received Datetime"].min(), df["Received Datetime"].max()
    min_date = min_dt.date() if pd.notna(min_dt) else date.today() - timedelta(days=30)
    max_date = max_dt.date() if pd.notna(max_dt) else date.today()
    picked = st.sidebar.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="date_range_filter")
    start, end = picked if isinstance(picked, tuple) and len(picked) == 2 else (min_date, max_date)
    status_options = [s for s in STATUS_ORDER if s in set(df["Status"])]
    statuses = st.sidebar.multiselect("Status", status_options, key="status_filter")
    companies = st.sidebar.multiselect("Company", sorted(df["Company Name"].unique()), key="company_filter")
    priorities = st.sidebar.multiselect("Priority", ["High", "Medium", "Normal"], key="priority_filter")
    action = st.sidebar.radio("Action Needed", ["All", "Yes", "No"], horizontal=True, key="action_needed_filter")
    search = st.sidebar.text_input("Search company / role / subject", key="search_filter")

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
        query = search.lower().strip()
        blob = (out["Company Name"] + " " + out["Job Role"] + " " + out["Subject"] + " " + out["Notes"]).str.lower()
        out = out[blob.str.contains(re.escape(query), na=False)]
    return out


def show_metrics(df: pd.DataFrame) -> None:
    cols = st.columns(6)
    values = [
        ("Total", len(df), "clean tracked rows"),
        ("Applied", int((df["Status"] == "Application Applied").sum()) if not df.empty else 0, "confirmation emails"),
        ("Updates", int((df["Status"] == "Application Update").sum()) if not df.empty else 0, "portal updates"),
        ("Assessments", int((df["Status"] == "Online Assessment").sum()) if not df.empty else 0, "tests/tasks"),
        ("Interviews", int((df["Status"] == "Interview / Next Stage").sum()) if not df.empty else 0, "next stage"),
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
            st.info("No clean job-tracker data yet.")
        else:
            counts = df.groupby("Status", as_index=False).size().rename(columns={"size": "Count"})
            counts["Order"] = counts["Status"].map({s: i for i, s in enumerate(STATUS_ORDER)})
            counts = counts.sort_values("Order")
            fig = px.bar(counts, x="Status", y="Count", text="Count", color="Status", color_discrete_map=STATUS_COLORS)
            fig.update_layout(height=390, margin=dict(l=10, r=10, t=20, b=10), showlegend=False, xaxis_title="", yaxis_title="Emails")
            st.plotly_chart(fig, use_container_width=True, key="status_pipeline_chart")
    with right:
        st.subheader("Daily activity")
        if df.empty:
            st.info("No clean job-tracker data yet.")
        else:
            daily = df.dropna(subset=["Received Datetime"]).assign(Day=lambda z: z["Received Datetime"].dt.date).groupby(["Day", "Status"], as_index=False).size().rename(columns={"size": "Count"})
            fig = px.area(daily, x="Day", y="Count", color="Status", color_discrete_map=STATUS_COLORS)
            fig.update_layout(height=390, margin=dict(l=10, r=10, t=20, b=10), xaxis_title="", yaxis_title="Emails", legend_title="")
            st.plotly_chart(fig, use_container_width=True, key="daily_activity_chart")


def dataframe(df: pd.DataFrame, followups_only: bool = False) -> None:
    table_key = "followups" if followups_only else "applications"
    data = df.copy()
    if followups_only:
        data = data[data["Action Needed"]].copy()
        data["Priority Rank"] = data["Priority"].map({"High": 0, "Medium": 1, "Normal": 2}).fillna(3)
        data = data.sort_values(["Priority Rank", "Received Datetime"], ascending=[True, False])
    cols = ["Date", "Time", "Priority", "Company Name", "Job Role", "Status", "Action Needed", "Thread Type", "Deadline", "Subject", "Gmail Link", "Notes"]
    display = data[cols].rename(columns={"Company Name": "Company", "Job Role": "Role", "Gmail Link": "Open Email"})
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=560,
        key=f"{table_key}_table",
        column_config={
            "Open Email": st.column_config.LinkColumn("Open Email", display_text="Open"),
            "Action Needed": st.column_config.CheckboxColumn("Action Needed"),
            "Subject": st.column_config.TextColumn(width="large"),
            "Notes": st.column_config.TextColumn(width="large"),
        },
    )
    st.download_button(
        "Download filtered CSV",
        display.to_csv(index=False).encode("utf-8"),
        f"job_applications_{datetime.now():%Y%m%d_%H%M}.csv",
        "text/csv",
        key=f"download_{table_key}_csv",
    )


def company_timeline(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No company data yet.")
        return
    summary = df.groupby("Company Name", as_index=False).agg(Emails=("Company Name", "size"), Latest=("Received Datetime", "max"), ActionNeeded=("Action Needed", "sum")).sort_values(["ActionNeeded", "Latest"], ascending=[False, False])
    left, right = st.columns([0.9, 1.1])
    with left:
        fig = px.bar(summary.head(15), x="Emails", y="Company Name", orientation="h", color="ActionNeeded", text="Emails")
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=20, b=10), yaxis={"categoryorder": "total ascending"}, xaxis_title="Emails", yaxis_title="", coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True, key="company_summary_chart")
    with right:
        company = st.selectbox("Select company", summary["Company Name"].tolist(), key="company_timeline_select")
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
    st.plotly_chart(fig, use_container_width=True, key="weekly_analytics_chart")
    total = max(len(valid), 1)
    c1, c2, c3 = st.columns(3)
    c1.metric("Assessment share", f"{valid['Status'].eq('Online Assessment').sum()/total*100:.1f}%")
    c2.metric("Interview share", f"{valid['Status'].eq('Interview / Next Stage').sum()/total*100:.1f}%")
    c3.metric("Rejection share", f"{valid['Status'].eq('Rejected').sum()/total*100:.1f}%")


def main() -> None:
    try:
        df = prepare(load_data(SHEET_URL, SHEET_NAME))
    except Exception as exc:
        st.error("Google Sheet read nahi ho pa raha.")
        st.markdown("Sheet sharing **Anyone with the link → Viewer** karo aur tab name **Job Applications** rakho.")
        st.code(str(exc))
        return

    latest = df["Received Datetime"].max() if not df.empty else pd.NaT
    latest_text = latest.strftime("%d %b %Y, %H:%M") if pd.notna(latest) else "No clean rows yet"
    st.markdown(f"<div class='hero'><h1>📬 Job Application Tracker</h1><p>Only real applications, updates, assessments, interviews and rejections • Latest tracked: {latest_text}</p></div>", unsafe_allow_html=True)
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
