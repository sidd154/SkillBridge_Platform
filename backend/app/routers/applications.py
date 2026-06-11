from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict
from app.services.supabase import get_supabase
from app.services.auth_middleware import require_candidate, require_recruiter
from app.services import session_store

router = APIRouter(prefix="/applications", tags=["applications"])

class ApplicationCreate(BaseModel):
    job_id: str
    source: str = "candidate_applied"

class ApplicationStatusUpdate(BaseModel):
    status: str

DEMO_CANDIDATE_ID = "00000000-0000-0000-0000-000000000001"
DEMO_RECRUITER_ID = "00000000-0000-0000-0000-000000000002"


def _get_demo_app(app_id: str):
    """Search all session_store keys for a demo application with the given id."""
    all_data = session_store.get_all_sessions()
    for key, val in all_data.items():
        if key.startswith("applications:") and isinstance(val, list):
            for app in val:
                if app.get("id") == app_id:
                    return key, app
    return None, None


def _is_demo_job(job_id: str) -> bool:
    """Check if job_id belongs to a demo job in session_store."""
    all_data = session_store.get_all_sessions()
    for key, val in all_data.items():
        if key.startswith("demo_jobs_") and isinstance(val, list):
            for job in val:
                if job.get("id") == job_id:
                    return True
    return False


@router.post("")
def create_application(app_data: ApplicationCreate, user: dict = Depends(require_candidate)):
    user_id = user["user_id"]
    client = get_supabase()

    # Demo user: check session_store for passport, store application in memory
    if user_id == DEMO_CANDIDATE_ID or not client:
        passport = session_store.get_session(f"passport:{user_id}")
        if not passport:
            raise HTTPException(
                status_code=403,
                detail="You need a Skill Passport to apply. Please upload your resume, complete the assessment test, and score ≥70% to earn your passport."
            )

        # Check if already applied
        existing_apps = session_store.get_session(f"applications:{user_id}") or []
        if any(a.get("job_id") == app_data.job_id for a in existing_apps):
            raise HTTPException(status_code=400, detail="You have already applied to this job.")

        import uuid as _uuid, datetime as _dt
        app_id = str(_uuid.uuid4())
        app_obj = {
            "id": app_id,
            "job_id": app_data.job_id,
            "candidate_id": user_id,
            "source": app_data.source,
            "status": "applied",
            "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat()
        }
        apps = existing_apps
        apps.append(app_obj)
        session_store.save_session(f"applications:{user_id}", apps)
        return app_obj

    # Check if candidate has active passport
    cand = client.table("candidates").select("passport_id").eq("id", user_id).single().execute()
    if not cand.data or not cand.data.get("passport_id"):
        raise HTTPException(status_code=403, detail="Must have a Skill Passport to apply")

    passport = client.table("skill_passports").select("is_active, expires_at").eq("id", cand.data["passport_id"]).single().execute()
    if not passport.data or not passport.data.get("is_active"):
        raise HTTPException(status_code=403, detail="Skill Passport not active")

    resp = client.table("applications").insert({
        "job_id": app_data.job_id,
        "candidate_id": user_id,
        "source": app_data.source,
        "status": "applied"
    }).execute()

    return resp.data[0]


@router.get("")
def list_applications(user: dict = Depends(require_candidate)):
    user_id = user["user_id"]

    client = get_supabase()

    # Demo user: return from session_store, enriched with job data
    if user_id == DEMO_CANDIDATE_ID or not client:
        apps = session_store.get_session(f"applications:{user_id}") or []
        if apps:
            # Try to enrich with job data (first from session_store, then Supabase)
            all_data = session_store.get_all_sessions()
            demo_job_map: Dict[str, dict] = {}
            for key, val in all_data.items():
                if key.startswith("demo_jobs_") and isinstance(val, list):
                    for job in val:
                        demo_job_map[job["id"]] = job

            for app in apps:
                jid = app.get("job_id")
                if jid in demo_job_map:
                    app["jobs"] = demo_job_map[jid]
                else:
                    try:
                        if client:
                            job_resp = client.table("jobs").select("*").eq("id", jid).single().execute()
                            app["jobs"] = job_resp.data if job_resp.data else {"title": "Job", "location": "Remote"}
                        else:
                            app["jobs"] = {"title": "Job Listing", "location": "Remote"}
                    except Exception:
                        app["jobs"] = {"title": "Job Listing", "location": "Remote"}
        return apps
    if not client:
        return []
    resp = client.table("applications").select("*, jobs(*)").eq("candidate_id", user_id).order("created_at", desc=True).execute()
    return resp.data


@router.put("/{id}/status")
def update_application_status(id: str, update_data: ApplicationStatusUpdate, user: dict = Depends(require_recruiter)):
    user_id = user["user_id"]

    client = get_supabase()

    # Demo recruiter bypass: update in session_store
    if user_id == DEMO_RECRUITER_ID or not client:
        key, app = _get_demo_app(id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        app["status"] = update_data.status
        apps = session_store.get_session(key) or []
        new_apps = [a if a.get("id") != id else app for a in apps]
        session_store.save_session(key, new_apps)
        return app
    app_data = client.table("applications").select("jobs(recruiter_id)").eq("id", id).single().execute()
    if not app_data.data or app_data.data["jobs"]["recruiter_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    resp = client.table("applications").update({"status": update_data.status}).eq("id", id).execute()
    return resp.data[0]


@router.put("/{id}/request_test")
def request_test(id: str, user: dict = Depends(require_recruiter)):
    user_id = user["user_id"]

    client = get_supabase()

    # Demo recruiter bypass
    if user_id == DEMO_RECRUITER_ID or not client:
        key, app = _get_demo_app(id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        app["status"] = "test_requested"
        apps = session_store.get_session(key) or []
        new_apps = [a if a.get("id") != id else app for a in apps]
        session_store.save_session(key, new_apps)
        return app
    app_data = client.table("applications").select("jobs(recruiter_id)").eq("id", id).single().execute()
    if not app_data.data or app_data.data["jobs"]["recruiter_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    resp = client.table("applications").update({"status": "test_requested"}).eq("id", id).execute()
    return resp.data[0]


@router.put("/{id}/request_interview")
def request_interview(id: str, user: dict = Depends(require_recruiter)):
    user_id = user["user_id"]

    client = get_supabase()

    # Demo recruiter bypass
    if user_id == DEMO_RECRUITER_ID or not client:
        key, app = _get_demo_app(id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        app["status"] = "interview_requested"
        apps = session_store.get_session(key) or []
        new_apps = [a if a.get("id") != id else app for a in apps]
        session_store.save_session(key, new_apps)
        return app
    app_data = client.table("applications").select("jobs(recruiter_id)").eq("id", id).single().execute()
    if not app_data.data or app_data.data["jobs"]["recruiter_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    resp = client.table("applications").update({"status": "interview_requested"}).eq("id", id).execute()
    return resp.data[0]


@router.put("/{id}/accept_interview")
def accept_interview(id: str, user: dict = Depends(require_candidate)):
    user_id = user["user_id"]

    client = get_supabase()

    # Demo candidate bypass: update in session_store, create in-memory interview session
    if user_id == DEMO_CANDIDATE_ID or not client:
        key, app = _get_demo_app(id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.get("candidate_id") != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        import uuid as _uuid
        session_id = str(_uuid.uuid4())
        app["status"] = "interview_accepted"
        app["interview_session_id"] = session_id

        apps = session_store.get_session(key) or []
        new_apps = [a if a.get("id") != id else app for a in apps]
        session_store.save_session(key, new_apps)

        # Store the interview session itself
        session_store.save_session(f"interview_session:{session_id}", {
            "id": session_id,
            "application_id": id,
            "status": "pending",
            "candidate_id": user_id,
        })

        return {**app, "interview_session_id": session_id}
    app_data = client.table("applications").select("candidate_id").eq("id", id).single().execute()
    if not app_data.data or app_data.data["candidate_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    resp = client.table("applications").update({"status": "interview_accepted"}).eq("id", id).execute()

    sess_resp = client.table("interview_sessions").insert({
        "application_id": id,
        "status": "pending"
    }).execute()

    session_id = sess_resp.data[0]["id"] if sess_resp.data else None

    result = resp.data[0]
    if session_id:
        result["interview_session_id"] = session_id
    return result
