import os
import sys
import subprocess
import time
import socket
import json
import urllib.request
import urllib.error

# Add backend folder to python path so we can import app modules directly
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

class DebuggerWorker:
    def __init__(self, name: str):
        self.name = name

    def run(self) -> tuple[bool, str]:
        raise NotImplementedError()

# 1. EnvConfigWorker
class EnvConfigWorker(DebuggerWorker):
    def __init__(self):
        super().__init__("Environment and Config Worker")

    def run(self) -> tuple[bool, str]:
        report = []
        success = True
        
        # Check if backend/.env exists
        env_path = os.path.join("backend", ".env")
        if os.path.exists(env_path):
            report.append(f"[OK] backend/.env file found.")
            # Read and check OPENAI_API_KEY
            openai_found = False
            with open(env_path, "r") as f:
                for line in f:
                    if "OPENAI_API_KEY" in line and "=" in line:
                        parts = line.split("=")
                        val = parts[1].strip().strip('"').strip("'")
                        if val and not val.startswith("sk-..."):
                            openai_found = True
            if openai_found:
                report.append("[OK] OPENAI_API_KEY is configured with a real key value.")
            else:
                report.append("[WARN] OPENAI_API_KEY is not set or still has default placeholder value. Agent graphs might fail on LLM invocations.")
        else:
            report.append("[INFO] backend/.env file not found. Creating one from .env.example...")
            try:
                example_path = os.path.join("backend", ".env.example")
                if os.path.exists(example_path):
                    with open(example_path, "r") as src, open(env_path, "w") as dest:
                        dest.write(src.read())
                    report.append("[OK] backend/.env created successfully. Please fill in your OPENAI_API_KEY if needed.")
                else:
                    report.append("[ERROR] backend/.env.example not found. Cannot auto-create .env.")
                    success = False
            except Exception as e:
                report.append(f"[ERROR] Failed to copy .env: {e}")
                success = False

        # Check ports
        def check_port(port: int) -> bool:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('127.0.0.1', port)) == 0

        if check_port(8000):
            report.append("[INFO] Port 8000 (Backend) is currently active / in use.")
        else:
            report.append("[INFO] Port 8000 (Backend) is free.")

        if check_port(5173):
            report.append("[INFO] Port 5173 (Frontend) is currently active / in use.")
        else:
            report.append("[INFO] Port 5173 (Frontend) is free.")

        return success, "\n".join(report)

# 2. BackendLinterWorker
class BackendLinterWorker(DebuggerWorker):
    def __init__(self):
        super().__init__("Backend Lint and Syntax Check Worker")

    def run(self) -> tuple[bool, str]:
        report = []
        success = True
        
        backend_dir = os.path.join("backend", "app")
        if not os.path.exists(backend_dir):
            return False, f"[ERROR] Backend app folder not found at {backend_dir}"

        report.append(f"Checking syntax of all Python files in {backend_dir}...")
        
        import py_compile
        errors = []
        for root, dirs, files in os.walk(backend_dir):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    try:
                        py_compile.compile(full_path, doraise=True)
                    except py_compile.PyCompileError as e:
                        errors.append(f"Syntax error in {file}: {e}")
                        success = False
        
        if success:
            report.append("[OK] All backend Python files compiled with correct syntax.")
        else:
            report.extend(errors)

        return success, "\n".join(report)

# 3. EndpointTesterWorker
class EndpointTesterWorker(DebuggerWorker):
    def __init__(self):
        super().__init__("HTTP Endpoint Tester Worker")

    def run(self) -> tuple[bool, str]:
        report = []
        success = True
        
        # Check if backend is running, if not launch uvicorn temporarily
        backend_process = None
        started_temp_backend = False
        
        # Helper to check port
        def check_port(port: int) -> bool:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('127.0.0.1', port)) == 0

        if not check_port(8000):
            report.append("[INFO] Starting a temporary backend process for API testing...")
            try:
                # Run uvicorn as a subprocess
                backend_process = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                    cwd="backend",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                started_temp_backend = True
                # Wait for port to open
                for _ in range(15):
                    time.sleep(1)
                    if check_port(8000):
                        report.append("[OK] Temporary backend process started successfully on port 8000.")
                        break
                else:
                    report.append("[ERROR] Temporary backend process failed to start or bind to port 8000.")
                    # Clean up
                    backend_process.kill()
                    return False, "\n".join(report)
            except Exception as e:
                return False, f"[ERROR] Failed to launch backend: {e}"
        else:
            report.append("[INFO] Reusing existing backend service on port 8000.")

        # Test health check
        try:
            req = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3)
            data = json.loads(req.read().decode('utf-8'))
            if data.get("status") == "ok":
                report.append("[OK] Health endpoint (/health) is returning status 'ok'.")
            else:
                report.append(f"[WARN] Health endpoint returned unexpected payload: {data}")
        except Exception as e:
            report.append(f"[ERROR] Failed to query /health endpoint: {e}")
            success = False

        # Test Candidate Demo Login
        try:
            login_data = json.dumps({
                "email": "demo.candidate@skillbridge.dev",
                "password": "Demo@1234"
            }).encode('utf-8')
            req = urllib.request.Request(
                "http://127.0.0.1:8000/api/auth/login",
                data=login_data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                res_payload = json.loads(resp.read().decode('utf-8'))
                if "token" in res_payload and res_payload.get("role") == "candidate":
                    report.append("[OK] Candidate demo login is returning valid JWT bypass token.")
                else:
                    report.append(f"[ERROR] Candidate demo login returned invalid payload: {res_payload}")
                    success = False
        except Exception as e:
            report.append(f"[ERROR] Candidate demo login endpoint failed: {e}")
            success = False

        # Test Recruiter Demo Login
        try:
            login_data = json.dumps({
                "email": "demo.recruiter@techcorp.com",
                "password": "Demo@1234"
            }).encode('utf-8')
            req = urllib.request.Request(
                "http://127.0.0.1:8000/api/auth/login",
                data=login_data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                res_payload = json.loads(resp.read().decode('utf-8'))
                if "token" in res_payload and res_payload.get("role") == "recruiter":
                    report.append("[OK] Recruiter demo login is returning valid JWT bypass token.")
                else:
                    report.append(f"[ERROR] Recruiter demo login returned invalid payload: {res_payload}")
                    success = False
        except Exception as e:
            report.append(f"[ERROR] Recruiter demo login endpoint failed: {e}")
            success = False

        # Clean up temporary process
        if started_temp_backend and backend_process:
            report.append("[INFO] Stopping temporary backend process...")
            backend_process.terminate()
            try:
                backend_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                backend_process.kill()
            report.append("[OK] Temporary backend process stopped.")

        return success, "\n".join(report)

# 4. AgentRunnerWorker
class AgentRunnerWorker(DebuggerWorker):
    def __init__(self):
        super().__init__("LangGraph Agents Diagnostic Worker")

    def run(self) -> tuple[bool, str]:
        report = []
        success = True
        
        # Load dotenv so OPENAI_API_KEY is available
        from dotenv import load_dotenv
        load_dotenv("backend/.env")
        
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key or openai_key.startswith("sk-..."):
            report.append("[WARN] Skipping direct LLM graph execution tests. Set a valid OPENAI_API_KEY to test LLM reasoning.")
            return success, "\n".join(report)

        report.append("Initializing LangGraph agent direct test invocations...")
        
        # Test Resume Parser State Compilation
        try:
            from app.agents.graphs.resume_parser_graph import resume_parser_graph
            report.append("[OK] Loaded resume_parser_graph compilation.")
        except Exception as e:
            report.append(f"[ERROR] Failed to load/compile resume_parser_graph: {e}")
            success = False

        # Test Test Generator Graph
        try:
            from app.agents.graphs.test_generator_graph import test_generator_graph
            report.append("[OK] Loaded test_generator_graph compilation.")
        except Exception as e:
            report.append(f"[ERROR] Failed to load/compile test_generator_graph: {e}")
            success = False

        # Test Passport Issuer Graph
        try:
            from app.agents.graphs.passport_issuer_graph import passport_issuer_graph
            report.append("[OK] Loaded passport_issuer_graph compilation.")
        except Exception as e:
            report.append(f"[ERROR] Failed to load/compile passport_issuer_graph: {e}")
            success = False

        return success, "\n".join(report)

# 5. FrontendSanityWorker
class FrontendSanityWorker(DebuggerWorker):
    def __init__(self):
        super().__init__("Frontend Sanity and Build Check Worker")

    def run(self) -> tuple[bool, str]:
        report = []
        success = True
        
        # Check package.json
        pkg_path = os.path.join("frontend", "package.json")
        if not os.path.exists(pkg_path):
            return False, f"[ERROR] Frontend package.json not found at {pkg_path}"

        report.append("[OK] Frontend package.json found.")
        
        # Check node_modules
        node_modules_path = os.path.join("frontend", "node_modules")
        if not os.path.exists(node_modules_path):
            report.append("[WARN] node_modules not found in frontend. Frontend might need 'npm install'.")
        else:
            report.append("[OK] node_modules found in frontend directory.")

        return success, "\n".join(report)

# Orchestrator
class MasterDebuggerOrchestrator:
    def __init__(self):
        self.workers = [
            EnvConfigWorker(),
            BackendLinterWorker(),
            EndpointTesterWorker(),
            AgentRunnerWorker(),
            FrontendSanityWorker()
        ]

    def run_all(self):
        print("="*60)
        print("            SKILLBRIDGE MASTER DEBUGGER ORCHESTRATOR            ")
        print("="*60)
        
        overall_success = True
        reports = []
        
        for idx, worker in enumerate(self.workers, 1):
            print(f"\n[{idx}/{len(self.workers)}] Running: {worker.name}...")
            print("-" * 50)
            try:
                success, details = worker.run()
                if not success:
                    overall_success = False
                status_str = "SUCCESS" if success else "FAILED"
                print(f"Status: {status_str}")
                print("Details:")
                print(details)
                reports.append((worker.name, success, details))
            except Exception as e:
                overall_success = False
                print(f"Status: EXCEPTION")
                print(f"Error: {e}")
                reports.append((worker.name, False, f"Exception occurred: {e}"))
            print("-" * 50)
            
        print("\n" + "="*60)
        print("                    FINAL DIAGNOSTICS REPORT                    ")
        print("="*60)
        for name, success, _ in reports:
            icon = "[OK]" if success else "[FAIL]"
            print(f" {icon:<6} {name:<40} : {'PASSED' if success else 'FAILED'}")
        print("="*60)
        
        if overall_success:
            print("\nALL SYSTEMS GO! The SkillBridge demo is ready to run successfully.")
        else:
            print("\nSOME CHECKS FAILED. Please review the diagnostic errors above.")
            sys.exit(1)

if __name__ == "__main__":
    orchestrator = MasterDebuggerOrchestrator()
    orchestrator.run_all()
