# Job Application Tracker Dashboard

A responsive Streamlit dashboard for the Gmail -> Google Sheet job application tracker.

## What it shows

- Total tracked emails
- Applications in the last 7 days
- Action needed emails
- Online assessments
- Interview / next-stage emails
- Recruiter follow-ups
- Rejections
- Company timeline
- Weekly analytics
- CSV download

## Data source

The app reads the `Job Applications` tab from your Google Sheet.

For the app to read it directly, set sharing to:

`Anyone with the link -> Viewer`

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Cloud deploy

1. Go to Streamlit Community Cloud
2. New app
3. Repository: `iamabhishek841/Dashboard_AD`
4. Branch: `master`
5. Main file path: `streamlit_app.py`
6. Deploy

Optional secrets:

```toml
GOOGLE_SHEET_URL = "your_google_sheet_url"
GOOGLE_SHEET_NAME = "Job Applications"
```
