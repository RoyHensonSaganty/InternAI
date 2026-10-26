import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Search, Sparkles, Bookmark, BriefcaseBusiness, MapPin, ArrowUpRight, RefreshCw, LayoutDashboard, Settings2, CheckCircle2, BrainCircuit, X, Mail, BellRing } from "lucide-react";
import "./styles.css";

const API = "http://127.0.0.1:8000";
const defaultSkills = "Python, JavaScript, React, HTML, CSS, AI/ML";
const defaultRoles = "AI Intern, Python Developer, Frontend Developer";

function App() {
  const [jobs, setJobs] = useState([]);
  const [saved, setSaved] = useState([]);
  const [analyses, setAnalyses] = useState({});
  const [query, setQuery] = useState("intern");
  const [skills, setSkills] = useState(localStorage.getItem("internai_skills") || defaultSkills);
  const [roles, setRoles] = useState(localStorage.getItem("internai_roles") || defaultRoles);
  const [email, setEmail] = useState(localStorage.getItem("internai_email") || "");
  const [emailOptIn, setEmailOptIn] = useState(localStorage.getItem("internai_email_opt_in") === "true");
  const [active, setActive] = useState("Discover");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [demo, setDemo] = useState(false);
  const [showPrefs, setShowPrefs] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);

  const skillList = useMemo(() => skills.split(",").map(s => s.trim()).filter(Boolean), [skills]);
  const roleList = useMemo(() => roles.split(",").map(s => s.trim()).filter(Boolean), [roles]);

  async function loadSaved() {
    try { const r = await fetch(`${API}/api/applications`); const d = await r.json(); setSaved(d.applications || []); }
    catch { setNotice("Backend is offline. Start FastAPI in the backend folder."); }
  }
  async function loadJobs(search = query) {
    setLoading(true); setNotice("");
    try {
      const r = await fetch(`${API}/api/jobs?q=${encodeURIComponent(search || "intern")}&limit=25`);
      const d = await r.json(); setJobs(d.jobs || []); setDemo(Boolean(d.demo));
      if (d.demo) setNotice("Showing demo listings because the live job source was unavailable.");
    } catch { setJobs([]); setNotice("Cannot connect to backend. Start FastAPI at http://127.0.0.1:8000."); }
    finally { setLoading(false); }
  }
  useEffect(() => { loadJobs("intern"); loadSaved(); }, []);

  async function analyze(job) {
    if (analyses[job.id]) return;
    setAnalyses(old => ({ ...old, [job.id]: { loading: true } }));
    try {
      const r = await fetch(`${API}/api/analyze`, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({title:job.title,company:job.company,description:job.description,skills:skillList,preferred_roles:roleList}) });
      if (!r.ok) throw new Error("Analysis failed");
      const data = await r.json(); setAnalyses(old => ({ ...old, [job.id]: data }));
    } catch { setAnalyses(old => ({ ...old, [job.id]: { match_score: 0, reason: "Could not analyze this listing. Check the backend.", key_skills: [] } })); }
  }
  async function saveJob(job) {
    try {
      const r = await fetch(`${API}/api/applications`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({job_id:job.id,title:job.title,company:job.company,application_link:job.applicationLink,status:"Saved"})});
      const d = await r.json(); await loadSaved(); setNotice(d.message || "Internship saved.");
    } catch { setNotice("Could not save. Check whether the backend is running."); }
  }
  async function changeStatus(app, status) {
    try { await fetch(`${API}/api/applications/${app.id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({status})}); await loadSaved(); }
    catch { setNotice("Could not update application status."); }
  }
  async function savePreferences() {
    if (!email.trim()) { setNotice("Enter an email address to save email preferences."); return; }
    setSavingPrefs(true);
    try {
      const r = await fetch(`${API}/api/subscriptions`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:email.trim(),skills:skillList,preferred_roles:roleList,email_opt_in:emailOptIn})});
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Could not save preferences");
      localStorage.setItem("internai_skills",skills); localStorage.setItem("internai_roles",roles);
      localStorage.setItem("internai_email",email.trim()); localStorage.setItem("internai_email_opt_in",String(emailOptIn));
      setAnalyses({}); setShowPrefs(false); setNotice(data.message);
    } catch (e) { setNotice(`Could not save preferences: ${e.message}`); }
    finally { setSavingPrefs(false); }
  }
  const savedIds = new Set(saved.map(s => s.job_id));

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><BrainCircuit size={23}/></div><div><b>InternAI</b><small>CAREER INTELLIGENCE</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      <button className={`nav-item ${active === "Discover" ? "active" : ""}`} onClick={() => setActive("Discover")}><LayoutDashboard size={18}/> Discover internships</button>
      <button className={`nav-item ${active === "Saved" ? "active" : ""}`} onClick={() => setActive("Saved")}><Bookmark size={18}/> Saved & tracker <span className="nav-count">{saved.length}</span></button>
      <button className="nav-item" onClick={() => setShowPrefs(true)}><Settings2 size={18}/> My preferences</button>
      <div className="sidebar-bottom"><div className="ai-mark"><Sparkles size={16}/><span>AI-powered matching</span></div><small>Find your next opportunity.</small></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <b>{active}</b></div><button className="profile" onClick={() => setShowPrefs(true)}><span className="avatar">S</span><span><b>Student workspace</b><small>Personalize your matches</small></span></button></header>
      <section className="welcome"><div><div className="eyebrow"><Sparkles size={14}/> YOUR NEXT CHAPTER STARTS HERE</div><h1>{active === "Saved" ? "Your career tracker." : "Find work that fits you."}</h1><p>{active === "Saved" ? "Keep every opportunity and application organized in one place." : "Discover internships matched to your skills, interests, and ambitions."}</p></div><div className="welcome-art"><div className="orbit orbit-one"></div><div className="orbit orbit-two"></div><div className="art-core"><BrainCircuit size={38}/></div><Sparkles className="spark spark-a" size={20}/><Sparkles className="spark spark-b" size={15}/></div></section>
      <section className="stats">
        <div className="stat-card"><div className="stat-icon purple"><BriefcaseBusiness size={19}/></div><div><small>Opportunities found</small><strong>{jobs.length}</strong><span>From internship listings</span></div></div>
        <div className="stat-card"><div className="stat-icon blue"><Bookmark size={19}/></div><div><small>Saved opportunities</small><strong>{saved.length}</strong><span>In your tracker</span></div></div>
        <div className="stat-card"><div className="stat-icon green"><CheckCircle2 size={19}/></div><div><small>Applications sent</small><strong>{saved.filter(s => s.status !== "Saved").length}</strong><span>Tracked applications</span></div></div>
      </section>
      {notice && <div className="notice"><span>{notice}</span><button onClick={() => setNotice("")} aria-label="Dismiss"><X size={15}/></button></div>}
      <section className="section-heading"><div><h2>{active === "Saved" ? "Saved internships" : "Explore opportunities"}</h2><p>{active === "Saved" ? "Update the status as you progress." : "Review listings and use AI to understand your match."}</p></div><button className="secondary-btn" onClick={() => loadJobs()} disabled={loading}><RefreshCw size={15} className={loading ? "spin" : ""}/> Refresh</button></section>
      {active === "Discover" && <form className="searchbar" onSubmit={e => {e.preventDefault();loadJobs(query);}}><Search size={19}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search AI, Python, frontend..."/><button type="submit" disabled={loading}>{loading ? "Searching..." : "Search jobs"}</button></form>}
      {active === "Saved" && saved.length > 0 && <div className="tracker-list">{saved.map(app => <div className="tracker-row" key={app.id}><div className="company-mark">{(app.company || "C").slice(0,1).toUpperCase()}</div><div className="tracker-info"><b>{app.title}</b><small>{app.company}</small></div><select value={app.status} onChange={e => changeStatus(app,e.target.value)}><option>Saved</option><option>Applied</option><option>Interview</option><option>Rejected</option><option>Offer</option></select>{app.application_link && <a href={app.application_link} target="_blank" rel="noreferrer">Open <ArrowUpRight size={14}/></a>}</div>)}</div>}
      {active === "Saved" && saved.length === 0 && <div className="empty"><Bookmark size={30}/><h3>No saved internships yet</h3><p>Go to Discover internships and save opportunities you like.</p><button onClick={() => setActive("Discover")}>Discover internships</button></div>}
      {active === "Discover" && <div className="job-grid">{jobs.map(job => {
        const analysis = analyses[job.id]; const score = analysis && !analysis.loading ? analysis.match_score : null;
        return <article className="job-card" key={job.id}>
          <div className="job-card-top"><div className="company-mark">{(job.company || "C").slice(0,1).toUpperCase()}</div><div className="source-pill">{job.source || "Internship"}</div><button className={`bookmark-btn ${savedIds.has(job.id) ? "bookmarked" : ""}`} onClick={() => saveJob(job)} title="Save internship"><Bookmark size={18} fill={savedIds.has(job.id) ? "currentColor" : "none"}/></button></div>
          <h3>{job.title}</h3><div className="company-name">{job.company}</div><div className="job-meta"><span><MapPin size={14}/>{job.location || "Location not specified"}</span><span><BriefcaseBusiness size={14}/>{job.employmentType || "Internship"}</span></div>
          <p className="job-description">{job.description || "Open the original listing to view the full description and requirements."}</p>
          {analysis && !analysis.loading && <div className="analysis-box"><div className="match-head"><span><Sparkles size={14}/> AI MATCH</span><b>{score}%</b></div><div className="score-track"><div style={{width:`${score}%`}}/></div><p>{analysis.reason}</p>{analysis.key_skills?.length > 0 && <div className="skill-tags">{analysis.key_skills.slice(0,4).map(s=><span key={s}>{s}</span>)}</div>}</div>}
          {analysis?.loading && <div className="analyzing"><span className="loader"/> Analyzing with AI...</div>}
          <div className="card-actions"><button className="analyze-btn" onClick={() => analyze(job)} disabled={Boolean(analysis)}><Sparkles size={15}/>{analysis ? (analysis.loading ? "Analyzing..." : "Analyzed") : "Analyze match"}</button><a className="apply-btn" href={job.applicationLink || "https://himalayas.app/jobs"} target="_blank" rel="noreferrer">Apply <ArrowUpRight size={15}/></a></div>
        </article>;
      })}</div>}
      <footer><span>InternAI <b>•</b> AI-Powered Internship Discovery</span><span>{emailOptIn ? "Email alerts opted in" : "Email alerts off"}{demo ? " · Demo listings" : " · Live source"}</span></footer>
    </main>
    {showPrefs && <div className="modal-backdrop" onClick={() => setShowPrefs(false)}><div className="modal" onClick={e => e.stopPropagation()}>
      <div className="modal-head"><div><div className="eyebrow"><Settings2 size={14}/> PERSONALIZE</div><h2>Your preferences</h2></div><button className="close-btn" onClick={() => setShowPrefs(false)}><X size={19}/></button></div>
      <p className="modal-copy">No account required. Enter your email and choose whether you want matching internship alerts.</p>
      <label>Email address</label><input className="pref-input" type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" required/>
      <label>Skills you know (comma-separated)</label><textarea rows="3" value={skills} onChange={e=>setSkills(e.target.value)} placeholder="Python, React, SQL, Machine Learning"/>
      <label>Preferred internship roles (comma-separated)</label><textarea rows="3" value={roles} onChange={e=>setRoles(e.target.value)} placeholder="AI Intern, Frontend Developer"/>
      <label className="consent"><input type="checkbox" checked={emailOptIn} onChange={e=>setEmailOptIn(e.target.checked)}/><span><b>Yes, email me matching internship alerts.</b><small>Unchecked by default. You can turn alerts off any time by unchecking this box and saving.</small></span></label>
      <div className="modal-actions"><button className="secondary-btn" onClick={()=>setShowPrefs(false)}>Cancel</button><button className="primary-btn" onClick={savePreferences} disabled={savingPrefs}>{savingPrefs ? "Saving..." : "Save preferences"}</button></div>
    </div></div>}
  </div>;
}
createRoot(document.getElementById("root")).render(<App />);
