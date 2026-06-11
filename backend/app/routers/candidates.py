import uuid
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.supabase import get_supabase
from app.services.auth_middleware import verify_token, require_candidate
from app.services import session_store
from app.agents.graphs.resume_parser_graph import resume_parser_graph
from app.agents.graphs.test_generator_graph import test_generator_graph
from app.agents.graphs.portfolio_analyzer_graph import portfolio_analyzer_graph

router = APIRouter(prefix="/candidates", tags=["candidates"])

class CandidateProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    college: Optional[str] = None
    graduation_year: Optional[int] = None
    degree: Optional[str] = None

@router.get("/profile")
def get_candidate_profile(user: dict = Depends(require_candidate)):
    client = get_supabase()
    user_id = user["user_id"]
    
    if user_id == DEMO_CANDIDATE_ID or not client:
        stored = session_store.get_session(f"profile:{user_id}")
        if not stored:
            stored = {
                "id": user_id,
                "role": "candidate",
                "full_name": "Demo Candidate",
                "email": "demo.candidate@skillbridge.dev",
                "phone": "1234567890",
                "college": "Skill University",
                "graduation_year": 2024,
                "degree": "B.S. CS"
            }
        return stored
        
    # Needs to join custom table and profiles
    
    profile_resp = client.table("profiles").select("*").eq("id", user_id).single().execute()
    candidate_resp = client.table("candidates").select("*").eq("id", user_id).single().execute()
    
    if not profile_resp.data or not candidate_resp.data:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    return {**profile_resp.data, **candidate_resp.data}

@router.put("/profile")
def update_candidate_profile(profile_data: CandidateProfileUpdate, user: dict = Depends(require_candidate)):
    client = get_supabase()
    user_id = user["user_id"]
    
    if user_id == DEMO_CANDIDATE_ID or not client:
        stored = session_store.get_session(f"profile:{user_id}") or {
            "id": user_id,
            "role": "candidate",
            "full_name": "Demo Candidate",
            "email": "demo.candidate@skillbridge.dev",
            "phone": "1234567890",
            "college": "Skill University",
            "graduation_year": 2024,
            "degree": "B.S. CS"
        }
        if profile_data.full_name is not None:
            stored["full_name"] = profile_data.full_name
        if profile_data.phone is not None:
            stored["phone"] = profile_data.phone
        if profile_data.college is not None:
            stored["college"] = profile_data.college
        if profile_data.graduation_year is not None:
            stored["graduation_year"] = profile_data.graduation_year
        if profile_data.degree is not None:
            stored["degree"] = profile_data.degree
        session_store.save_session(f"profile:{user_id}", stored)
        return {"message": "Profile updated successfully"}
        
    profile_updates = {}
    if profile_data.full_name is not None:
        profile_updates["full_name"] = profile_data.full_name
    if profile_data.phone is not None:
        profile_updates["phone"] = profile_data.phone
        
    if profile_updates:
        client.table("profiles").update(profile_updates).eq("id", user_id).execute()
        
    candidate_updates = {}
    if profile_data.college is not None:
        candidate_updates["college"] = profile_data.college
    if profile_data.graduation_year is not None:
        candidate_updates["graduation_year"] = profile_data.graduation_year
    if profile_data.degree is not None:
        candidate_updates["degree"] = profile_data.degree
        
    if candidate_updates:
        client.table("candidates").update(candidate_updates).eq("id", user_id).execute()
        
    return {"message": "Profile updated successfully"}

DEMO_CANDIDATE_ID = "00000000-0000-0000-0000-000000000001"

@router.post("/upload-resume")
async def upload_resume(
    resume: UploadFile = File(...), 
    github: str = Form(""),
    leetcode: str = Form(""),
    linkedin: str = Form(""),
    tenth_marks: str = Form(""),
    twelfth_marks: str = Form(""),
    user: dict = Depends(require_candidate)
):
    print("====== ENDPOINT HIT ======", flush=True)
    user_id = user["user_id"]
    file_content = await resume.read()
    
    # ── DEMO USER: all Supabase writes are skipped (fake UUID not in auth.users) ──
    if user_id == DEMO_CANDIDATE_ID:
        import os, io, json, uuid as _uuid
        import pdfplumber
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # 1. Save to local disk
        local_dir = os.path.join("storage", "resumes", user_id)
        os.makedirs(local_dir, exist_ok=True)
        file_id = str(_uuid.uuid4())
        file_ext = resume.filename.split('.')[-1] if '.' in resume.filename else 'pdf'
        local_path = os.path.join(local_dir, f"{file_id}.{file_ext}")
        with open(local_path, "wb") as f:
            f.write(file_content)
        
        # 2. Parse PDF text
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                pages = [p.extract_text() for p in pdf.pages if p.extract_text()]
            raw_text = " ".join(pages).strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF parsing failed: {e}")
        
        if len(raw_text) < 50:
            raise HTTPException(status_code=400, detail="Could not extract enough text from PDF. Ensure it is not a scanned image.")
        
        # 3. Extract skills with GPT-4o
        llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
        sys_prompt = """You are an advanced resume parser. Return ONLY valid JSON with this structure:
{"extracted_skills": [{"skill_name": "...", "category": "...", "proficiency_claimed": "beginner/intermediate/advanced", "years_of_experience_claimed": 0}],
 "github_link": "URL or null", "leetcode_link": "URL or null", "linkedin_link": "URL or null"}"""
        try:
            resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=raw_text)])
            parsed = json.loads(resp.content.replace("```json", "").replace("```", "").strip())
            extracted_skills = parsed.get("extracted_skills", [])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM parsing failed: {e}")
        
        # 4. Generate test questions with GPT-4o
        q_llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
        q_prompt = """Generate exactly 5 unique MCQ questions for the given skills. 
Avoid common generic questions; focus on specific implementation details or edge cases.
Return ONLY a JSON array.
Use unique, predictable internal IDs: "q1", "q2", "q3", "q4", "q5".
Schema: [{"question_id": "q1", "skill": "string", "question_text": "string", "options": {"A":"","B":"","C":"","D":""}, "correct_answer": "A/B/C/D", "difficulty": "easy/medium/hard"}]"""
        try:
            qresp = q_llm.invoke([SystemMessage(content=q_prompt), HumanMessage(content=json.dumps(extracted_skills))])
            questions = json.loads(qresp.content.replace("```json", "").replace("```", "").strip())
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Question generation failed: {e}")

        # 5. Clear old demo sessions to ensure fresh results
        from app.services import session_store
        session_store.delete_session(f"passport:{user_id}")
        session_store.delete_session(f"roadmap:{user_id}")
        demo_session_id = f"demo-{str(_uuid.uuid4())}"
        from app.services import session_store
        session_store.save_session(demo_session_id, {
            "id": demo_session_id,
            "candidate_id": user_id,
            "questions": questions,
            "proctoring_consent": False,
            "answers": None,
            "extracted_skills": extracted_skills,
            "github_link": github or parsed.get("github_link", ""),
            "leetcode_link": leetcode or parsed.get("leetcode_link", ""),
        })
        
        # Also save skills separately so matches/profile endpoints can find them
        session_store.save_session(f"skills:{user_id}", {
            "extracted_skills": extracted_skills,
            "github_link": github or parsed.get("github_link", ""),
            "leetcode_link": leetcode or parsed.get("leetcode_link", ""),
            "linkedin_link": parsed.get("linkedin_link", ""),
        })
        
        return {"extracted_skills": extracted_skills, "session_id": demo_session_id}
    
    # ── REAL USER: full DB flow ──
    client = get_supabase()
    from app.services.supabase import SUPABASE_RESUME_BUCKET
    
    file_id = str(uuid.uuid4())
    file_ext = resume.filename.split('.')[-1] if '.' in resume.filename else 'pdf'
    storage_path = f"{user_id}/{file_id}.{file_ext}"
    
    # Try Supabase Storage, fall back to local disk
    try:
        client.storage.from_(SUPABASE_RESUME_BUCKET).upload(storage_path, file_content, {"content-type": resume.content_type})
    except Exception:
        import os
        local_dir = os.path.join("storage", "resumes", user_id)
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, f"{file_id}.{file_ext}")
        with open(local_path, "wb") as f:
            f.write(file_content)
        storage_path = local_path
    
    client.table("candidates").update({"resume_path": storage_path}).eq("id", user_id).execute()

    try:
        parser_state = {
            "pdf_path": storage_path,
            "candidate_id": user_id,
            "raw_text": "",
            "extracted_skills": [],
            "tenth_marks": "",
            "twelfth_marks": "",
            "github_link": "",
            "leetcode_link": "",
            "linkedin_link": "",
            "error": ""
        }
        
        parser_result = await resume_parser_graph.ainvoke(parser_state)
        
        if parser_result.get("error"):
            raise HTTPException(status_code=400, detail=parser_result["error"])
            
        extracted_skills = parser_result.get("extracted_skills", [])
        
        candidate_updates = {
            "github_link": github or parser_result.get("github_link", ""),
            "leetcode_link": leetcode or parser_result.get("leetcode_link", ""),
            "linkedin_link": linkedin or parser_result.get("linkedin_link", ""),
            "tenth_marks": tenth_marks or parser_result.get("tenth_marks", ""),
            "twelfth_marks": twelfth_marks or parser_result.get("twelfth_marks", "")
        }
        
        client.table("candidates").update(candidate_updates).eq("id", user_id).execute()
        
        portfolio_state = {
            "candidate_id": user_id,
            "github_link": candidate_updates["github_link"],
            "leetcode_link": candidate_updates["leetcode_link"],
            "github_raw_html": "",
            "leetcode_raw_html": "",
            "github_score": 0.0,
            "leetcode_score": 0.0,
            "total_portfolio_score": 0.0,
            "error": ""
        }
        await portfolio_analyzer_graph.ainvoke(portfolio_state)

        test_state = {
            "candidate_id": user_id,
            "extracted_skills": extracted_skills,
            "generated_questions": [],
            "session_id": "",
            "error": "",
            "retry_count": 0
        }
        
        test_result = await test_generator_graph.ainvoke(test_state)
        
        if test_result.get("error"):
            raise HTTPException(status_code=400, detail=test_result["error"])
            
        session_id = test_result.get("session_id")
        
        return {"extracted_skills": extracted_skills, "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=traceback.format_exc())

@router.get("/passport")
def get_passport(user: dict = Depends(require_candidate)):
    user_id = user["user_id"]
    
    # Check in-memory store first (demo user)
    from app.services import session_store
    cached_passport = session_store.get_session(f"passport:{user_id}")
    if cached_passport:
        return cached_passport
    
    client = get_supabase()
    if not client:
        raise HTTPException(status_code=404, detail="No passport found")
    resp = client.table("skill_passports").select("*").eq("candidate_id", user_id).order("issued_at", desc=True).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="No passport found")
    return resp.data[0]

@router.get("/roadmap")
def get_roadmap(user: dict = Depends(require_candidate)):
    user_id = user["user_id"]
    
    # Check in-memory store first (demo user)
    from app.services import session_store
    cached_roadmap = session_store.get_session(f"roadmap:{user_id}")
    if cached_roadmap:
        return cached_roadmap
    
    client = get_supabase()
    if not client:
        raise HTTPException(status_code=404, detail="No roadmap found")
    resp = client.table("improvement_roadmaps").select("*").eq("candidate_id", user_id).order("created_at", desc=True).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="No roadmap found")
    return resp.data[0]

@router.get("/matches")
def get_job_matches(user: dict = Depends(require_candidate)):
    user_id = user["user_id"]
    client = get_supabase()
    
    candidate_skills = []
    verified_skills = []
    
    # For demo user: get skills from session_store (no Supabase row)
    if user_id == DEMO_CANDIDATE_ID:
        from app.services import session_store
        cached_skills = session_store.get_session(f"skills:{user_id}")
        if not cached_skills:
            return []
        candidate_skills = cached_skills.get("extracted_skills", [])
        # Check for passport in session_store
        cached_passport = session_store.get_session(f"passport:{user_id}")
        if cached_passport:
            verified_skills = cached_passport.get("skills", [])
    else:
        # 1. Get Candidate Skills from Supabase
        candidate_resp = client.table("candidates").select("extracted_skills").eq("id", user_id).single().execute()
        if not candidate_resp.data:
            raise HTTPException(status_code=404, detail="Candidate not found")
        candidate_skills = candidate_resp.data.get("extracted_skills", [])
        
        # 2. Check if they have a passport for verified skills
        passport_resp = client.table("skill_passports").select("verified_skills").eq("candidate_id", user_id).eq("is_active", True).execute()
        if passport_resp.data:
            verified_skills = passport_resp.data[0].get("verified_skills", [])
        
    skills_to_match = verified_skills if verified_skills else candidate_skills
    
    # 3. Get Open Jobs: merge Supabase job_briefs + demo session_store jobs
    jobs = []
    
    # 3a. Supabase job_briefs (for verified recruiter jobs)
    try:
        jobs_resp = client.table("job_briefs").select("job_id, title, role_description, tech_stack, criteria").execute()
        if jobs_resp.data:
            jobs.extend(jobs_resp.data)
    except Exception:
        pass
    
    # 3b. Demo jobs from session_store (always include these so demo candidate sees matches)
    from app.services import session_store as ss
    all_sessions = ss.get_all_sessions()
    for key, val in all_sessions.items():
        if key.startswith("demo_jobs_") and isinstance(val, list):
            for demo_job in val:
                # Build a job_brief-like object from the demo job
                skills_str = ", ".join(s.get("skill_name", "") for s in demo_job.get("required_skills", []))
                jobs.append({
                    "job_id": demo_job["id"],
                    "title": demo_job.get("title", ""),
                    "role_description": demo_job.get("description", ""),
                    "tech_stack": skills_str,
                    "criteria": f"Min {demo_job.get('min_experience_years', 0)} years experience. Skills: {skills_str}"
                })
    
    if not jobs:
        return []
        
    if not skills_to_match:
        return [{"job_id": j["job_id"], "match_percentage": 0, "reason": "No skills extracted yet."} for j in jobs]
        
    # 4. LLM matching
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0, max_tokens=2000)
    
    system_prompt = """You are an AI recruitment matchmaker.
    You will be given a candidate's list of skills (either extracted from resume or verified via test), and a list of open jobs.
    For each job, calculate a match percentage (0-100) based on how well the candidate's skills align with the job's role description, tech stack, and criteria.
    Provide a brief, 1-sentence reason for the score.
    
    Respond STRICTLY in the following JSON format:
    {
       "matches": [
          {
             "job_id": "job_id_from_input",
             "match_percentage": 85,
             "reason": "Strong alignment in React and Python, lacking AWS experience."
          }
       ]
    }
    """
    
    human_msg = f"Candidate Skills: {skills_to_match}\n\nJobs:\n"
    for job in jobs:
        human_msg += f"- ID: {job['job_id']}\n  Title: {job['title']}\n  Stack: {job['tech_stack']}\n  Criteria: {job['criteria']}\n\n"
        
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_msg)
        ])
        
        raw_content = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_content)
        
        match_dict = {m["job_id"]: m for m in data.get("matches", [])}
        result = []
        for job in jobs:
            job_id = job["job_id"]
            if job_id in match_dict:
                result.append(match_dict[job_id])
            else:
                result.append({"job_id": job_id, "match_percentage": 0, "reason": "Match evaluation failed."})
                
        result.sort(key=lambda x: x["match_percentage"], reverse=True)
        return result
        
    except Exception as e:
        print(f"LLM Matching Error: {e}")
        return [{"job_id": j["job_id"], "match_percentage": 0, "reason": "Error during evaluation."} for j in jobs]
