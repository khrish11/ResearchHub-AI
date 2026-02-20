import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

# Only create the Groq client when an API key is provided. Otherwise keep
# `client` as None so import-time failures are avoided and callers can
# handle unavailability at runtime.
if api_key:
    client = Groq(api_key=api_key)
else:
    client = None
    print("Warning: GROQ_API_KEY not found in environment variables. AI calls will be disabled; set GROQ_API_KEY to enable them.")

MODEL_CONFIG = {
    "model": "llama-3.3-70b-versatile",
    "temperature": 0.3,
    "max_tokens": 2000,
    "top_p": 0.9
}
