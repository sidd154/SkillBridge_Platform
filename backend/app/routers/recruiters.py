from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.services.supabase import get_supabase
from app.services.auth_middleware import verify_token, require_recruiter

router = APIRouter(prefix="/recruiters", tags=["recruiters"])

class RecruiterProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    company_size: Optional[str] = None
    designation: Optional[str] = None

@router.get("/profile")
def get_recruiter_profile(user: dict = Depends(require_recruiter)):
    client = get_supabase()
    user_id = user["user_id"]
    # --- DEMO BYPASS START ---
    if user_id == "00000000-0000-0000-0000-000000000002":
        return {
            "id": user_id, "role": "recruiter", "full_name": "Demo Recruiter", "email": "demo.recruiter@techcorp.com",
            "phone": "0000000000", "company_name": "Tech Corp", "company_domain": "techcorp.com", 
            "company_size": "51-200", "designation": "Talent Acq Lead", "is_verified": True
        }
    from app.services import session_store
    stored_user = session_store.get_session(f"user_by_id:{user_id}")
    if stored_user:
        return stored_user
    # --- DEMO BYPASS END ---

    profile_resp = client.table("profiles").select("*").eq("id", user_id).single().execute()
    recruiter_resp = client.table("recruiters").select("*").eq("id", user_id).single().execute()
    
    if not profile_resp.data or not recruiter_resp.data:
        raise HTTPException(status_code=404, detail="Recruiter not found")
        
    return {**profile_resp.data, **recruiter_resp.data}

@router.put("/profile")
def update_recruiter_profile(profile_data: RecruiterProfileUpdate, user: dict = Depends(require_recruiter)):
    client = get_supabase()
    user_id = user["user_id"]
    
    if user_id == "00000000-0000-0000-0000-000000000002" or not client:
        stored = session_store.get_session(f"user_by_id:{user_id}") or {
            "id": user_id, "role": "recruiter", "full_name": "Demo Recruiter", "email": "demo.recruiter@techcorp.com",
            "phone": "0000000000", "company_name": "Tech Corp", "company_domain": "techcorp.com", 
            "company_size": "51-200", "designation": "Talent Acq Lead", "is_verified": True
        }
        if profile_data.full_name is not None:
            stored["full_name"] = profile_data.full_name
        if profile_data.company_name is not None:
            stored["company_name"] = profile_data.company_name
        if profile_data.company_size is not None:
            stored["company_size"] = profile_data.company_size
        if profile_data.designation is not None:
            stored["designation"] = profile_data.designation
        from app.services import session_store
        session_store.save_session(f"user_by_id:{user_id}", stored)
        session_store.save_session(f"user:{stored['email']}", stored)
        return {"message": "Profile updated successfully"}
        
    profile_updates = {}
    if profile_data.full_name is not None:
        client.table("profiles").update({"full_name": profile_data.full_name}).eq("id", user_id).execute()
        
    rec_updates = {}
    if profile_data.company_name is not None:
        rec_updates["company_name"] = profile_data.company_name
    if profile_data.company_size is not None:
        rec_updates["company_size"] = profile_data.company_size
    if profile_data.designation is not None:
        rec_updates["designation"] = profile_data.designation
        
    if rec_updates:
        client.table("recruiters").update(rec_updates).eq("id", user_id).execute()
        
    return {"message": "Profile updated successfully"}

@router.get("/candidates")
def search_talent(user: dict = Depends(require_recruiter)):
    client = get_supabase()
    user_id = user["user_id"]
    
    if user_id == "00000000-0000-0000-0000-000000000002" or not client:
        # Check all sessions for passport
        from app.services import session_store
        all_sessions = session_store.get_all_sessions()
        results = []
        for key, val in all_sessions.items():
            if key.startswith("passport:") and isinstance(val, dict):
                cand_id = val.get("candidate_id")
                # retrieve profile
                prof = session_store.get_session(f"profile:{cand_id}") or {
                    "full_name": "Demo Candidate",
                    "degree": "B.Tech",
                }
                skills_data = val.get("skills", [])
                results.append({
                    "id": cand_id,
                    "passport_id": val.get("id"),
                    "full_name": prof.get("full_name", "Demo Candidate"),
                    "degree": prof.get("degree", "B.Tech"),
                    "proctoring_score": val.get("proctoring_score", 100),
                    "skills": skills_data,
                    "github_score": prof.get("github_score", 90),
                    "leetcode_score": prof.get("leetcode_score", 90)
                })
        # If empty, return a pre-seeded demo list so it looks populated for the demo
        if not results:
            # Let's see if we have candidate_data or skills uploaded in session
            demo_skills = session_store.get_session("skills:00000000-0000-0000-0000-000000000001")
            skills_list = demo_skills.get("extracted_skills", []) if demo_skills else []
            if not skills_list:
                skills_list = [
                    {"skill_name": "React", "category": "Frontend", "verified": True, "proficiency_level": "advanced"},
                    {"skill_name": "TypeScript", "category": "Frontend", "verified": True, "proficiency_level": "advanced"},
                    {"skill_name": "Tailwind CSS", "category": "Frontend", "verified": True, "proficiency_level": "intermediate"},
                    {"skill_name": "Python", "category": "Backend", "verified": True, "proficiency_level": "intermediate"},
                ]
            results.append({
                "id": "00000000-0000-0000-0000-000000000001",
                "passport_id": "passport-demo",
                "full_name": "Demo Candidate",
                "degree": "B.S. CS",
                "proctoring_score": 95,
                "skills": skills_list,
                "github_score": 88,
                "leetcode_score": 92
            })
        return results

    # Check verification
    rec_resp = client.table("recruiters").select("is_verified").eq("id", user_id).single().execute()
    if not rec_resp.data or not rec_resp.data.get("is_verified"):
        raise HTTPException(status_code=403, detail="Account pending verification")
        
    # fetch passports joined with candidates and profiles
    resp = client.table("skill_passports").select("*, candidates(*, profiles(full_name))").eq("is_active", True).execute()
    
    results = []
    for sp in resp.data:
        if isinstance(sp.get("candidates"), dict) and "profiles" in sp["candidates"]:
            cand = sp["candidates"]
            prof = cand.get("profiles", {}) or {}
            
            # Use raw JSON skills or map them out
            skills_data = sp.get("skills", [])
            
            results.append({
                "id": cand["id"],
                "passport_id": sp["id"],
                "full_name": prof.get("full_name", "Anonymous"),
                "degree": cand.get("degree", "B.S. Generic"),
                "proctoring_score": sp.get("proctoring_score", 0),
                "skills": skills_data,
                "github_score": cand.get("github_score"),
                "leetcode_score": cand.get("leetcode_score")
            })
    return results
