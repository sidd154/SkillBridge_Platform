from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.supabase import get_supabase
from app.services.auth_middleware import require_recruiter, require_candidate

router = APIRouter(prefix="/headhunt", tags=["headhunt"])

class HeadhuntRequest(BaseModel):
    candidate_id: str
    job_id: str
    message: str

class HeadhuntRespond(BaseModel):
    status: str # "accepted" or "declined"

@router.post("")
def headhunt_candidate(req: HeadhuntRequest, user: dict = Depends(require_recruiter)):
    client = get_supabase()
    recruiter_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    if recruiter_id == "00000000-0000-0000-0000-000000000002" or not client:
        import uuid as _uuid, datetime as _dt
        inv_id = str(_uuid.uuid4())
        invitation = {
            "id": inv_id,
            "recruiter_id": recruiter_id,
            "candidate_id": req.candidate_id,
            "job_id": req.job_id,
            "message": req.message,
            "status": "pending",
            "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat()
        }
        invs = session_store.get_session(f"invitations:{req.candidate_id}") or []
        invs.append(invitation)
        session_store.save_session(f"invitations:{req.candidate_id}", invs)
        return {"message": "Invitation sent", "data": invitation}
    # --- DEMO BYPASS END ---
    
    # Verify candidate has active passport (Rule 6)
    cand = client.table("candidates").select("passport_id, skill_passports!inner(is_active)").eq("id", req.candidate_id).single().execute()
    if not cand.data or not cand.data.get("skill_passports") or not cand.data["skill_passports"].get("is_active"):
        raise HTTPException(status_code=400, detail="Cannot headhunt a candidate without active passport")
        
    resp = client.table("headhunt_invitations").insert({
        "recruiter_id": recruiter_id,
        "candidate_id": req.candidate_id,
        "job_id": req.job_id,
        "message": req.message
    }).execute()
    
    return {"message": "Invitation sent", "data": resp.data[0]}

@router.get("/invitations")
def get_invitations(user: dict = Depends(require_candidate)):
    client = get_supabase()
    user_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    if user_id == "00000000-0000-0000-0000-000000000001" or not client:
        invs = session_store.get_session(f"invitations:{user_id}") or []
        # Enrich invitations with job/company details
        enriched = []
        for inv in invs:
            # try to find job
            all_sessions = session_store.get_all_sessions()
            job_obj = {"title": "Job Offer", "location": "Remote"}
            for key, val in all_sessions.items():
                if key.startswith("demo_jobs_") and isinstance(val, list):
                    for job in val:
                        if job.get("id") == inv.get("job_id"):
                            job_obj = job
                            break
            inv_copy = dict(inv)
            inv_copy["jobs"] = job_obj
            inv_copy["recruiters"] = {"company_name": "Tech Corp"}
            enriched.append(inv_copy)
        return enriched
    # --- DEMO BYPASS END ---
    
    resp = client.table("headhunt_invitations").select("*, jobs(*), recruiters!inner(company_name)").eq("candidate_id", user_id).order("created_at", desc=True).execute()
    return resp.data

@router.put("/{invitation_id}/respond")
def respond_headhunt(invitation_id: str, data: HeadhuntRespond, user: dict = Depends(require_candidate)):
    if data.status not in ["accepted", "declined"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    client = get_supabase()
    user_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    if user_id == "00000000-0000-0000-0000-000000000001" or not client:
        invs = session_store.get_session(f"invitations:{user_id}") or []
        matched_inv = None
        for inv in invs:
            if inv.get("id") == invitation_id:
                inv["status"] = data.status
                matched_inv = inv
                break
        if not matched_inv:
            raise HTTPException(status_code=404, detail="Invitation not found")
        session_store.save_session(f"invitations:{user_id}", invs)
        
        if data.status == "accepted":
            # Create an application in session_store
            existing_apps = session_store.get_session(f"applications:{user_id}") or []
            if not any(a.get("job_id") == matched_inv["job_id"] for a in existing_apps):
                import uuid as _uuid, datetime as _dt
                app_obj = {
                    "id": str(_uuid.uuid4()),
                    "job_id": matched_inv["job_id"],
                    "candidate_id": user_id,
                    "source": "recruiter_headhunted",
                    "status": "interview_pending",
                    "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat()
                }
                existing_apps.append(app_obj)
                session_store.save_session(f"applications:{user_id}", existing_apps)
                
        return {"message": f"Invitation {data.status}"}
    # --- DEMO BYPASS END ---
    
    inv = client.table("headhunt_invitations").select("*").eq("id", invitation_id).eq("candidate_id", user_id).single().execute()
    if not inv.data:
        raise HTTPException(status_code=404, detail="Invitation not found")
        
    client.table("headhunt_invitations").update({"status": data.status}).eq("id", invitation_id).execute()
    
    if data.status == "accepted":
        # Create an application based on this
        client.table("applications").insert({
            "job_id": inv.data["job_id"],
            "candidate_id": user_id,
            "source": "recruiter_headhunted",
            "status": "interview_pending"
        }).execute()
        
    return {"message": f"Invitation {data.status}"}
