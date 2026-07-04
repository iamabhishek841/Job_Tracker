# Job Application Tracker Dashboard

A responsive Streamlit dashboard for Gmail to Google Sheet job application tracking, now with an Ireland Job Finder tab.

## What it shows

- Total tracked emails
- Action needed emails
- Online assessments
- Interview / next-stage emails
- Recruiter follow-ups
- Rejections
- Company timeline
- Weekly analytics
- CSV download
- Job Finder with ATS, Irish job board, startup and LinkedIn search links
- Sponsor-likely company portal database

## Data source

The app reads the Job Applications tab from your Google Sheet.

For the app to read it directly, set sharing to: Anyone with the link -> Viewer

## Run locally

pip install -r requirements.txt

streamlit run app.py

## Streamlit Cloud deploy

Repository: iamabhishek841/Job_Tracker

Branch: master

Main file path: app.py

LinkedIn is not scraped. The app only generates LinkedIn search links.
