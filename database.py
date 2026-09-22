import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Load .env only for local development
if os.getenv("VERCEL_ENV") is None:
    load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

class MissingSupabaseClient:
    def __getattr__(self, name):
        raise RuntimeError(
            "Supabase client is not initialized. Please set SUPABASE_URL and SUPABASE_KEY in your .env file or environment variables."
        )

if url and key:
    supabase: Client = create_client(url, key)
else:
    print("[WARNING] SUPABASE_URL and SUPABASE_KEY are not set. Please set them in .env for full database access.", file=sys.stderr)
    supabase = MissingSupabaseClient()