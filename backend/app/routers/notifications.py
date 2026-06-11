from fastapi import APIRouter, Depends
from app.services.supabase import get_supabase
from app.services.auth_middleware import verify_token

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("")
def get_notifications(user: dict = Depends(verify_token)):
    client = get_supabase()
    user_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    if user_id == "00000000-0000-0000-0000-000000000001" or user_id == "00000000-0000-0000-0000-000000000002" or not client:
        return session_store.get_session(f"notifications:{user_id}") or []
    # --- DEMO BYPASS END ---
    
    resp = client.table("notifications").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return resp.data

@router.put("/{id}/read")
def mark_notification_read(id: str, user: dict = Depends(verify_token)):
    client = get_supabase()
    user_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    if user_id == "00000000-0000-0000-0000-000000000001" or user_id == "00000000-0000-0000-0000-000000000002" or not client:
        notifications = session_store.get_session(f"notifications:{user_id}") or []
        for notif in notifications:
            if notif.get("id") == id:
                notif["is_read"] = True
        session_store.save_session(f"notifications:{user_id}", notifications)
        return {"message": "Notification read"}
    # --- DEMO BYPASS END ---
    
    # Optional ownership check before update
    client.table("notifications").update({"is_read": True}).eq("id", id).eq("user_id", user_id).execute()
    return {"message": "Notification read"}
