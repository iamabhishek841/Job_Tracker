import re
from datetime import date, timedelta, datetime
from urllib.parse import quote_plus

import pandas as pd
import plotly.express as px
import streamlit as st

SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", "https://docs.google.com/spreadsheets/d/18AYYaEv450ZGQBwBOw6oODQs-qlJxVp3LetJ70-Lmt8/edit?usp=sharing")
SHEET_NAME = st.secrets.get("GOOGLE_SHEET_NAME", "Job Applications")
COMPANY_DB = "data/companies.csv"

st.set_page_config(page_title="Job Application Tracker", page_icon="📬", layout="wide")

STATUS_ORDER = ["Application Applied", "Application Update", "Recruiter / Follow-up", "Online Assessment", "Interview / Next Stage", "Rejected"]
STATUS_COLORS = {"Application Applied":"#2563eb","Application Update":"#64748b","Recruiter / Follow-up":"#7c3aed","Online Assessment":"#f59e0b","Interview / Next Stage":"#10b981","Rejected":"#ef4444"}
NOISE = ["newsletter","job alert","jobs alert","recommended jobs","top employers","company spotlights","discover your path","contest","streak","unsubscribe","how to use neetcode","get ready for interv"]
GENERIC_COMPANIES = {"codesignal","leetcode","neetcode","hello","mail","comms","unknown"}
INTERVIEW_STRICT = [
    "interview invite",
    "interview invitation",
    "invited to interview",
    "invite you to interview",
    "selected for interview",
    "shortlisted for interview",
    "schedule your interview",
    "book your interview",
    "select a time for your interview",
    "choose a time for your interview",
    "availability for interview",
    "technical screen",
    "phone screen",
    "recruiter screen",
    "technical interview",
    "onsite interview",
    "final interview"
]
INTERVIEW_FALSE_POSITIVE = [
    "we will contact you to schedule an interview",
    "we will contact you to schedule",
    "if your qualifications match",
    "if your profile matches",
    "if your experience matches",
    "currently reviewing your candidacy",
    "currently reviewing your application",
    "reviewing your candidacy",
    "reviewing your application",
    "review process may take some time",
    "in the meantime"
]
ASSESSMENT_STRICT = ["online assessment","coding assessment","technical assessment","take the assessment","complete the assessment","assessment invite","test invite","coding test","complete your test"]
SOURCES = ["LinkedIn","IrishJobs","Indeed","Jobs.ie","Career Page","Greenhouse","Lever","Ashby","Workday","Wellfound / YC"]
JOB_TYPES = ["Backend Engineer","Platform Engineer","Software Engineer","Cloud Software Engineer","Data Platform Engineer","Data Engineer","ML Platform Engineer","MLOps Engineer","Site Reliability Engineer"]
ROLE_QUERY = {"Backend Engineer":"Backend Engineer OR Backend Software Engineer OR Software Engineer","Platform Engineer":"Platform Engineer OR Cloud Platform Engineer","Software Engineer":"Software Engineer"}

def sheet_id(url):
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", str(url))
    return m.group(1) if m else str(url).strip()

@st.cache_data(ttl=600, show_spinner=False)
def load_data():
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id(SHEET_URL)}/gviz/tq?tqx=out:csv&sheet={quote_plus(SHEET_NAME)}"
    df = pd.read_csv(url)
    df.columns = [str(c).strip() for c in df.columns]
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_companies():
    try:
        return pd.read_csv(COMPANY_DB).fillna("")
    except Exception:
        return pd.DataFrame(columns=["company_name","company_type","ireland_locations","career_url","ats_type","sponsor_likelihood","notes"])

def has(text, terms): 
    return any(term in text for term in terms)

def row_text(row): 
    return " ".join(str(row.get(c,"")) for c in ["Email Type / Status","Subject","Notes","Sender","Company Name","Job Role"]).lower()

def real_assessment(text):
    context = ["application","role","position","recruit","hiring","graduate","engineer","analyst","software"]
    return has(text,ASSESSMENT_STRICT) and has(text,context) and not has(text,NOISE)

def real_interview(text):
    if has(text, INTERVIEW_FALSE_POSITIVE):
        return False
    return has(text, INTERVIEW_STRICT) and not has(text, NOISE)

def status_for(row):
    text = row_text(row)
    raw_status = str(row.get("Email Type / Status","")).lower()
    if has(text,["not selected","not moving forward","unsuccessful","regret to inform","unfortunately"]): 
        return "Rejected"
    if real_assessment(text): 
        return "Online Assessment"
    if real_interview(text): 
        return "Interview / Next Stage"
    if has(text,["recruiter","talent acquisition","hiring team","follow-up","follow up"]): 
        return "Recruiter / Follow-up"
    if has(text,["thank you for applying","thanks for applying","application received","has been received","we received your application","your application to"]): 
        return "Application Applied"
    if "interview" in raw_status: 
        return "Application Update"
    return "Application Update"

def keep(row):
    text = row_text(row)
    company = str(row.get("Company Name","")).lower().strip()
    subject = str(row.get("Subject","")).lower().strip()
    if has(text,NOISE): 
        return False
    if company in GENERIC_COMPANIES and not real_assessment(text): 
        return False
    if subject in {"keep track of your application","thank you for applying!","reset password link","reset link"}: 
        return False
    strong = ["thank you for applying","thanks for applying","application received","has been received","we received your application","your application to","not selected","not moving forward","unsuccessful"]
    return has(text,strong) or real_assessment(text) or real_interview(text)

def role_for(row):
    current = str(row.get("Job Role","")).strip()
    subject = str(row.get("Subject","")).strip()
    if current and current.lower() not in {"unknown","latest","role. in the"}: 
        return current
    patterns = [
        r"role of\s+(.+?)(?:$|\.|,|\-| at )",
        r"for the role of\s+(.+?)(?:$|\.|,|\-| at )",
        r"for the\s+(.+?)\s+(?:role|position)",
        r"application for\s+(.+?)(?:$|\.|,| at )"
    ]
    for pattern in patterns:
        match = re.search(pattern,subject,flags=re.I)
        if match:
            value = match.group(1).strip(" .,-")
            if 3 <= len(value) <= 90: 
                return value
    return "Unknown"

def prepare(df):
    defaults = {"Tracked At":"","Received Date":"","Received Time":"","Company Name":"Unknown","Job Role":"Unknown","Email Type / Status":"Unknown","Sender":"","Subject":"","Gmail Link":"","Notes":""}
    df = df.copy()
    for col, default in defaults.items():
        if col not in df.columns: 
            df[col] = default
        df[col] = df[col].fillna(default).astype(str).str.strip()
    df["Company Name"] = df["Company Name"].replace("","Unknown")
    df["Job Role"] = df.apply(role_for,axis=1)
    dt = (df["Received Date"] + " " + df["Received Time"]).str.strip()
    df["Received Datetime"] = pd.to_datetime(dt,errors="coerce")
    df.loc[df["Received Datetime"].isna(),"Received Datetime"] = pd.to_datetime(df["Received Date"],errors="coerce")
    df["Date"] = df["Received Datetime"].dt.date
    df["Time"] = df["Received Datetime"].dt.strftime("%H:%M").fillna("")
    df = df[df.apply(keep,axis=1)].copy()
    df["Status"] = df.apply(status_for,axis=1)
    df["Action Needed"] = df["Status"].isin(["Recruiter / Follow-up","Online Assessment","Interview / Next Stage"])
    df["Priority"] = df["Status"].map({"Interview / Next Stage":"High","Online Assessment":"Medium","Recruiter / Follow-up":"Medium"}).fillna("Normal")
    df["Thread Type"] = df["Status"].map({"Application Applied":"Applied","Application Update":"Update","Recruiter / Follow-up":"Recruiter","Online Assessment":"Assessment","Interview / Next Stage":"Interview"})
    df["Deadline"] = ""
    return df.sort_values("Received Datetime",ascending=False,na_position="last")

def filter_data(df):
    st.sidebar.title("⚙️ Tracker")
    if st.sidebar.button("Refresh now",use_container_width=True): 
        st.cache_data.clear()
        st.rerun()
    if df.empty: 
        return df
    min_date = df["Received Datetime"].min().date() if pd.notna(df["Received Datetime"].min()) else date.today()-timedelta(days=30)
    max_date = df["Received Datetime"].max().date() if pd.notna(df["Received Datetime"].max()) else date.today()
    today = date.today()

    min_picker_date = min(min_date, today)
    max_picker_date = max(max_date, today)

    selected = st.sidebar.date_input(
        "Date range",
        (today, today),
        min_value=min_picker_date,
        max_value=max_picker_date,
        key="date_range_filter"
    )
    start,end = selected if isinstance(selected,tuple) and len(selected)==2 else (min_date,max_date)
    statuses = st.sidebar.multiselect("Status",[s for s in STATUS_ORDER if s in set(df["Status"])])
    companies = st.sidebar.multiselect("Company",sorted(df["Company Name"].unique()))
    query = st.sidebar.text_input("Search company / role / subject")
    out = df[(df["Date"]>=start)&(df["Date"]<=end)].copy()
    if statuses: 
        out = out[out["Status"].isin(statuses)]
    if companies: 
        out = out[out["Company Name"].isin(companies)]
    if query.strip():
        q = query.lower().strip()
        hay = (out["Company Name"]+" "+out["Job Role"]+" "+out["Subject"]+" "+out["Notes"]).str.lower()
        out = out[hay.str.contains(re.escape(q),na=False)]
    return out

def show_table(df,key):
    cols = ["Date","Time","Priority","Company Name","Job Role","Status","Action Needed","Thread Type","Subject","Gmail Link","Notes"]
    display = df[cols].rename(columns={"Company Name":"Company","Job Role":"Role","Gmail Link":"Open Email"})
    st.dataframe(display,use_container_width=True,hide_index=True,height=560,key=f"{key}_table",column_config={"Open Email":st.column_config.LinkColumn("Open Email",display_text="Open")})
    st.download_button("Download filtered CSV",display.to_csv(index=False).encode("utf-8"),f"job_applications_{key}.csv","text/csv",key=f"{key}_download")

def select_all_reset(prefix, options):
    c1,c2 = st.columns(2)
    with c1:
        if st.button("Select all",key=f"{prefix}_all",use_container_width=True): 
            st.session_state[f"{prefix}_selected"] = options
            st.rerun()
    with c2:
        if st.button("Reset",key=f"{prefix}_reset",use_container_width=True): 
            st.session_state[f"{prefix}_selected"] = []
            st.rerun()

def make_url(source, query):
    if source == "LinkedIn": 
        return f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query)}&location=Ireland"
    if source == "IrishJobs": 
        return f"https://www.irishjobs.ie/jobs?keywords={quote_plus(query)}&location=Ireland"
    if source == "Indeed": 
        return f"https://ie.indeed.com/jobs?q={quote_plus(query)}&l=Ireland"
    if source == "Jobs.ie": 
        return f"https://www.jobs.ie/jobs?keywords={quote_plus(query)}&location=Ireland"
    return f"https://www.google.com/search?q={quote_plus(query)}"

def build_search_rows(sources, companies, roles, location):
    loc = "Ireland" if location == "All Ireland" else location
    rows = []
    for _, c in companies.iterrows():
        company = str(c.get("company_name","")).strip()
        career = str(c.get("career_url","")).strip()
        for role in roles:
            role_query = ROLE_QUERY.get(role, role)
            for source in sources:
                if source == "Career Page": 
                    query = f'{company} careers {loc} ({role_query})'
                    url = make_url("Google",query)
                elif source in {"Greenhouse","Lever","Ashby","Workday"}:
                    site = {"Greenhouse":"boards.greenhouse.io","Lever":"jobs.lever.co","Ashby":"ashbyhq.com","Workday":"myworkdayjobs.com"}[source]
                    query = f'site:{site} {company} {loc} ({role_query})'
                    url = make_url("Google",query)
                elif source == "Wellfound / YC": 
                    query = f'({company} OR {loc}) ({role_query}) (site:wellfound.com OR site:ycombinator.com/jobs)'
                    url = make_url("Google",query)
                else: 
                    query = f'{company} {role_query} {loc}'
                    url = make_url(source,query)
                rows.append({"Source":source,"Company":company,"Job Type":role,"Search Link":url,"Career URL":career})
    return pd.DataFrame(rows)

def job_finder_tab():
    st.subheader("🎯 Ireland Job Finder")
    companies = load_companies()
    if companies.empty: 
        st.warning("Company database not found.")
        return
    location = st.selectbox("Location",["All Ireland","Dublin","Cork","Galway","Limerick","Remote Ireland"])
    st.markdown("**1) Select sources**")
    st.session_state.setdefault("sources_selected",["Career Page","Greenhouse","Lever","Workday","IrishJobs","Indeed","LinkedIn"])
    select_all_reset("sources",SOURCES)
    selected_sources = st.session_state.get("sources_selected",[])
    
    st.markdown("**2) Select companies**")
    company_options = companies["company_name"].dropna().tolist()
    st.session_state.setdefault("companies_selected",company_options[:10])
    select_all_reset("companies",company_options)
    selected_names = st.session_state.get("companies_selected",[])
    
    st.markdown("**3) Select job types**")
    st.session_state.setdefault("roles_selected",["Backend Engineer","Platform Engineer","Software Engineer","Data Platform Engineer","ML Platform Engineer"])
    select_all_reset("roles",JOB_TYPES)
    selected_roles = st.session_state.get("roles_selected",[])
    
    selected_companies = companies[companies["company_name"].isin(selected_names)]
    if st.button("Generate search links",use_container_width=True):
        if not selected_sources or not selected_names or not selected_roles: 
            st.error("At least one source, company and job type select karo.")
        else: 
            st.session_state["search_rows"] = build_search_rows(selected_sources,selected_companies,selected_roles,location)
    rows = st.session_state.get("search_rows",pd.DataFrame())
    if not rows.empty:
        st.success(f"{len(rows)} search links generated.")
        st.dataframe(rows,use_container_width=True,hide_index=True,height=520,column_config={"Search Link":st.column_config.LinkColumn("Open Search",display_text="Open")})
    else: 
        st.info("Filters select karo, phir Generate search links dabao.")
    st.markdown("**Company database**")
    st.dataframe(companies,use_container_width=True,hide_index=True,height=320,column_config={"career_url":st.column_config.LinkColumn("Career URL")})

def main():
    try: 
        df = prepare(load_data())
    except Exception as exc: 
        st.error("Google Sheet read nahi ho pa raha.")
        st.code(str(exc))
        return
    latest = df["Received Datetime"].max() if not df.empty else pd.NaT
    latest_text = latest.strftime("%d %b %Y, %H:%M") if pd.notna(latest) else "No clean rows yet"
    st.title("📬 Job Application Tracker")
    st.caption(f"Strict interview detection + Ireland Job Finder. Latest tracked: {latest_text}")
    filtered = filter_data(df)
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: 
        st.metric("Total",len(filtered),help="clean rows")
    with c2: 
        st.metric("Applied",int((filtered["Status"]=="Application Applied").sum()) if not filtered.empty else 0,help="confirmations")
    with c3: 
        st.metric("Updates",int((filtered["Status"]=="Application Update").sum()) if not filtered.empty else 0,help="updates")
    with c4: 
        st.metric("Assessments",int((filtered["Status"]=="Online Assessment").sum()) if not filtered.empty else 0,help="tests")
    with c5: 
        st.metric("Interviews",int((filtered["Status"]=="Interview / Next Stage").sum()) if not filtered.empty else 0,help="strict invites only")
    with c6: 
        st.metric("Rejected",int((filtered["Status"]=="Rejected").sum()) if not filtered.empty else 0,help="closed")
    tabs = st.tabs(["Overview","Follow-ups","Applications","Analytics","Job Finder"])
    with tabs[0]:
        if filtered.empty: 
            st.info("No clean data yet.")
        else:
            counts = filtered.groupby("Status",as_index=False).size().rename(columns={"size":"Count"})
            fig = px.bar(counts,x="Status",y="Count",text="Count",color="Status",color_discrete_map=STATUS_COLORS)
            st.plotly_chart(fig,use_container_width=True)
    with tabs[1]: 
        show_table(filtered[filtered["Action Needed"]],"followups")
    with tabs[2]: 
        show_table(filtered,"applications")
    with tabs[3]:
        if filtered.empty: 
            st.info("No analytics yet.")
        else:
            daily = filtered.dropna(subset=["Received Datetime"]).assign(Day=lambda z:z["Received Datetime"].dt.date).groupby(["Day","Status"],as_index=False).size().rename(columns={"size":"Count"})
            fig2 = px.line(daily,x="Day",y="Count",color="Status",color_discrete_map=STATUS_COLORS)
            st.plotly_chart(fig2,use_container_width=True)
    with tabs[4]: 
        job_finder_tab()

if __name__ == "__main__": 
    main()
