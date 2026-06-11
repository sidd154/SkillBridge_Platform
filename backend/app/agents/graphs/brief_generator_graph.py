import json
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.supabase import get_supabase
from app.config import settings

class BriefGeneratorState(TypedDict, total=False):
    job_id: str
    job_title: str
    job_description: str
    skills: List[str]
    experience: int
    recruiter_id: str
    focus_areas: List[str]
    recruiter_mcqs: List[Dict[str, Any]]
    instructions: str
    error: str

def generate_brief_node(state: BriefGeneratorState):
    # Check if OpenAI is configured
    import os
    openai_key = os.getenv("OPENAI_API_KEY")
    is_openai_configured = openai_key and len(openai_key) > 30 and "your-key" not in openai_key and "your-proj" not in openai_key
    
    if not is_openai_configured:
        # Fallback pre-populated demo brief
        return {
            "focus_areas": ["State management", "Performance", "Coding style"],
            "recruiter_questions": [
                {"question": "How do you handle global state in React?", "expected_keywords": ["Redux", "Zustand", "Context"]},
                {"question": "What is the difference between useMemo and useCallback?", "expected_keywords": ["memoize", "value", "function"]},
                {"question": "How do you structure CSS styles in React?", "expected_keywords": ["Tailwind", "CSS Modules", "Styled Components"]}
            ],
            "mass_mcqs": [
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
            ],
            "instructions": "Be friendly and evaluate standard React frontend capabilities."
        }

    llm = ChatOpenAI(model=settings.AI_MODEL_NAME, temperature=0.2)
    sys_prompt = """You are an expert technical recruiter AI. Given a job description, skills, and experience required, you must construct a bot interview brief.
Generate exactly:
2. recruiter_questions: A list of 3-5 open-ended or technical questions the bot should ask in the live session.
3. mass_mcqs: A list of exactly 5 multiple-choice questions to test applicants before they can apply. Include options and the correct answer.
4. instructions: A paragraph of instructions giving the bot a persona (e.g. "You are a friendly but rigorous Senior Engineer evaluating backend skills...").

Return ONLY a valid JSON object matching this schema:
{
  "focus_areas": ["str", "str"],
  "recruiter_questions": [
    {"question": "str", "expected_keywords": ["str", "str"]}
  ],
  "mass_mcqs": [
    {"question": "str", "options": ["A", "B", "C", "D"], "correct_answer": "A"}
  ],
  "instructions": "str"
}
No markdown formatting or explanation."""

    msg = f"Title: {state.get('job_title')}\nExperience: {state.get('experience')} years\nSkills: {', '.join(state.get('skills', []))}\nDescription: {state.get('job_description')}"
    
    try:
        resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=msg)])
        json_str = resp.content.replace('```json\n', '').replace('```', '')
        result = json.loads(json_str)
        return {
            "focus_areas": result.get("focus_areas", []),
            "recruiter_questions": result.get("recruiter_questions", []),
            "mass_mcqs": result.get("mass_mcqs", []),
            "instructions": result.get("instructions", "")
        }
    except Exception as e:
        return {"error": f"Failed to generate brief: {e}"}

# Demo ID is now in settings.DEMO_RECRUITER_ID

def save_brief_node(state: BriefGeneratorState):
    if state.get("error"):
        return {"error": state["error"]}
        
    client = get_supabase()
    job_id = state.get("job_id")
    recruiter_id = state.get("recruiter_id")
    
    insert_data = {
        "job_id": job_id,
        "focus_areas": state.get("focus_areas"),
        "recruiter_mcqs": state.get("recruiter_questions"),
        "mass_mcqs": state.get("mass_mcqs"),
        "instructions": state.get("instructions")
    }
    
    if recruiter_id == settings.DEMO_RECRUITER_ID or not client:
        from app.services import session_store
        session_store.save_session(f"brief:{job_id}", insert_data)
        return {"instructions": state.get("instructions")}

    if client:
        client.table("job_briefs").upsert(insert_data, on_conflict="job_id").execute()
        
    return {"instructions": state.get("instructions")}

def build_brief_generator_graph():
    builder = StateGraph(BriefGeneratorState)
    builder.add_node("generate_brief_node", generate_brief_node)
    builder.add_node("save_brief_node", save_brief_node)
    
    builder.set_entry_point("generate_brief_node")
    builder.add_edge("generate_brief_node", "save_brief_node")
    builder.add_edge("save_brief_node", END)
    
    return builder.compile()

brief_generator_graph = build_brief_generator_graph()
