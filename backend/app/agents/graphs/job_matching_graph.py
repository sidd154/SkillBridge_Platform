import json
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.supabase import get_supabase
from app.config import settings

class JobMatchingState(TypedDict):
    candidate_id: str
    passport_skills: List[Dict[str, Any]]
    all_active_jobs: List[Dict[str, Any]]
    ranked_jobs: List[Dict[str, Any]]

def load_jobs_node(state: JobMatchingState):
    client = get_supabase()
    if not client:
        return {"all_active_jobs": []}
    resp = client.table("jobs").select("*, recruiters!inner(company_name)").eq("is_active", True).execute()
    return {"all_active_jobs": resp.data if resp.data else []}

def match_and_rank_node(state: JobMatchingState):
    jobs = state.get("all_active_jobs", [])
    skills = state.get("passport_skills", [])
    
    if not jobs:
        return {"ranked_jobs": []}
        
    llm = ChatOpenAI(model=settings.AI_MODEL_NAME, temperature=0.1)
    
    sys = """You are an AI job matcher. For each job, compute match_score (0-100), match_reason (1 sentence), skill_overlap, skill_gaps against the candidate's verified passport skills. Return a JSON array sorted by match_score desc."""
    msg = f"Candidate Skills: {json.dumps(skills)}\nJobs: {json.dumps(jobs)}"
    
    try:
        resp = llm.invoke([SystemMessage(content=sys), HumanMessage(content=msg)])
        ranked = json.loads(resp.content.replace('```json\n', '').replace('```', ''))
        return {"ranked_jobs": ranked}
    except Exception as e:
        # Fallback simple rank
        return {"ranked_jobs": jobs}

def save_rankings_node(state: JobMatchingState):
    # Depending on optimization, rank could be streamed directly to frontend or cached in DB
    return {"candidate_id": state.get("candidate_id")}

def build_job_matching_graph():
    builder = StateGraph(JobMatchingState)
    builder.add_node("load_jobs_node", load_jobs_node)
    builder.add_node("match_and_rank_node", match_and_rank_node)
    builder.add_node("save_rankings_node", save_rankings_node)
    
    builder.set_entry_point("load_jobs_node")
    builder.add_edge("load_jobs_node", "match_and_rank_node")
    builder.add_edge("match_and_rank_node", "save_rankings_node")
    builder.add_edge("save_rankings_node", END)
    
    return builder.compile()

job_matching_graph = build_job_matching_graph()
