import os
import sys

from dotenv import load_dotenv
from supabase import Client, create_client


def get_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def create_supabase_client() -> Client:
    load_dotenv()
    supabase_url = get_env_var("SUPABASE_URL")
    supabase_key = get_env_var("SUPABASE_SERVICE_KEY")
    return create_client(supabase_url, supabase_key)


def main() -> int:
    try:
        supabase = create_supabase_client()

        # Connectivity check against PostgREST.
        # If auth/key is valid, a missing table returns a controlled DB error
        # rather than an auth error.
        try:
            response = (
                supabase.table("__connection_probe__")
                .select("*")
                .limit(1)
                .execute()
            )
            print("Supabase connection successful.")
            print(f"Probe response: {response}")
            return 0
        except Exception as probe_error:
            message = str(probe_error)
            # Expected for the probe table; still proves network/auth is valid.
            if "PGRST205" in message and "__connection_probe__" in message:
                print("Supabase connection successful.")
                print("Probe table is missing (expected), but API/auth is reachable.")
                return 0
            raise
    except Exception as error:
        print("Supabase connection failed.")
        print(f"Error type: {type(error).__name__}")
        print(f"Error: {error!r}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
