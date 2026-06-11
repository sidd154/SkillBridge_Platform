from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List
from app.services.supabase import get_supabase
from app.services.auth_middleware import require_candidate
from app.agents.graphs.passport_issuer_graph import passport_issuer_graph
from app.config import settings
import datetime
import asyncio

router = APIRouter(prefix="/tests", tags=["tests"])

@router.get("/job/{job_id}/mcqs")
def get_job_mcqs(job_id: str, user: dict = Depends(require_candidate)):
    client = get_supabase()
    user_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    is_demo = False
    if user_id == "00000000-0000-0000-0000-000000000001" or not client:
        is_demo = True
    else:
        # Check if job is in demo jobs first
        demo_jobs = session_store.get_session(f"demo_jobs_{settings.DEMO_RECRUITER_ID}") or []
        if any(j.get("id") == job_id for j in demo_jobs):
            is_demo = True
            
    if is_demo:
        brief = session_store.get_session(f"brief:{job_id}")
        mcqs = brief.get("mass_mcqs") if brief else None
        if not mcqs:
            # Fallback mock questions
            mcqs = [
                {
                    "question": "What hook would you use to perform side effects in React?",
                    "options": {"A": "useState", "B": "useEffect", "C": "useContext", "D": "useMemo"},
                    "correct_answer": "B"
                },
                {
                    "question": "Which of the following is true about TypeScript?",
                    "options": {"A": "It is a superset of JavaScript", "B": "It has static typing", "C": "It compiles to clean JS", "D": "All of the above"},
                    "correct_answer": "D"
                },
                {
                    "question": "Which Tailwind class is used to apply a display flex?",
                    "options": {"A": "flex-row", "B": "display-flex", "C": "flex", "D": "flex-box"},
                    "correct_answer": "C"
                },
                {
                    "question": "In Python, what keyword defines a function?",
                    "options": {"A": "func", "B": "function", "C": "def", "D": "define"},
                    "correct_answer": "C"
                },
                {
                    "question": "What is FastAPI used for?",
                    "options": {"A": "Building frontend apps", "B": "CSS styling", "C": "Web APIs in Python", "D": "Database migration"},
                    "correct_answer": "C"
                }
            ]
        
        # Strip answers
        sanitized_mcqs = []
        for q in mcqs:
            sanitized_mcqs.append({
                "question": q.get("question"),
                "options": q.get("options")
            })
        return {"questions": sanitized_mcqs}
    # --- DEMO BYPASS END ---
    
    resp = client.table("job_briefs").select("mass_mcqs").eq("job_id", job_id).single().execute()
    if not resp.data or not resp.data.get("mass_mcqs"):
        raise HTTPException(status_code=404, detail="No MCQs found for this job")
        
    mcqs = resp.data["mass_mcqs"]
    # Strip answers
    sanitized_mcqs = []
    for q in mcqs:
        sanitized_mcqs.append({
            "question": q.get("question"),
            "options": q.get("options")
        })
    return {"questions": sanitized_mcqs}

class JobAnswersModel(BaseModel):
    answers: Dict[str, str]

@router.post("/job/{job_id}/submit")
def submit_job_mcqs(job_id: str, data: JobAnswersModel, user: dict = Depends(require_candidate)):
    client = get_supabase()
    user_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    is_demo = False
    if user_id == "00000000-0000-0000-0000-000000000001" or not client:
        is_demo = True
    else:
        # Check if job is in demo jobs first
        demo_jobs = session_store.get_session(f"demo_jobs_{settings.DEMO_RECRUITER_ID}") or []
        if any(j.get("id") == job_id for j in demo_jobs):
            is_demo = True
            
    if is_demo:
        mcq_score = 0.0
        brief = session_store.get_session(f"brief:{job_id}")
        mcqs = brief.get("mass_mcqs") if brief else None
        if not mcqs:
            # Match the hardcoded mock questions
            mcqs = [
                {"correct_answer": "B"},
                {"correct_answer": "D"},
                {"correct_answer": "C"},
                {"correct_answer": "C"},
                {"correct_answer": "C"}
            ]
        correct = 0
        total = len(mcqs)
        for i, q in enumerate(mcqs):
            cand_answer = data.answers.get(str(i))
            if cand_answer and cand_answer == q.get("correct_answer"):
                correct += 1
        if total > 0:
            mcq_score = (correct / total) * 100
            
        # Update application in session_store
        apps = session_store.get_session(f"applications:{user_id}") or []
        for app in apps:
            if app.get("job_id") == job_id:
                app["mcq_score"] = mcq_score
                app["status"] = "test_completed"
        session_store.save_session(f"applications:{user_id}", apps)
        return {"message": "Test evaluated", "score": mcq_score}
    # --- DEMO BYPASS END ---
    
    # Calculate MCQ Score
    mcq_score = 0.0
    brief_resp = client.table("job_briefs").select("mass_mcqs").eq("job_id", job_id).single().execute()
    if brief_resp.data and brief_resp.data.get("mass_mcqs"):
        mcqs = brief_resp.data["mass_mcqs"]
        correct = 0
        total = len(mcqs)
        for i, q in enumerate(mcqs):
            cand_answer = data.answers.get(str(i))
            if cand_answer and cand_answer == q.get("correct_answer"):
                correct += 1
        if total > 0:
            mcq_score = (correct / total) * 100
            
    # Update application
    client.table("applications").update({"mcq_score": mcq_score, "status": "test_completed"}).eq("job_id", job_id).eq("candidate_id", user_id).execute()
    
    return {"message": "Test evaluated", "score": mcq_score}



class ConsentModel(BaseModel):
    consent: bool

class AnswersModel(BaseModel):
    answers: Dict[str, str]

@router.get("/{session_id}")
def get_test_session(session_id: str, user: dict = Depends(require_candidate)):
    # Check in-memory session store first (used for demo user)
    from app.services import session_store
    cached = session_store.get_session(session_id)
    if cached:
        return cached
    
    user_id = user["user_id"]
    client = get_supabase()
    resp = client.table("test_sessions").select("*").eq("id", session_id).eq("candidate_id", user_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Test session not found. Please parse your resume first.")
        
    return resp.data

@router.post("/{session_id}/consent")
def submit_consent(session_id: str, data: ConsentModel, user: dict = Depends(require_candidate)):
    if not data.consent:
        raise HTTPException(status_code=400, detail="Consent is required to proceed")
    
    user_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    cached = session_store.get_session(session_id)
    client = get_supabase()
    if cached or user_id == "00000000-0000-0000-0000-000000000001" or not client:
        if not cached:
            cached = {
                "id": session_id,
                "candidate_id": user_id,
                "questions": [],
                "proctoring_consent": True,
                "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        else:
            cached["proctoring_consent"] = True
            cached["started_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        session_store.save_session(session_id, cached)
        return {"message": "Consent recorded"}
    # --- DEMO BYPASS END ---
    
    resp = client.table("test_sessions").select("id").eq("id", session_id).eq("candidate_id", user_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Test session not found")
        
    client.table("test_sessions").update({
        "proctoring_consent": True,
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }).eq("id", session_id).execute()
    
    return {"message": "Consent recorded"}

async def run_passport_issuer(candidate_id: str, session_id: str, answers: dict,
                              preloaded_questions: list = None, preloaded_skills: list = None):
    """Run Agent 4: Passport Issuer or Roadmap Generator, triggered after test submit."""
    # Use pre-loaded data if provided (demo user path)
    if preloaded_questions is not None:
        questions = preloaded_questions
        extracted_skills = preloaded_skills or []
    else:
        # Real user: fetch from Supabase
        client = get_supabase()
        session_resp = client.table("test_sessions").select("*").eq("id", session_id).single().execute()
        if not session_resp.data:
            return
        questions = session_resp.data.get("questions", [])
        candidate_resp = client.table("candidates").select("extracted_skills").eq("id", candidate_id).single().execute()
        extracted_skills = candidate_resp.data.get("extracted_skills", []) if candidate_resp.data else []
    
    state = {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "answers": answers,
        "questions": questions,
        "proctoring_score": 100.0,
        "extracted_skills": extracted_skills,
        "score": 0.0,
        "passed": False,
        "error": ""
    }
    
    await passport_issuer_graph.ainvoke(state)

@router.post("/{session_id}/submit")
async def submit_test(session_id: str, data: AnswersModel, background_tasks: BackgroundTasks, user: dict = Depends(require_candidate)):
    user_id = user["user_id"]
    
    # Check session_store first (demo user sessions are stored in-memory)
    from app.services import session_store
    cached_session = session_store.get_session(session_id)
    
    if cached_session:
        if cached_session.get("answers"):
            raise HTTPException(status_code=400, detail="Test already submitted")
        cached_session["answers"] = data.answers
        session_store.save_session(session_id, cached_session)
        # Pass session data directly to avoid Supabase lookups in the passport issuer
        background_tasks.add_task(
            run_passport_issuer, user_id, session_id, data.answers,
            cached_session.get("questions", []),
            cached_session.get("extracted_skills", [])
        )
        return {"message": "Test submitted. Agent 4 is evaluating your results."}
    
    # Real user: read from Supabase
    client = get_supabase()
    resp = client.table("test_sessions").select("*").eq("id", session_id).eq("candidate_id", user_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Test session not found")
        
    session = resp.data
    if session.get("answers"):
        raise HTTPException(status_code=400, detail="Test already submitted")
        
    client.table("test_sessions").update({
        "answers": data.answers,
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }).eq("id", session_id).execute()
    
    background_tasks.add_task(run_passport_issuer, user_id, session_id, data.answers)
    
    return {"message": "Test submitted. Agent 4 is evaluating your results."}
