# MediScribe v1

A deliberately lightweight college-demo medical scribing prototype.

## Features
- Doctor demo login
- Dashboard with live patient/consultation counts
- Patient directory with search and add-patient flow
- Patient consultation history
- Consultation workspace with demo recording
- Local rule-based clinical-note generation with **no API key or external AI credits**
- Save consultation to SQLite
- Copy and print clinical notes

## Run
```bash
pip install -r requirements.txt
uvicorn app:app --reload
```
Then open http://127.0.0.1:8000

Demo login:
- Email: doctor@mediscribe.com
- Password: demo

## Important
This is an educational prototype, not a medical device and not intended for real patient data or clinical decision-making.
