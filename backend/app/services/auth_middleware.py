from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.supabase import get_supabase
import os
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates the Supabase JWT token and extracts user_id and role.
    """
    token = credentials.credentials
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    
    # 1. Attempt decode (leniently for demo)
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        user_id = payload.get("sub")
        role = payload.get("role")
    except Exception:
        user_id = None
        role = None

    # 2. DEMO BYPASS
    if token == "demo-token-candidate":
         return {"user_id": "00000000-0000-0000-0000-000000000001", "role": "candidate"}
    if token == "demo-token-recruiter":
         return {"user_id": "00000000-0000-0000-0000-000000000002", "role": "recruiter"}
    if token and token.startswith("demo-token-"):
         parts = token.split("-")
         if len(parts) >= 4:
             role = parts[2]
             user_id = "-".join(parts[3:])
             return {"user_id": user_id, "role": role}

    if user_id:
        if user_id == "00000000-0000-0000-0000-000000000001":
            return {"user_id": user_id, "role": "candidate"}
        if user_id == "00000000-0000-0000-0000-000000000002":
            return {"user_id": user_id, "role": "recruiter"}

    # 3. Production: Query Supabase if bypass didn't trigger
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        client = get_supabase()
        if client:
            user_profile = client.table("profiles").select("role").eq("id", user_id).single().execute()
            if user_profile.data:
                role = user_profile.data.get("role")
        return {"user_id": user_id, "role": role}
    except Exception:
        if role and role != "authenticated":
            return {"user_id": user_id, "role": role}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User profile not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Example role checker dependencies
def require_candidate(user: dict = Depends(verify_token)):
    if user.get("role") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access required")
    return user

def require_recruiter(user: dict = Depends(verify_token)):
    if user.get("role") != "recruiter":
        raise HTTPException(status_code=403, detail="Recruiter access required")
    return user
