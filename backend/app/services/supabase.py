import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_RESUME_BUCKET = os.getenv("SUPABASE_RESUME_BUCKET", "resumes")

# Check for placeholder/unconfigured values
is_placeholder = (
    not SUPABASE_URL or 
    not SUPABASE_KEY or 
    "your-project" in SUPABASE_URL or 
    "your-anon-key" in SUPABASE_KEY
)

if is_placeholder:
    print("WARNING: Supabase credentials not found or placeholder values detected. Running in database-free DEMO mode.")
    supabase_client: Client = None
else:
    try:
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"WARNING: Failed to initialize Supabase client: {e}. Falling back to demo mode.")
        supabase_client: Client = None

def get_supabase() -> Client:
    return supabase_client
