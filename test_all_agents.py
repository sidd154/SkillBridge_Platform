import os
import sys
import json
import traceback

# Add backend folder to python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

# Load dotenv
from dotenv import load_dotenv
load_dotenv("backend/.env")

print("=" * 60)
print("             SKILLBRIDGE AGENT INTEGRATION TEST             ")
print("=" * 60)

def run_agent_test(name, graph_import_path, graph_name, input_data):
    print(f"\n[TESTING] {name}...")
    print("-" * 50)
    try:
        # Dynamic import
        module = __import__(graph_import_path, fromlist=[graph_name])
        graph = getattr(module, graph_name)
        
        print("Invoking graph...")
        result = graph.invoke(input_data)
        
        print("Invocation Success!")
        print("Keys returned:", list(result.keys()))
        if "error" in result and result["error"]:
            print(f"WARN: Agent returned error state: {result['error']}")
            return False, f"Returned error: {result['error']}"
            
        # Sample output preview
        preview = {k: v for k, v in result.items() if k not in ["raw_text", "github_raw_html", "leetcode_raw_html"]}
        print("Output preview (excluding large HTML/raw text):")
        print(json.dumps(preview, indent=2)[:800] + ("..." if len(json.dumps(preview)) > 800 else ""))
        return True, "Passed"
    except Exception as e:
        print(f"FAILED: Exception occurred during testing:")
        traceback.print_exc()
        return False, str(e)

# 1. Resume Parser Graph
resume_input = {
    "pdf_path": os.path.abspath("sample_resume.pdf") if os.path.exists("sample_resume.pdf") else os.path.abspath("backend/storage/resumes/00000000-0000-0000-0000-000000000001/0e65089e-6432-4c66-855e-4c270f6efc86.pdf"),
    "candidate_id": "00000000-0000-0000-0000-000000000001",
    "raw_text": "",
    "extracted_skills": [],
    "tenth_marks": "",
    "twelfth_marks": "",
    "github_link": "",
    "leetcode_link": "",
    "linkedin_link": "",
    "error": ""
}

# 2. Test Generator Graph
test_generator_input = {
    "candidate_id": "00000000-0000-0000-0000-000000000001",
    "extracted_skills": [
        {"skill_name": "Python", "proficiency_claimed": "advanced"},
        {"skill_name": "React", "proficiency_claimed": "intermediate"}
    ],
    "generated_questions": [],
    "session_id": "",
    "error": "",
    "retry_count": 0
}

# 3. Passport Issuer Graph - Pass Flow
passport_pass_input = {
    "session_id": "test-session-pass",
    "candidate_id": "00000000-0000-0000-0000-000000000001",
    "questions": [
        {"question_id": "q1", "correct_answer": "A"},
        {"question_id": "q2", "correct_answer": "B"}
    ],
    "answers": {
        "q1": "A",
        "q2": "B"
    },
    "extracted_skills": [{"skill_name": "Python", "proficiency_claimed": "advanced"}],
    "proctoring_score": 95.0,
    "score": 0.0,
    "passed": False,
    "error": ""
}

# 4. Passport Issuer Graph - Fail/Roadmap Flow
passport_fail_input = {
    "session_id": "test-session-fail",
    "candidate_id": "00000000-0000-0000-0000-000000000001",
    "questions": [
        {"question_id": "q1", "correct_answer": "A"},
        {"question_id": "q2", "correct_answer": "B"}
    ],
    "answers": {
        "q1": "B",
        "q2": "A"
    },
    "extracted_skills": [{"skill_name": "Python", "proficiency_claimed": "advanced"}],
    "proctoring_score": 95.0,
    "score": 0.0,
    "passed": False,
    "error": ""
}

# 5. Portfolio Analyzer Graph
portfolio_input = {
    "candidate_id": "00000000-0000-0000-0000-000000000001",
    "github_link": "https://github.com/torvalds",
    "leetcode_link": "https://leetcode.com/u/torvalds",
    "github_raw_html": "",
    "leetcode_raw_html": "",
    "github_score": 0.0,
    "leetcode_score": 0.0,
    "total_portfolio_score": 0.0,
    "error": ""
}

# 6. Job Matching Graph
job_matching_input = {
    "candidate_id": "00000000-0000-0000-0000-000000000001",
    "passport_skills": [
        {"skill_name": "Python", "proficiency_level": "advanced", "verified": True},
        {"skill_name": "SQL", "proficiency_level": "intermediate", "verified": True}
    ],
    "all_active_jobs": [
        {
            "id": "job-1",
            "job_title": "Senior Backend Developer",
            "job_description": "Required 5+ years of experience with Python, FastAPI, and SQL data modeling to build highly concurrent microservices.",
            "skills": ["Python", "SQL"],
            "experience": 5
        },
        {
            "id": "job-2",
            "job_title": "React Developer",
            "job_description": "Build premium frontend user interfaces with React, Tailwind CSS, and state management.",
            "skills": ["React"],
            "experience": 2
        }
    ],
    "ranked_jobs": []
}

# 7. Brief Generator Graph
brief_generator_input = {
    "job_id": "test-job-123",
    "job_title": "FastAPI Developer",
    "job_description": "We need a developer to write high performance endpoints with FastAPI, write tests, and deploy to Docker.",
    "skills": ["Python", "FastAPI"],
    "experience": 3,
    "recruiter_id": "00000000-0000-0000-0000-000000000002",
    "focus_areas": [],
    "recruiter_mcqs": [],
    "instructions": "",
    "error": ""
}

# 8. Bot Interview Graph
bot_interview_input = {
    "application_id": "demo-app-id",
    "interview_session_id": "demo-interview-session-id",
    "job_description": "Backend FastAPI Developer",
    "passport_skills": [{"skill_name": "Python", "proficiency_level": "advanced"}],
    "recruiter_mcqs": [],
    "focus_areas": ["Concurrency", "Async programming"],
    "transcript": [
        {"role": "bot", "content": "Welcome! Let's start the technical assessment. Can you explain what async/await does in Python?"}
    ],
    "last_user_message": "async/await is used to write asynchronous code, allowing the program to perform other tasks while waiting for I/O operations.",
    "next_bot_message": "",
    "current_phase": "technical",
    "question_count": 1,
    "follow_up_depth": 0,
    "error": ""
}

# 9. Summarizer Graph
summarizer_input = {
    "interview_session_id": "demo-interview-session-id",
    "transcript": [
        {"role": "bot", "content": "Welcome! Let's start. Can you explain what async/await does in Python?"},
        {"role": "candidate", "content": "async/await is used to write asynchronous code, allowing the program to perform other tasks while waiting for I/O operations."},
        {"role": "bot", "content": "Excellent. How do you handle exceptions in async tasks?"},
        {"role": "candidate", "content": "We can wrap the code inside try-except block, or use asyncio.gather with return_exceptions=True."}
    ],
    "passport_skills": [{"skill_name": "Python"}],
    "job_description": "Backend FastAPI Developer",
    "recruiter_mcqs": [],
    "code_snapshot": "async def test():\n    try:\n        await call_api()\n    except Exception as e:\n        log_error(e)",
    "summary": {}
}

tests = [
    ("Resume Parser Graph", "app.agents.graphs.resume_parser_graph", "resume_parser_graph", resume_input),
    ("Test Generator Graph", "app.agents.graphs.test_generator_graph", "test_generator_graph", test_generator_input),
    ("Passport Issuer Graph (Pass flow)", "app.agents.graphs.passport_issuer_graph", "passport_issuer_graph", passport_pass_input),
    ("Passport Issuer Graph (Fail flow)", "app.agents.graphs.passport_issuer_graph", "passport_issuer_graph", passport_fail_input),
    ("Portfolio Analyzer Graph", "app.agents.graphs.portfolio_analyzer_graph", "portfolio_analyzer_graph", portfolio_input),
    ("Job Matching Graph", "app.agents.graphs.job_matching_graph", "job_matching_graph", job_matching_input),
    ("Brief Generator Graph", "app.agents.graphs.brief_generator_graph", "brief_generator_graph", brief_generator_input),
    ("Bot Interview Graph", "app.agents.graphs.bot_interview_graph", "bot_interview_graph", bot_interview_input),
    ("Summarizer Graph", "app.agents.graphs.summarizer_graph", "summarizer_graph", summarizer_input),
]

summary_report = []

for name, import_path, graph_name, input_data in tests:
    success, reason = run_agent_test(name, import_path, graph_name, input_data)
    summary_report.append((name, success, reason))

print("\n" + "=" * 60)
print("                   AGENT INTEGRATION REPORT                   ")
print("=" * 60)
all_success = True
for name, success, reason in summary_report:
    status = "[OK] PASSED" if success else "[FAIL] FAILED"
    if not success:
        all_success = False
    print(f" - {name:<35} : {status:<15} ({reason})")
print("=" * 60)

if all_success:
    print("\nALL AGENTS VERIFIED AND WORKING SUCCESSFULLY!")
    sys.exit(0)
else:
    print("\nSOME AGENT TESTS FAILED. PLEASE CHECK DETAILED LOGS ABOVE.")
    sys.exit(1)
