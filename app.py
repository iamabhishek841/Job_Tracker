from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import quote_plus

import pandas as pd
import plotly.express as px
import streamlit as st

SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", "https://docs.google.com/spreadsheets/d/18AYYaEv450ZGQBwBOw6oODQs-qlJxVp3LetJ70-Lmt8/edit?usp=sharing")
SHEET_NAME = st.secrets.get("GOOGLE_SHEET_NAME", "Job Applications")

st.set_page_config(page_title="Job Application Tracker", page_icon="📬", layout="wide")
st.markdown("""
<style>
.block-container{max-width:1500px;padding-top:1.3rem}.hero{border-radius:24px;padding:26px;background:linear-gradient(135deg,#f8fafc,#eef6ff);border:1px solid #e2e8f0;margin-bottom:1rem}.hero h1{font-size:clamp(2rem,5vw,3.2rem);letter-spacing:-.05em;margin:0}.hero p{color:#64748b}.metric-card{border:1px solid #e2e8f0;border-radius:18px;padding:15px;background:white}.metric-label{font-size:.75rem;text-transform:uppercase;color:#64748b;font-weight:800}.metric-value{font-size:2rem;font-weight:900}.metric-help{color:#64748b;font-size:.82rem}.panel{border:1px solid #e2e8f0;border-radius:18px;padding:14px;background:white;margin-bottom:10px}.pill{border-radius:99px;padding:4px 10px;background:#f8fafc;border:1px solid #e2e8f0;font-weight:800;font-size:.75rem}.muted{color:#64748b;font-size:.86rem}
</style>
""", unsafe_allow_html=True)

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
EVENT_NOISE = ["hackathon", "workshop", "webinar", "bootcamp", "masterclass", "summit", "meetup", "career fair", "campus event", "virtual event", "community challenge"]
MARKETING_NOISE = ["newsletter", "job alert", "jobs alert", "recommended jobs", "top employers", "company spotlights", "discover your path", "contest", "streak", "unsubscribe"]
GENERIC_COMPANIES = {"codesignal", "leetcode", "hello", "mail", "comms", "unknown"}


def sheet_id(url: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", str(url))
    return m.group(1) if m else str(url).strip()


@st.cache_data(ttl=600, show_spinner=False)
def load_data(url: str, sheet: str) -> pd.DataFrame:
    csv = f"https://docs.google.com/spreadsheets/d/{sheet_id(url)}/gviz/tq?tqx=out:csv&sheet={quote_plus(sheet)}"
    df = pd.read_csv(csv)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def blob(row: pd.Series) -> str:
    cols = ["Email Type / Status", "Subject", "Notes", "Sender", "Company Name", "Job Role"]
    return " ".join(str(row.get(c, "")) for c in cols).lower()


def has(t: str, terms: list[str]) -> bool:
    return any(x in t for x in terms)


def is_real_assessment(t: str) -> bool:
    assessment_terms = ["online assessment", "coding assessment", "technical assessment", "take the assessment", "complete the assessment", "assessment invite", "test invite", "coding test", "complete your test", "complete your assessment"]
    job_context = ["application", "role", "position", "recruit", "hiring", "graduate", "engineer", "analyst", "software"]
    return has(t, assessment_terms) and has(t, job_context) and not has(t, EVENT_NOISE + MARKETING_NOISE)


def keep_row(row: pd.Series) -> bool:
    t = blob(row)
    company = str(row.get("Company Name", "")).strip().lower()
    subject = str(row.get("Subject", "")).strip().lower()
    if has(t, EVENT_NOISE + MARKETING_NOISE):
        return False
    if company in GENERIC_COMPANIES and not is_real_assessment(t):
        return False
    if subject in {"keep track of your application", "thank you for applying!"} and company in GENERIC_COMPANIES:
        return False
    strong = ["thank you for applying", "thanks for applying", "application received", "has been received", "we received your application", "your application to", "not selected", "not moving forward", "unsuccessful", "regret to inform", "recruiter", "talent acquisition", "hiring team", "interview", "next stage", "schedule a call"]
    return has(t, strong) or is_real_assessment(t)


def row_status(row: pd.Series) -> str:
    t = blob(row)
    if has(t, ["not selected", "not moving forward", "unsuccessful", "regret to inform", "unfortunately"]):
        return "Rejected"
    if is_real_assessment(t):
        return "Online Assessment"
    if has(t, ["interview", "schedule a call", "availability", "calendar", "next stage", "next step", "technical screen"]):
        return "Interview / Next Stage"
    if has(t, ["recruiter", "talent acquisition", "hiring team", "follow-up", "follow up"]):
        return "Recruiter / Follow-up"
    if has(t, ["thank you for applying", "thanks for applying", "application received", "has been received", "we received your application", "your application to"]):
        return "Application Applied"
    return "Application Update"


def role(row: pd.Series) -> str:
    cur = str(row.get("Job Role", "")).strip()
    subj = str(row.get("Subject", "")).strip()
    if cur and cur.lower() not in {"unknown", "latest", "role. in the"}:
        return cur
    patterns = [r"role of\s+(.+?)(?:$|\.|,|\-| at )", r"for the role of\s+(.+?)(?:$|\.|,|\-| at )", r"for the\s+(.+?)\s+(?:role|position)", r"application for\s+(.+?)(?:$|\.|,| at )"]
    for p in patterns:
        m = re.search(p, subj, flags=re.I)
        if m:
            val = m.group(1).strip(" .,-")
            if 3 <= len(val) <= 90:
                return val
    return "Unknown"


def deadline(row: pd.Series) -> str:
    t = f"{row.get('Subject','')} {row.get('Notes','')}"
    for p in [r"(?:deadline|due|before|by)\s+([A-Za-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?)", r"(?:deadline|due|before|by)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", r"within\s+(\d+\s+(?:hours?|days?))"]:
        m = re.search(p, t, flags=re.I)
        if m:
            return m.group(1).strip()
    return ""


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    defaults = {"Tracked At": "", "Received Date": "", "Received Time": "", "Company Name": "Unknown", "Job Role": "Unknown", "Email Type / Status": "Unknown", "Sender": "", "Subject": "", "Gmail Link": "", "Notes": ""}
    df = df.copy()
    for c, d in defaults.items():
        if c not in df.columns:
            df[c] = d
        df[c] = df[c].fillna(d).astype(str).str.strip()
    df["Company Name"] = df["Company Name"].replace("", "Unknown")
    df["Job Role"] = df.apply(role, axis=1)
    dt = (df["Received Date"] + " " + df["Received Time"]).str.strip()
    df["Received Datetime"] = pd.to_datetime(dt, errors="coerce")
    df.loc[df["Received Datetime"].isna(), "Received Datetime"] = pd.to_datetime(df["Received Date"], errors="coerce")
    df["Date"] = df["Received Datetime"].dt.date
    df["Time"] = df["Received Datetime"].dt.strftime("%H:%M").fillna("")
    df = df[df.apply(keep_row, axis=1)].copy()
    df["Status"] = df.apply(row_status, axis=1)
    df["Action Needed"] = df.apply(lambda r: r["Status"] in ACTION_STATUSES or (r["Status"] != "Rejected" and has(blob(r), ["deadline", "complete", "due", "before", "availability", "schedule", "reply", "respond", "confirm", "assessment", "interview", "next step", "next stage"])), axis=1)
    df["Priority"] = df.apply(lambda r: "High" if r["Status"] == "Interview / Next Stage" or has(blob(r), ["deadline", "due", "within 24", "within 48"]) else ("Medium" if r["Status"] in {"Online Assessment", "Recruiter / Follow-up"} else "Normal"), axis=1)
    df["Thread Type"] = df["Status"].map({"Rejected": "Rejection", "Online Assessment": "Assessment", "Interview / Next Stage": "Interview", "Recruiter / Follow-up": "Recruiter", "Application Applied": "Applied", "Application Update": "Update"}).fillna("Update")
    df["Deadline"] = df.apply(deadline, axis=1)
    return df.sort_values("Received Datetime", ascending=False, na_position="last")


def card(label: str, value: int | str, help_text: str) -> None:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div><div class='metric-help'>{help_text}</div></div>", unsafe_allow_html=True)


def filter_df(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.title("⚙️ Tracker")
    st.sidebar.caption("Only real applications and updates")
    if st.sidebar.button("Refresh now", use_container_width=True, key="refresh_now_sidebar"):
        st.cache_data.clear(); st.rerun()
    st.sidebar.divider(); st.sidebar.header("Filters")
    if df.empty:
        return df
    start_default = df["Received Datetime"].min().date() if pd.notna(df["Received Datetime"].min()) else date.today() - timedelta(days=30)
    end_default = df["Received Datetime"].max().date() if pd.notna(df["Received Datetime"].max()) else date.today()
    picked = st.sidebar.date_input("Date range", value=(start_default, end_default), min_value=start_default, max_value=end_default, key="date_range_filter")
    start, end = picked if isinstance(picked, tuple) and len(picked) == 2 else (start_default, end_default)
    statuses = st.sidebar.multiselect("Status", [s for s in STATUS_ORDER if s in set(df["Status"])], key="status_filter")
    companies = st.sidebar.multiselect("Company", sorted(df["Company Name"].unique()), key="company_filter")
    priorities = st.sidebar.multiselect("Priority", ["High", "Medium", "Normal"], key="priority_filter")
    action = st.sidebar.radio("Action Needed", ["All", "Yes", "No"], horizontal=True, key="action_needed_filter")
    search = st.sidebar.text_input("Search company / role / subject", key="search_filter")
    out = df[(df["Date"] >= start) & (df["Date"] <= end)].copy()
    if statuses: out = out[out["Status"].isin(statuses)]
    if companies: out = out[out["Company Name"].isin(companies)]
    if priorities: out = out[out["Priority"].isin(priorities)]
    if action == "Yes": out = out[out["Action Needed"]]
    if action == "No": out = out[~out["Action Needed"]]
    if search.strip():
        q = search.lower().strip()
        hay = (out["Company Name"] + " " + out["Job Role"] + " " + out["Subject"] + " " + out["Notes"]).str.lower()
        out = out[hay.str.contains(re.escape(q), na=False)]
    return out


def show_metrics(df: pd.DataFrame) -> None:
    vals = [("Total", len(df), "clean rows"), ("Applied", int((df["Status"] == "Application Applied").sum()) if not df.empty else 0, "confirmations"), ("Updates", int((df["Status"] == "Application Update").sum()) if not df.empty else 0, "updates"), ("Assessments", int((df["Status"] == "Online Assessment").sum()) if not df.empty else 0, "tests"), ("Interviews", int((df["Status"] == "Interview / Next Stage").sum()) if not df.empty else 0, "next stage"), ("Rejected", int((df["Status"] == "Rejected").sum()) if not df.empty else 0, "closed")]
    for col, val in zip(st.columns(6), vals):
        with col: card(*val)


def charts(df: pd.DataFrame) -> None:
    left, right = st.columns(2)
    with left:
        st.subheader("Status pipeline")
        if df.empty: st.info("No clean data yet.")
        else:
            counts = df.groupby("Status", as_index=False).size().rename(columns={"size": "Count"})
            counts["Order"] = counts["Status"].map({s: i for i, s in enumerate(STATUS_ORDER)})
            fig = px.bar(counts.sort_values("Order"), x="Status", y="Count", text="Count", color="Status", color_discrete_map=STATUS_COLORS)
            fig.update_layout(height=390, margin=dict(l=10, r=10, t=20, b=10), showlegend=False, xaxis_title="", yaxis_title="Emails")
            st.plotly_chart(fig, use_container_width=True, key="status_pipeline_chart")
    with right:
        st.subheader("Daily activity")
        if df.empty: st.info("No clean data yet.")
        else:
            daily = df.dropna(subset=["Received Datetime"]).assign(Day=lambda z: z["Received Datetime"].dt.date).groupby(["Day", "Status"], as_index=False).size().rename(columns={"size": "Count"})
            fig = px.area(daily, x="Day", y="Count", color="Status", color_discrete_map=STATUS_COLORS)
            fig.update_layout(height=390, margin=dict(l=10, r=10, t=20, b=10), xaxis_title="", yaxis_title="Emails", legend_title="")
            st.plotly_chart(fig, use_container_width=True, key="daily_activity_chart")


def data_table(df: pd.DataFrame, followups: bool = False) -> None:
    key = "followups" if followups else "applications"
    data = df[df["Action Needed"]].copy() if followups else df.copy()
    if followups and not data.empty:
        data["Priority Rank"] = data["Priority"].map({"High": 0, "Medium": 1, "Normal": 2}).fillna(3)
        data = data.sort_values(["Priority Rank", "Received Datetime"], ascending=[True, False])
    cols = ["Date", "Time", "Priority", "Company Name", "Job Role", "Status", "Action Needed", "Thread Type", "Deadline", "Subject", "Gmail Link", "Notes"]
    display = data[cols].rename(columns={"Company Name": "Company", "Job Role": "Role", "Gmail Link": "Open Email"})
    st.dataframe(display, use_container_width=True, hide_index=True, height=560, key=f"{key}_table", column_config={"Open Email": st.column_config.LinkColumn("Open Email", display_text="Open"), "Action Needed": st.column_config.CheckboxColumn("Action Needed"), "Subject": st.column_config.TextColumn(width="large"), "Notes": st.column_config.TextColumn(width="large")})
    st.download_button("Download filtered CSV", display.to_csv(index=False).encode("utf-8"), f"job_applications_{datetime.now():%Y%m%d_%H%M}.csv", "text/csv", key=f"download_{key}_csv")


def company_timeline(df: pd.DataFrame) -> None:
    if df.empty: st.info("No company data yet."); return
    summary = df.groupby("Company Name", as_index=False).agg(Emails=("Company Name", "size"), Latest=("Received Datetime", "max"), ActionNeeded=("Action Needed", "sum")).sort_values(["ActionNeeded", "Latest"], ascending=[False, False])
    left, right = st.columns([.9, 1.1])
    with left:
        fig = px.bar(summary.head(15), x="Emails", y="Company Name", orientation="h", color="ActionNeeded", text="Emails")
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=20, b=10), yaxis={"categoryorder": "total ascending"}, xaxis_title="Emails", yaxis_title="", coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True, key="company_summary_chart")
    with right:
        company = st.selectbox("Select company", summary["Company Name"].tolist(), key="company_timeline_select")
        for _, row in df[df["Company Name"] == company].head(12).iterrows():
            when = row["Received Datetime"].strftime("%d %b %Y %H:%M") if pd.notna(row["Received Datetime"]) else "Unknown"
            st.markdown(f"<div class='panel'><span class='pill'>{row['Status']}</span><h4 style='margin:.5rem 0 .1rem'>{row['Job Role']}</h4><div class='muted'>{when}</div><p>{row['Subject']}</p></div>", unsafe_allow_html=True)


def analytics(df: pd.DataFrame) -> None:
    if df.empty: st.info("No analytics yet."); return
    valid = df.dropna(subset=["Received Datetime"]).copy()
    valid["Week"] = valid["Received Datetime"].dt.to_period("W").astype(str)
    weekly = valid.groupby(["Week", "Status"], as_index=False).size().rename(columns={"size": "Count"})
    fig = px.bar(weekly, x="Week", y="Count", color="Status", barmode="stack", color_discrete_map=STATUS_COLORS)
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=20, b=10), legend_title="")
    st.plotly_chart(fig, use_container_width=True, key="weekly_analytics_chart")


def job_finder_tab() -> None:
    st.subheader("🎯 Job Finder")
    st.info("Company DB added. Next step is JD analyzer integration. For now, use the generated search links and company portal table.")
    role_family = st.selectbox("Role family", ["Backend Engineer", "Platform Engineer", "Software Engineer", "Data Platform Engineer", "Data Engineer", "ML Platform Engineer", "DevOps / SRE"])
    location = st.selectbox("Location", ["All Ireland", "Dublin", "Cork", "Galway", "Limerick", "Remote Ireland"])
    source = st.radio("Source", ["ATS portals", "Irish job boards", "LinkedIn link"], horizontal=True)
    role_query = {
        "Backend Engineer": "Backend Engineer OR Software Engineer OR Java Developer",
        "Platform Engineer": "Platform Engineer OR Cloud Software Engineer",
        "Software Engineer": "Software Engineer OR Software Developer",
        "Data Platform Engineer": "Data Platform Engineer OR Spark SQL",
        "Data Engineer": "Data Engineer OR Spark OR SQL",
        "ML Platform Engineer": "ML Platform Engineer OR MLOps Engineer",
        "DevOps / SRE": "Site Reliability Engineer OR DevOps Engineer",
    }[role_family]
    loc = "Ireland" if location == "All Ireland" else location
    if source == "ATS portals":
        queries = [f'site:boards.greenhouse.io {loc} ({role_query})', f'site:jobs.lever.co {loc} ({role_query})', f'site:ashbyhq.com {loc} ({role_query})', f'site:myworkdayjobs.com {loc} ({role_query})']
    elif source == "Irish job boards":
        queries = [f'site:irishjobs.ie {loc} ({role_query})', f'site:ie.indeed.com {loc} ({role_query})', f'site:jobs.ie {loc} ({role_query})']
    else:
        queries = [f'{role_query} {loc}']
    for q in queries:
        if source == "LinkedIn link":
            st.markdown(f"- [{q}](https://www.linkedin.com/jobs/search/?keywords={quote_plus(q)}&location=Ireland)")
        else:
            st.markdown(f"- [{q}](https://www.google.com/search?q={quote_plus(q)})")
    try:
        companies = pd.read_csv("data/companies.csv")
        st.dataframe(companies, use_container_width=True, hide_index=True, column_config={"career_url": st.column_config.LinkColumn("Career URL")})
    except Exception as exc:
        st.warning(f"Company DB not available: {exc}")


def main() -> None:
    try:
        df = prepare(load_data(SHEET_URL, SHEET_NAME))
    except Exception as exc:
        st.error("Google Sheet read nahi ho pa raha.")
        st.markdown("Sheet sharing **Anyone with the link → Viewer** karo aur tab name **Job Applications** rakho.")
        st.code(str(exc)); df = pd.DataFrame()
    latest = df["Received Datetime"].max() if not df.empty else pd.NaT
    latest_text = latest.strftime("%d %b %Y, %H:%M") if pd.notna(latest) else "No clean rows yet"
    st.markdown(f"<div class='hero'><h1>📬 Job Application Tracker</h1><p>Only real applications, updates, assessments, interviews and rejections • Latest tracked: {latest_text}</p></div>", unsafe_allow_html=True)
    filtered = filter_df(df) if not df.empty else df
    if not filtered.empty:
        show_metrics(filtered)
    tabs = st.tabs(["Overview", "Follow-ups", "Applications", "Company Timeline", "Analytics", "Job Finder"])
    with tabs[0]: charts(filtered) if not filtered.empty else st.info("No clean tracker data yet.")
    with tabs[1]: st.subheader("🔥 Follow-up needed"); data_table(filtered, followups=True) if not filtered.empty and not filtered[filtered["Action Needed"]].empty else st.success("No urgent job email needs action right now.")
    with tabs[2]: st.subheader("📋 All tracked emails"); data_table(filtered) if not filtered.empty else st.info("No tracked emails yet.")
    with tabs[3]: st.subheader("🏢 Company timeline"); company_timeline(filtered)
    with tabs[4]: st.subheader("📈 Weekly analytics"); analytics(filtered)
    with tabs[5]: job_finder_tab()


if __name__ == "__main__":
    main()
