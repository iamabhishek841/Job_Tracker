import re
from datetime import date
from urllib.parse import quote_plus

import pandas as pd
import plotly.express as px
import streamlit as st

SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", "https://docs.google.com/spreadsheets/d/18AYYaEv450ZGQBwBOw6oODQs-qlJxVp3LetJ70-Lmt8/edit?usp=sharing")
SHEET_NAME = st.secrets.get("GOOGLE_SHEET_NAME", "Job Applications")

st.set_page_config(page_title="Job Application Tracker", page_icon="📬", layout="wide")

STATUS_ORDER = ["Application Applied", "Application Update", "Recruiter / Follow-up", "Online Assessment", "Interview / Next Stage", "Rejected"]
STATUS_COLORS = {
    "Application Applied": "#2563eb",
    "Application Update": "#64748b",
    "Recruiter / Follow-up": "#7c3aed",
    "Online Assessment": "#f59e0b",
    "Interview / Next Stage": "#10b981",
    "Rejected": "#ef4444",
}

NOISE = [
    "newsletter", "job alert", "recommended jobs", "top employers", "company spotlights",
    "contest", "streak", "unsubscribe", "neetcode", "leetcode", "webinar", "workshop",
    "hackathon", "summit", "meetup", "reset password", "reset link"
]

INTERVIEW_STRICT = [
    "interview invite", "interview invitation", "invited to interview", "invite you to interview",
    "selected for interview", "shortlisted for interview", "schedule your interview",
    "schedule an interview", "book your interview", "select a time for your interview",
    "choose a time for your interview", "availability for interview", "technical interview",
    "technical screen", "phone screen", "recruiter screen", "onsite interview", "final interview"
]

INTERVIEW_FALSE_POSITIVE = [
    "we will contact you to schedule an interview", "we will contact you to schedule",
    "if your qualifications match", "if your profile matches", "if your experience matches",
    "currently reviewing your candidacy", "currently reviewing your application",
    "reviewing your candidacy", "reviewing your application", "review process may take some time",
    "in the meantime"
]

ASSESSMENT_TERMS = ["online assessment", "coding assessment", "technical assessment", "assessment invite", "test invite", "coding test", "complete your test"]


def sheet_id(url):
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", str(url))
    return match.group(1) if match else str(url).strip()


@st.cache_data(ttl=600, show_spinner=False)
def load_sheet():
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id(SHEET_URL)}/gviz/tq?tqx=out:csv&sheet={quote_plus(SHEET_NAME)}"
    df = pd.read_csv(csv_url)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def has(text, terms):
    return any(term in text for term in terms)


def row_text(row):
    cols = ["Email Type / Status", "Subject", "Notes", "Sender", "Company Name", "Job Role"]
    return " ".join(str(row.get(c, "")) for c in cols).lower()


def is_interview(text):
    if has(text, INTERVIEW_FALSE_POSITIVE):
        return False
    return has(text, INTERVIEW_STRICT) and not has(text, NOISE)


def classify(row):
    text = row_text(row)
    raw_status = str(row.get("Email Type / Status", "")).lower()
    if has(text, ["not selected", "not moving forward", "unsuccessful", "regret to inform", "unfortunately"]):
        return "Rejected"
    if has(text, ASSESSMENT_TERMS) and not has(text, NOISE):
        return "Online Assessment"
    if is_interview(text):
        return "Interview / Next Stage"
    if has(text, ["recruiter", "talent acquisition", "hiring team", "follow-up", "follow up"]):
        return "Recruiter / Follow-up"
    if has(text, ["thank you for applying", "thanks for applying", "thank you for your interest", "application received", "has been received", "received your application", "we received your application", "your application to"]):
        return "Application Applied"
    if "interview" in raw_status:
        return "Application Update"
    return "Application Update"


def keep(row):
    text = row_text(row)
    subject = str(row.get("Subject", "")).lower().strip()
    if has(text, NOISE):
        return False
    if subject in {"keep track of your application", "thank you for applying!", "reset password link", "reset link"}:
        return False
    strong = [
        "thank you for applying", "thanks for applying", "thank you for your interest",
        "application received", "has been received", "received your application", "we received your application",
        "your application to", "not selected", "not moving forward", "unsuccessful", "regret to inform",
        "recruiter", "talent acquisition", "hiring team", "online assessment", "coding assessment", "coding test"
    ]
    return has(text, strong) or is_interview(text)


def extract_role(row):
    current = str(row.get("Job Role", "")).strip()
    subject = str(row.get("Subject", "")).strip()
    if current and current.lower() not in {"unknown", "latest", "role. in the"}:
        return current
    patterns = [r"role of\s+(.+?)(?:$|\.|,|\-| at )", r"for the role of\s+(.+?)(?:$|\.|,|\-| at )", r"application for\s+(.+?)(?:$|\.|,| at )"]
    for pattern in patterns:
        match = re.search(pattern, subject, flags=re.I)
        if match:
            value = match.group(1).strip(" .,-")
            if 3 <= len(value) <= 100:
                return value
    return "Unknown"


def prepare(df):
    defaults = {
        "Tracked At": "", "Received Date": "", "Received Time": "", "Company Name": "Unknown",
        "Job Role": "Unknown", "Email Type / Status": "Unknown", "Sender": "", "Subject": "",
        "Gmail Link": "", "Notes": ""
    }
    df = df.copy()
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].fillna(default).astype(str).str.strip()
    df["Company Name"] = df["Company Name"].replace("", "Unknown")
    df["Job Role"] = df.apply(extract_role, axis=1)
    combined = (df["Received Date"] + " " + df["Received Time"]).str.strip()
    df["Received Datetime"] = pd.to_datetime(combined, errors="coerce")
    df.loc[df["Received Datetime"].isna(), "Received Datetime"] = pd.to_datetime(df["Received Date"], errors="coerce")
    df["Date"] = df["Received Datetime"].dt.date
    df["Time"] = df["Received Datetime"].dt.strftime("%H:%M").fillna("")
    df = df[df.apply(keep, axis=1)].copy()
    df["Status"] = df.apply(classify, axis=1)
    df["Action Needed"] = df["Status"].isin(["Recruiter / Follow-up", "Online Assessment", "Interview / Next Stage"])
    df["Priority"] = df["Status"].map({"Interview / Next Stage": "High", "Online Assessment": "Medium", "Recruiter / Follow-up": "Medium"}).fillna("Normal")
    df["Thread Type"] = df["Status"].map({"Application Applied": "Applied", "Application Update": "Update", "Recruiter / Follow-up": "Recruiter", "Online Assessment": "Assessment", "Interview / Next Stage": "Interview", "Rejected": "Rejection"})
    return df.sort_values("Received Datetime", ascending=False, na_position="last")


def filter_data(df):
    st.sidebar.title("⚙️ Tracker")
    if st.sidebar.button("Refresh now", use_container_width=True, key="refresh_latest"):
        st.cache_data.clear()
        st.rerun()
    if df.empty:
        return df
    min_date = df["Received Datetime"].min().date() if pd.notna(df["Received Datetime"].min()) else date.today()
    max_date = df["Received Datetime"].max().date() if pd.notna(df["Received Datetime"].max()) else date.today()
    selected = st.sidebar.date_input("Date range", (max_date, max_date), min_value=min_date, max_value=max_date, key="date_range_latest_v4")
    start, end = selected if isinstance(selected, tuple) and len(selected) == 2 else (max_date, max_date)
    statuses = st.sidebar.multiselect("Status", [s for s in STATUS_ORDER if s in set(df["Status"])], key="status_v4")
    companies = st.sidebar.multiselect("Company", sorted(df["Company Name"].unique()), key="company_v4")
    query = st.sidebar.text_input("Search company / role / subject", key="search_v4")
    out = df[(df["Date"] >= start) & (df["Date"] <= end)].copy()
    if statuses:
        out = out[out["Status"].isin(statuses)]
    if companies:
        out = out[out["Company Name"].isin(companies)]
    if query.strip():
        q = query.lower().strip()
        hay = (out["Company Name"] + " " + out["Job Role"] + " " + out["Subject"] + " " + out["Notes"]).str.lower()
        out = out[hay.str.contains(re.escape(q), na=False)]
    return out


def show_table(df, key):
    columns = ["Date", "Time", "Priority", "Company Name", "Job Role", "Status", "Action Needed", "Thread Type", "Subject", "Gmail Link", "Notes"]
    view = df[columns].rename(columns={"Company Name": "Company", "Job Role": "Role", "Gmail Link": "Open Email"})
    st.dataframe(view, use_container_width=True, hide_index=True, height=560, key=f"{key}_table", column_config={"Open Email": st.column_config.LinkColumn("Open Email", display_text="Open")})
    st.download_button("Download filtered CSV", view.to_csv(index=False).encode("utf-8"), f"job_applications_{key}.csv", "text/csv", key=f"download_{key}")


def main():
    try:
        df = prepare(load_sheet())
    except Exception as exc:
        st.error("Google Sheet read nahi ho pa raha.")
        st.code(str(exc))
        return
    latest = df["Received Datetime"].max() if not df.empty else pd.NaT
    latest_text = latest.strftime("%d %b %Y, %H:%M") if pd.notna(latest) else "No clean rows yet"
    st.title("📬 Job Application Tracker")
    st.caption(f"Default view: latest available date. Strict interview detection. Latest tracked: {latest_text}")
    data = filter_data(df)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total", len(data), help="selected date range")
    c2.metric("Applied", int((data["Status"] == "Application Applied").sum()) if not data.empty else 0)
    c3.metric("Updates", int((data["Status"] == "Application Update").sum()) if not data.empty else 0)
    c4.metric("Assessments", int((data["Status"] == "Online Assessment").sum()) if not data.empty else 0)
    c5.metric("Interviews", int((data["Status"] == "Interview / Next Stage").sum()) if not data.empty else 0, help="real invites only")
    c6.metric("Rejected", int((data["Status"] == "Rejected").sum()) if not data.empty else 0)
    tabs = st.tabs(["Overview", "Follow-ups", "Applications", "Analytics"])
    with tabs[0]:
        if data.empty:
            st.info("No clean data for the selected date range.")
        else:
            counts = data.groupby("Status", as_index=False).size().rename(columns={"size": "Count"})
            counts["Order"] = counts["Status"].map({status: i for i, status in enumerate(STATUS_ORDER)})
            fig = px.bar(counts.sort_values("Order"), x="Status", y="Count", text="Count", color="Status", color_discrete_map=STATUS_COLORS)
            st.plotly_chart(fig, use_container_width=True, key="overview_chart")
    with tabs[1]:
        show_table(data[data["Action Needed"]], "followups")
    with tabs[2]:
        show_table(data, "applications")
    with tabs[3]:
        if data.empty:
            st.info("No analytics for the selected date range.")
        else:
            daily = data.dropna(subset=["Received Datetime"]).assign(Day=lambda x: x["Received Datetime"].dt.date).groupby(["Day", "Status"], as_index=False).size().rename(columns={"size": "Count"})
            fig = px.area(daily, x="Day", y="Count", color="Status", color_discrete_map=STATUS_COLORS)
            st.plotly_chart(fig, use_container_width=True, key="daily_chart")


if __name__ == "__main__":
    main()
