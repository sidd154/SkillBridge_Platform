import os
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from app.services.supabase import get_supabase
from app.config import settings
from authlib.jose import jwt
import random
from typing import Optional

router = APIRouter(prefix="/auth", tags=["auth"])

# Models
class CandidateRegisterBase(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    college: str
    graduation_year: int
    degree: str
    phone: str

class RecruiterRegisterBase(BaseModel):
    full_name: str
    work_email: EmailStr
    password: str
    company_name: str
    company_size: str
    designation: str

class LoginBase(BaseModel):
    email: EmailStr
    password: str

class OTPVerifyBase(BaseModel):
    email: EmailStr
    otp_code: str

# Email Service integration placeholder
# We need to send OTP via SMTP. Let's assume we have send_otp(email, code) in email_service.py
from app.services.email_service import send_otp

def is_valid_work_email(email: str) -> bool:
    disposable_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com']
    domain = email.split('@')[-1].lower()
    return domain not in disposable_domains

@router.post("/register/candidate")
async def register_candidate(user: CandidateRegisterBase):
    client = get_supabase()
    
    # --- DEMO BYPASS START ---
    if not client:
        from app.services import session_store
        import uuid
        user_id = str(uuid.uuid4())
        user_dict = {
            "id": user_id,
            "email": user.email,
            "password": user.password,
            "full_name": user.full_name,
            "role": "candidate",
            "college": user.college,
            "graduation_year": user.graduation_year,
            "degree": user.degree,
            "phone": user.phone,
            "is_verified": True
        }
        session_store.save_session(f"user:{user.email}", user_dict)
        session_store.save_session(f"user_by_id:{user_id}", user_dict)
        session_store.save_session(f"profile:{user_id}", user_dict)
        return {"message": "Candidate registered successfully."}
    # --- DEMO BYPASS END ---
    
    try:
        response = client.auth.sign_up({
            "email": user.email,
            "password": user.password
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if not response.user:
        raise HTTPException(status_code=400, detail="Registration failed")
        
    user_id = response.user.id
    
    client.table("profiles").insert({
        "id": user_id,
        "email": user.email,
        "full_name": user.full_name,
        "role": "candidate"
    }).execute()
    
    client.table("candidates").insert({
        "id": user_id,
        "college": user.college,
        "graduation_year": user.graduation_year,
        "degree": user.degree,
        "phone": user.phone
    }).execute()
    
    return {"message": "Candidate registered successfully."}

@router.post("/register/recruiter")
async def register_recruiter(user: RecruiterRegisterBase, background_tasks: BackgroundTasks):
    client = get_supabase()
    
    if not is_valid_work_email(user.work_email):
        raise HTTPException(status_code=400, detail="Personal email domains are not allowed.")
        
    # --- DEMO BYPASS START ---
    if not client:
        from app.services import session_store
        import uuid
        user_id = str(uuid.uuid4())
        user_dict = {
            "id": user_id,
            "email": user.work_email,
            "password": user.password,
            "full_name": user.full_name,
            "role": "recruiter",
            "company_name": user.company_name,
            "company_size": user.company_size,
            "designation": user.designation,
            "is_verified": True
        }
        session_store.save_session(f"user:{user.work_email}", user_dict)
        session_store.save_session(f"user_by_id:{user_id}", user_dict)
        return {"message": "Recruiter registered successfully!"}
    # --- DEMO BYPASS END ---
    
    try:
        response = client.auth.sign_up({
            "email": user.work_email,
            "password": user.password
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if not response.user:
        raise HTTPException(status_code=400, detail="Registration failed")
        
    user_id = response.user.id
    
    client.table("profiles").insert({
        "id": user_id,
        "email": user.work_email,
        "full_name": user.full_name,
        "role": "recruiter"
    }).execute()

    client.table("recruiters").insert({
        "id": user_id,
        "company_name": user.company_name,
        "company_size": user.company_size,
        "designation": user.designation,
        "is_verified": True
    }).execute()
    
    return {"message": "Recruiter registered successfully!"}

@router.post("/verify-otp")
async def verify_otp(data: OTPVerifyBase):
    client = get_supabase()
    
    # Find recruiter by email to get user_id
    profile_resp = client.table("profiles").select("id").eq("email", data.email).eq("role", "recruiter").limit(1).execute()
    if not profile_resp.data:
        raise HTTPException(status_code=404, detail="Recruiter not found.")
    
    user_id = profile_resp.data[0]['id']
    
    rec_resp = client.table("recruiters").select("otp_code", "otp_expires_at", "is_verified").eq("id", user_id).single().execute()
    if not rec_resp.data:
        raise HTTPException(status_code=404, detail="Recruiter data not found.")
    
    record = rec_resp.data
    if record["is_verified"]:
        return {"message": "Already verified."}
    
    if record["otp_code"] != data.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP.")
    
    from datetime import datetime, timezone
    expires_at = datetime.fromisoformat(record["otp_expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="OTP expired.")
        
    client.table("recruiters").update({"is_verified": True, "otp_code": None, "otp_expires_at": None}).eq("id", user_id).execute()
    
    return {"message": "Verification successful."}

@router.post("/login")
async def login(data: LoginBase):
    if data.email == 'demo.candidate@skillbridge.dev' and data.password == 'Demo@1234':
        return {
            "user": {"id": settings.DEMO_CANDIDATE_ID, "role": "candidate", "full_name": "Demo Candidate", "email": "demo.candidate@skillbridge.dev"},
            "token": "demo-token-candidate",
            "role": "candidate",
            "is_verified": True
        }
    if data.email == 'demo.recruiter@techcorp.com' and data.password == 'Demo@1234':
        return {
            "user": {"id": settings.DEMO_RECRUITER_ID, "role": "recruiter", "full_name": "Demo Recruiter", "email": "demo.recruiter@techcorp.com"},
            "token": "demo-token-recruiter",
            "role": "recruiter",
            "is_verified": True
        }

    # --- DEMO BYPASS: Check local session store first ---
    from app.services import session_store
    stored_user = session_store.get_session(f"user:{data.email}")
    if stored_user:
        if stored_user.get("password") == data.password:
            role = stored_user.get("role", "candidate")
            token = f"demo-token-{role}"
            return {
                "user": stored_user,
                "token": token,
                "role": role,
                "is_verified": stored_user.get("is_verified", True)
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    # Strict DB Login
    client = get_supabase()
    try:
        response = client.auth.sign_in_with_password({"email": data.email, "password": data.password})
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not response.session:
        raise HTTPException(status_code=401, detail="Login failed")
    
    token = response.session.access_token
    user_id = response.user.id
    
    # Fetch role & is_verified for the response
    profile = client.table("profiles").select("role").eq("id", user_id).single().execute().data
    role = profile["role"] if profile else "candidate"
    
    is_verified = True
    if role == "recruiter":
        recruiter_data = client.table("recruiters").select("is_verified").eq("id", user_id).single().execute()
        if recruiter_data.data:
            is_verified = recruiter_data.data.get("is_verified", False)
            
    # Fetch full profile
    profile_data = client.table("profiles").select("*").eq("id", user_id).single().execute().data
    
    return {
        "user": profile_data,
        "token": token,
        "role": role,
        "is_verified": is_verified
    }
