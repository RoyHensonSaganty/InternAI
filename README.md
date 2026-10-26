# InternAI — Internship Discovery + Opt-in Email Alerts

## Included
- React + Vite dashboard
- FastAPI backend
- Himalayas internship listing integration with demo fallback
- Optional Gemini analysis
- Save internships and track application status
- Email subscription form with explicit opt-in (checkbox unchecked by default)
- Gmail SMTP alerts for new matching internships
- Optional MongoDB persistence; in-memory fallback for local demo
- Background check every 6 hours while backend is running

## Start backend (Windows PowerShell)
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `backend/.env` and configure Gmail SMTP before sending real email:
```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
MONGODB_URI=
MONGODB_DATABASE=internai
FRONTEND_ORIGIN=http://localhost:5173
SMTP_EMAIL=yourgmail@gmail.com
SMTP_APP_PASSWORD=your_16_character_gmail_app_password
ALERT_INTERVAL_HOURS=6
```
Use a Google App Password (with 2-Step Verification enabled), not your normal Gmail password. Do not share or commit `.env`.

Then run:
```powershell
uvicorn main:app --reload
```
API docs: http://127.0.0.1:8000/docs

## Start frontend in a second terminal
```powershell
cd frontend
npm install
npm run dev
```
Open the local URL Vite prints, usually http://localhost:5173.

## How opt-in alerts work
1. Open My preferences.
2. Enter an email, skills, and preferred roles.
3. Explicitly tick “I agree to receive internship email alerts”.
4. Click Save preferences.
5. The backend stores the subscription and checks for matching new internships every 6 hours while it is running.
6. Uncheck the consent box and save to unsubscribe.

The backend does not send emails unless the user opts in and SMTP is configured. In-memory subscription data is lost when the backend restarts unless MongoDB is configured. For a real public launch, configure MongoDB, verify email ownership, protect the unsubscribe process, and deploy the API with a reliable scheduler.

## Test email settings
- Set `SMTP_EMAIL` to the Gmail account that will send alerts.
- Create a Google App Password from the Google Account security settings.
- Set `SMTP_APP_PASSWORD` to the app password.
- Never put SMTP secrets in React/frontend code.
- You can test the alert pipeline from http://127.0.0.1:8000/docs using POST `/api/alerts/check`; this sends only to opted-in subscriptions.
- Automatic checks run every `ALERT_INTERVAL_HOURS` hours while the API process is running.

## Important limitations
- Himalayas API access/fields may change; demo listings are used if the live source fails.
- AI uses Gemini only when a valid API key is configured and a request succeeds; otherwise keyword fallback is used.
- This is a college-project MVP, not a production email marketing service. It has no login; email ownership verification is not implemented.
