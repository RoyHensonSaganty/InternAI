import asyncio
import os
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

load_dotenv()

app = FastAPI(title="InternAI API", version="2.0.0")
origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin, "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

mongo_db = None
mongo_collection = None
subscriptions_collection = None
sent_alerts_collection = None
try:
    uri = os.getenv("MONGODB_URI", "").strip()
    if uri:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=2500)
        client.admin.command("ping")
        mongo_db = client[os.getenv("MONGODB_DATABASE", "internai")]
        mongo_collection = mongo_db["applications"]
        subscriptions_collection = mongo_db["subscriptions"]
        sent_alerts_collection = mongo_db["sent_alerts"]
except Exception as exc:
    print(f"MongoDB unavailable; using in-memory storage: {exc}")

memory_applications = []
memory_subscriptions = []
memory_sent_alerts = set()

demo_jobs = [
    {"id": "demo-1", "title": "AI/ML Intern", "company": "Demo AI Labs", "location": "Remote", "employmentType": "Internship", "description": "Work with Python, machine learning, data preprocessing and model evaluation.", "applicationLink": "https://himalayas.app/jobs", "source": "Demo listing"},
    {"id": "demo-2", "title": "Frontend Developer Intern", "company": "WebSpark", "location": "Remote", "employmentType": "Internship", "description": "Build responsive interfaces using HTML, CSS, JavaScript and React.", "applicationLink": "https://himalayas.app/jobs", "source": "Demo listing"},
    {"id": "demo-3", "title": "Python Backend Intern", "company": "CloudNest", "location": "India / Remote", "employmentType": "Internship", "description": "Develop REST APIs in Python, work with databases and write tests.", "applicationLink": "https://himalayas.app/jobs", "source": "Demo listing"},
    {"id": "demo-4", "title": "Generative AI Intern", "company": "NextGen Research", "location": "Remote", "employmentType": "Internship", "description": "Explore LLM APIs, prompt engineering, Python and retrieval-based applications.", "applicationLink": "https://himalayas.app/jobs", "source": "Demo listing"},
]

class AnalyzeRequest(BaseModel):
    title: str = ""
    company: str = ""
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)

class ApplicationCreate(BaseModel):
    job_id: str
    title: str
    company: str = ""
    application_link: str = ""
    status: str = "Saved"

class ApplicationUpdate(BaseModel):
    status: str

class SubscriptionRequest(BaseModel):
    email: EmailStr
    skills: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    email_opt_in: bool = False

def normalize_job(raw: dict, index: int = 0) -> dict:
    title = raw.get("title") or raw.get("name") or "Internship opportunity"
    company = raw.get("companyName") or raw.get("company") or "Company not listed"
    loc = raw.get("locationRestrictions") or raw.get("location") or []
    location = ", ".join(str(x) for x in loc) if isinstance(loc, list) and loc else (str(loc) if loc else "Not specified")
    description = re.sub(r"<[^>]+>", " ", str(raw.get("description") or ""))
    description = re.sub(r"\s+", " ", description).strip()
    return {
        "id": str(raw.get("guid") or raw.get("id") or f"job-{index}-{title}"),
        "title": title, "company": company, "location": location,
        "employmentType": raw.get("employmentType") or "Internship",
        "description": description[:2500],
        "applicationLink": raw.get("applicationLink") or raw.get("url") or raw.get("guid") or "https://himalayas.app/jobs",
        "source": "Himalayas"
    }

async def fetch_jobs(q: str = "intern", limit: int = 25):
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get("https://himalayas.app/jobs/api/search", params={"q": q, "employment_type": "intern", "sort": "recent"})
            response.raise_for_status()
            payload = response.json()
        raw_jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        jobs = [normalize_job(j, i) for i, j in enumerate(raw_jobs[:limit])]
        if jobs:
            return jobs, False
    except Exception as exc:
        print(f"Jobs API unavailable: {exc}")
    filtered = [j for j in demo_jobs if q.lower() in (j["title"] + " " + j["description"] + " " + j["company"]).lower()]
    return (filtered or demo_jobs)[:limit], True

def get_subscriptions():
    if subscriptions_collection is not None:
        return list(subscriptions_collection.find({}, {"_id": 0}))
    return [dict(x) for x in memory_subscriptions]

def find_subscription(email: str):
    normalized = email.strip().lower()
    if subscriptions_collection is not None:
        return subscriptions_collection.find_one({"email": normalized}, {"_id": 0})
    return next((x for x in memory_subscriptions if x["email"] == normalized), None)

def store_subscription(item: dict):
    email = item["email"].strip().lower()
    item["email"] = email
    item["updated_at"] = datetime.now(timezone.utc).isoformat()
    if subscriptions_collection is not None:
        subscriptions_collection.replace_one({"email": email}, item, upsert=True)
    else:
        for idx, existing in enumerate(memory_subscriptions):
            if existing["email"] == email:
                memory_subscriptions[idx] = item
                break
        else:
            memory_subscriptions.append(item)
    return item

def was_sent(email: str, job_id: str) -> bool:
    key = f"{email.lower()}::{job_id}"
    if sent_alerts_collection is not None:
        return sent_alerts_collection.find_one({"key": key}) is not None
    return key in memory_sent_alerts

def mark_sent(email: str, job_id: str):
    key = f"{email.lower()}::{job_id}"
    if sent_alerts_collection is not None:
        sent_alerts_collection.update_one({"key": key}, {"$setOnInsert": {"key": key, "sent_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    else:
        memory_sent_alerts.add(key)

def send_email(to_email: str, subject: str, html: str, text_body: str):
    sender = os.getenv("SMTP_EMAIL", "").strip()
    password = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "").strip()
    if not sender or not password:
        raise RuntimeError("Email is not configured. Set SMTP_EMAIL and SMTP_APP_PASSWORD in backend/.env.")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(sender, password)
        server.send_message(msg)

def job_matches(job: dict, skills: list[str], roles: list[str]):
    searchable = f'{job.get("title","")} {job.get("company","")} {job.get("description","")}'.lower()
    terms = [x.lower().strip() for x in skills + roles if x.strip()]
    matched = [x for x in terms if x in searchable]
    return bool(matched), matched

async def run_alert_check():
    if not os.getenv("SMTP_EMAIL", "").strip() or not os.getenv("SMTP_APP_PASSWORD", "").strip():
        return {"sent": 0, "skipped": 0, "message": "SMTP is not configured; no emails sent."}
    subscriptions = [s for s in get_subscriptions() if s.get("email_opt_in") is True]
    sent, skipped = 0, 0
    for sub in subscriptions:
        jobs, _ = await fetch_jobs("intern", 30)
        for job in jobs:
            if was_sent(sub["email"], job["id"]):
                continue
            matched, terms = job_matches(job, sub.get("skills", []), sub.get("preferred_roles", []))
            if not matched:
                continue
            try:
                score = min(95, 35 + len(set(terms)) * 15) if terms else 50
                html = f"""<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#20243a">
                <h2>InternAI found a matching internship</h2><h3>{job['title']}</h3>
                <p><b>Company:</b> {job['company']}<br><b>Location:</b> {job['location']}<br><b>Estimated keyword match:</b> {score}%</p>
                <p><b>Why it matched:</b> {', '.join(sorted(set(terms)))}</p>
                <p>{job['description'][:600]}</p>
                <p><a href="{job['applicationLink']}" style="display:inline-block;padding:12px 18px;background:#7157d9;color:white;text-decoration:none;border-radius:7px">View internship / Apply</a></p>
                <p style="font-size:12px;color:#777">You received this because you opted in to InternAI email alerts.</p></div>"""
                plain = f"InternAI match: {job['title']} at {job['company']}\nLocation: {job['location']}\nMatched terms: {', '.join(terms)}\nApply: {job['applicationLink']}"
                send_email(sub["email"], f"InternAI match: {job['title']}", html, plain)
                mark_sent(sub["email"], job["id"])
                sent += 1
            except Exception as exc:
                print(f"Could not send alert to {sub['email']}: {exc}")
                skipped += 1
    return {"sent": sent, "skipped": skipped, "opted_in_subscribers": len(subscriptions)}

@app.on_event("startup")
async def start_alert_scheduler():
    async def loop():
        interval = max(1, int(os.getenv("ALERT_INTERVAL_HOURS", "6"))) * 3600
        while True:
            await asyncio.sleep(interval)
            try:
                result = await run_alert_check()
                print(f"InternAI alert check: {result}")
            except Exception as exc:
                print(f"Scheduled alert check failed: {exc}")
    app.state.alert_task = asyncio.create_task(loop())

@app.on_event("shutdown")
async def stop_alert_scheduler():
    task = getattr(app.state, "alert_task", None)
    if task:
        task.cancel()

@app.get("/")
def root():
    return {"message": "InternAI API is running", "docs": "/docs"}

@app.get("/api/health")
def health():
    return {"status": "ok", "database": "MongoDB" if mongo_collection is not None else "in-memory fallback", "smtp_configured": bool(os.getenv("SMTP_EMAIL") and os.getenv("SMTP_APP_PASSWORD"))}

@app.get("/api/jobs")
async def get_jobs(q: str = Query(default="intern", min_length=1), limit: int = Query(default=20, ge=1, le=50)):
    jobs, demo = await fetch_jobs(q, limit)
    return {"jobs": jobs, "source": "Demo data (live API unavailable)" if demo else "Himalayas", "demo": demo}

@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    text = f"{req.title} {req.company} {req.description}".lower()
    user_terms = [s.strip().lower() for s in req.skills if s.strip()]
    role_terms = [s.strip().lower() for s in req.preferred_roles if s.strip()]
    if os.getenv("GEMINI_API_KEY", "").strip():
        try:
            from google import genai
            from google.genai import types
            import json
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            prompt = f"""Analyze this internship for a student. Return JSON with keys match_score (integer 0-100), reason (one short sentence), key_skills (array), missing_skills (array), eligibility_note (string), summary (string). Student skills: {user_terms}. Preferred roles: {role_terms}. Internship: {req.title} at {req.company}. Description: {req.description[:5000]}. Be honest; don't invent eligibility details."""
            result = client.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
            parsed = json.loads(result.text or "{}")
            parsed["match_score"] = max(0, min(100, int(parsed.get("match_score", 50))))
            return parsed
        except Exception as exc:
            print(f"Gemini unavailable; using keyword fallback: {exc}")
    terms = user_terms + role_terms
    matched = sorted({term for term in terms if term and term in text})
    score = min(95, 35 + len(matched) * 15) if terms else 50
    return {"match_score": score, "reason": ("Matches your profile terms: " + ", ".join(matched[:4])) if matched else "Add skills and preferred roles for a more personalized match.", "key_skills": matched[:6] or ["Review the full job description"], "missing_skills": [], "eligibility_note": "Check the official listing for eligibility.", "summary": req.description[:220], "mode": "keyword fallback"}

@app.post("/api/subscriptions")
def save_subscription(req: SubscriptionRequest):
    email = str(req.email).strip().lower()
    # Saving unchecked consent explicitly disables future alerts for this address.
    item = {"email": email, "skills": req.skills, "preferred_roles": req.preferred_roles, "email_opt_in": bool(req.email_opt_in), "consent_updated_at": datetime.now(timezone.utc).isoformat()}
    store_subscription(item)
    return {"message": "Email alerts enabled." if item["email_opt_in"] else "Preferences saved; email alerts are OFF.", "email_opt_in": item["email_opt_in"]}

@app.get("/api/subscriptions/status")
def subscription_status(email: EmailStr):
    sub = find_subscription(str(email).lower())
    if not sub:
        return {"found": False, "email_opt_in": False}
    return {"found": True, "email_opt_in": bool(sub.get("email_opt_in")), "skills": sub.get("skills", []), "preferred_roles": sub.get("preferred_roles", [])}

@app.post("/api/alerts/check")
async def check_alerts_now():
    # Manual test endpoint; only subscriptions with explicit opt-in are eligible.
    return await run_alert_check()

@app.get("/api/applications")
def get_applications():
    if mongo_collection is not None:
        return {"applications": list(mongo_collection.find({}, {"_id": 0}).sort("created_at", -1))}
    return {"applications": memory_applications}

@app.post("/api/applications")
def save_application(app_data: ApplicationCreate):
    item = app_data.model_dump()
    item["id"] = str(uuid4())
    item["created_at"] = datetime.now(timezone.utc).isoformat()
    if mongo_collection is not None:
        existing = mongo_collection.find_one({"job_id": item["job_id"]})
        if existing:
            return {"application": {k: v for k, v in existing.items() if k != "_id"}, "message": "Already saved"}
        mongo_collection.insert_one(item)
    else:
        existing = next((x for x in memory_applications if x["job_id"] == item["job_id"]), None)
        if existing:
            return {"application": existing, "message": "Already saved"}
        memory_applications.insert(0, item)
    return {"application": item, "message": "Saved successfully"}

@app.patch("/api/applications/{application_id}")
def update_application(application_id: str, update: ApplicationUpdate):
    allowed = {"Saved", "Applied", "Interview", "Rejected", "Offer"}
    if update.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(sorted(allowed))}")
    if mongo_collection is not None:
        result = mongo_collection.update_one({"id": application_id}, {"$set": {"status": update.status}})
        if not result.matched_count:
            raise HTTPException(status_code=404, detail="Application not found")
        return {"application": mongo_collection.find_one({"id": application_id}, {"_id": 0})}
    for item in memory_applications:
        if item["id"] == application_id:
            item["status"] = update.status
            return {"application": item}
    raise HTTPException(status_code=404, detail="Application not found")
