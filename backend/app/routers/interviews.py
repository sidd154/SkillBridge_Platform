import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from typing import Dict
from pydantic import BaseModel
from app.services.supabase import get_supabase
from app.services.auth_middleware import verify_token, require_candidate, require_recruiter
from app.agents.graphs.bot_interview_graph import bot_interview_graph
from app.agents.graphs.summarizer_graph import summarizer_graph

router = APIRouter(tags=["interviews"])

class LiveInterviewManager:
    def __init__(self):
        # session_id -> {"candidate": ws, "recruiter": ws}
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, session_id: str, role: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.rooms:
            self.rooms[session_id] = {}
        self.rooms[session_id][role] = websocket
        
        if role == "candidate":
            if "recruiter" not in self.rooms[session_id]:
                await websocket.send_json({"type": "waiting_room", "message": "Waiting for recruiter to join."})
            else:
                await websocket.send_json({"type": "recruiter_joined", "message": "Recruiter is here."})
                await self.rooms[session_id]["recruiter"].send_json({"type": "candidate_joined"})
        elif role == "recruiter":
            if "candidate" in self.rooms[session_id]:
                await self.rooms[session_id]["candidate"].send_json({"type": "recruiter_joined", "message": "Recruiter joined!"})

    def disconnect(self, session_id: str, role: str):
        if session_id in self.rooms and role in self.rooms[session_id]:
            del self.rooms[session_id][role]

    async def send_to_peer(self, session_id: str, sender_role: str, message: dict):
        room = self.rooms.get(session_id, {})
        for role, ws in room.items():
            if role != sender_role:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    async def broadcast(self, session_id: str, message: dict):
        room = self.rooms.get(session_id, {})
        for role, ws in room.items():
            try:
                await ws.send_json(message)
            except Exception:
                pass

    def get_waiting_sessions(self) -> list:
        waiting = []
        for s_id, participants in self.rooms.items():
            if "candidate" in participants and "recruiter" not in participants:
                waiting.append(s_id)
        return waiting

manager = LiveInterviewManager()

@router.get("/interviews/waiting")
def get_waiting_interviews(user: dict = Depends(require_recruiter)):
    return {"waiting_sessions": manager.get_waiting_sessions()}

@router.post("/interviews/start/{application_id}")
def start_interview(application_id: str, background_tasks: BackgroundTasks, user: dict = Depends(require_candidate)):
    user_id = user["user_id"]
    client = get_supabase()
    
    # Demo bypass
    if user_id == "00000000-0000-0000-0000-000000000001" or not client:
        from app.services import session_store
        import uuid
        demo_session_id = None
        apps = session_store.get_session(f"applications:{user_id}") or []
        for app in apps:
            if app.get("id") == application_id:
                demo_session_id = app.get("interview_session_id")
                break
        if not demo_session_id:
            # Check all sessions
            all_sessions = session_store.get_all_sessions()
            for key, val in all_sessions.items():
                if key.startswith("applications:") and isinstance(val, list):
                    for app in val:
                        if app.get("id") == application_id:
                            demo_session_id = app.get("interview_session_id")
                            break
        if not demo_session_id:
            demo_session_id = str(uuid.uuid4())
        return {"interview_session_id": demo_session_id}
    resp = client.table("interview_sessions").insert({
        "application_id": application_id,
        "status": "in_progress"
    }).execute()
    
    if not resp.data:
        raise HTTPException(status_code=400, detail="Failed to start interview")
        
    return {"interview_session_id": resp.data[0]["id"]}

class EndSessionRequest(BaseModel):
    transcript: list
    code_snapshot: str

@router.post("/interviews/{session_id}/end")
def end_interview(session_id: str, req: EndSessionRequest, background_tasks: BackgroundTasks, user: dict = Depends(require_recruiter)):
    client = get_supabase()
    user_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    cached_session = session_store.get_session(f"interview_session:{session_id}")
    if cached_session or user_id == "00000000-0000-0000-0000-000000000002" or not client:
        if not cached_session:
            cached_session = {
                "id": session_id,
                "application_id": "demo-app-id",
                "status": "completed",
                "candidate_id": "00000000-0000-0000-0000-000000000001"
            }
        else:
            cached_session["status"] = "completed"
        session_store.save_session(f"interview_session:{session_id}", cached_session)
        
        # update application status to interview_done
        app_id = cached_session.get("application_id")
        if app_id:
            all_sessions = session_store.get_all_sessions()
            for key, val in all_sessions.items():
                if key.startswith("applications:") and isinstance(val, list):
                    for app in val:
                        if app.get("id") == app_id:
                            app["status"] = "interview_done"
                            session_store.save_session(key, val)
                            break
                            
        state = {
            "interview_session_id": session_id,
            "transcript": req.transcript,
            "code_snapshot": req.code_snapshot,
            "passport_skills": [],
            "job_description": "Technical Interview",
            "recruiter_mcqs": []
        }
        background_tasks.add_task(summarizer_graph.invoke, state)
        return {"status": "summarizing"}
    # --- DEMO BYPASS END ---
    
    # Ensure it's marked as complete immediately
    client.table("interview_sessions").update({"status": "completed"}).eq("id", session_id).execute()
    
    # Also update the application status to interview_done
    session = client.table("interview_sessions").select("application_id").eq("id", session_id).single().execute()
    if session.data and session.data.get("application_id"):
        client.table("applications").update({"status": "interview_done"}).eq("id", session.data["application_id"]).execute()
    
    state = {
        "interview_session_id": session_id,
        "transcript": req.transcript,
        "code_snapshot": req.code_snapshot,
        "passport_skills": [],
        "job_description": "",
        "recruiter_mcqs": []
    }
    background_tasks.add_task(summarizer_graph.invoke, state)
    return {"status": "summarizing"}

@router.get("/interviews/{session_id}/summary")
def get_interview_summary(session_id: str, user: dict = Depends(require_recruiter)):
    client = get_supabase()
    user_id = user["user_id"]
    
    # --- DEMO BYPASS START ---
    from app.services import session_store
    cached_session = session_store.get_session(f"interview_session:{session_id}")
    if cached_session or user_id == "00000000-0000-0000-0000-000000000002" or not client:
        if cached_session and cached_session.get("summary"):
            return {"id": session_id, "summary": cached_session["summary"]}
        return {"id": session_id, "summary": None, "status": "processing"}
    # --- DEMO BYPASS END ---
    
    resp = client.table("interview_sessions").select("summary").eq("id", session_id).single().execute()
    if resp.data and resp.data.get("summary"):
        return {"id": session_id, "summary": resp.data["summary"]}
    
    return {"id": session_id, "summary": None, "status": "processing"}

@router.websocket("/ws/live-interview/{session_id}/{role}")
async def live_interview_endpoint(websocket: WebSocket, session_id: str, role: str):
    await manager.connect(session_id, role, websocket)
    
    # Fetch real data for the AI co-pilot
    client = get_supabase()
    job_desc = "Technical Interview"
    target_skills = []

    try:
        session_data = client.table("interview_sessions").select("*, applications(*, jobs(*, job_briefs(*)), candidates(*, profiles(*)))").eq("id", session_id).single().execute()
        
        if session_data.data:
            app = session_data.data.get("applications", {})
            job = app.get("jobs", {})
            job_desc = job.get("description", "Technical Interview")
            candidate = app.get("candidates", {})
            target_skills = candidate.get("extracted_skills", [])
    except Exception as e:
        print(f"WS Supabase Fetch Error (expected in demo mode): {e}")

    state = {
        "interview_session_id": session_id,
        "job_description": job_desc,
        "passport_skills": target_skills,
        "recruiter_mcqs": [],
        "focus_areas": [],
        "transcript": [],
        "question_count": 0,
        "current_phase": "intro",
        "last_user_message": ""
    }

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type in ["candidate_speech", "recruiter_speech"]:
                user_role = "candidate" if msg_type == "candidate_speech" else "recruiter"
                state["transcript"].append({"role": user_role, "content": data["text"]})
                state["last_user_message"] = data["text"]
                await manager.broadcast(session_id, data)
                
            elif msg_type == "code_update":
                await manager.broadcast(session_id, data)
                
            elif msg_type == "request_bot_suggestion":
                # Request the AI graph for the next question
                result = await bot_interview_graph.ainvoke(state)
                suggestion = result.get("next_bot_message", "Can you walk me through your code and the complexity?")
                
                rec_ws = manager.rooms.get(session_id, {}).get("recruiter")
                if rec_ws:
                    await rec_ws.send_json({
                        "type": "bot_suggestion",
                        "text": suggestion
                    })
                    
            elif msg_type == "approve_bot_question":
                state["transcript"].append({"role": "assistant", "content": data["text"]})
                await manager.broadcast(session_id, {
                    "type": "bot_speaks",
                    "text": data["text"]
                })
                
            elif msg_type in ["offer", "answer", "ice_candidate", "candidate_webrtc_ready"]:
                await manager.send_to_peer(session_id, role, data)
                
    except WebSocketDisconnect:
        manager.disconnect(session_id, role)
    except Exception as e:
        print(f"WS Error: {e}")
        try:
            manager.disconnect(session_id, role)
        except:
            pass
