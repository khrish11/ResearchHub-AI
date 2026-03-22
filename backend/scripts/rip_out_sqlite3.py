import os
import re

BACKEND_DIR = r"e:\rezsrch\ResearchHub-AI\backend"
RESEARCH_PY = os.path.join(BACKEND_DIR, "repositories", "research.py")

print("Starting refactor...")

# Part 1: Fix research.py again in case it was partially modified or not modified
with open(RESEARCH_PY, "r", encoding="utf-8") as f:
    rcontent = f.read()

# 1. Strip SqlAlchemyResearchRepository only if it exists
idx1 = rcontent.find("class SqlAlchemyResearchRepository:")
idx2 = rcontent.find("class FirebaseResearchRepository:")
if idx1 != -1 and idx2 != -1 and idx1 < idx2:
    rcontent = rcontent[:idx1] + rcontent[idx2:]
    print("Removed SqlAlchemyResearchRepository.")

# 2. Cleanup `get_research_repository`
repo_func_start = rcontent.find("def get_research_repository(")
if repo_func_start != -1 and "SqlAlchemyResearchRepository" in rcontent[repo_func_start:]:
    new_repo_func = '''def get_research_repository() -> ResearchRepository:
    return FirebaseResearchRepository()
'''
    old_func_end = rcontent.find("def ", repo_func_start + 10)
    if old_func_end == -1: old_func_end = len(rcontent)
    rcontent = rcontent[:repo_func_start] + new_repo_func + rcontent[old_func_end:]
    print("Cleaned up get_research_repository.")

# 3. Strip _optional_db
rcontent = re.sub(r'def _optional_db\(\):.*?(?=def get_research_repository)', '', rcontent, flags=re.DOTALL)

# 4. Remove models and database imports
rcontent = re.sub(r'rcontent = re.sub(r'from repositories.research import \([\s\S]*?\)\n', '', rcontent)
rcontent = re.sub(r'from repositories.research import .*?\n', '', rcontent)
rcontent = re.sub(r'from sqlalchemy\..*?import.*?\n', '', rcontent)
rcontent = re.sub(r'rcontent = re.sub(r'try:\n\s+from sqlalchemy.*?\n\s+Session = Any\n', '', rcontent, flags=re.DOTALL)

dataclasses = ["User", "Workspace", "Paper", "Chat", "SearchHistory", "SessionState", "WorkspaceDocument", "WorkspaceFile", "DataRightsRequest"]
for cls in dataclasses:
    rcontent = re.sub(rf'\bRepo{cls}\b', cls, rcontent)
    # clean up union duplicates: 'User | User' -> 'User'
    rcontent = rcontent.replace(f"{cls} | {cls}", cls)
    rcontent = rcontent.replace(f"{cls} | Optional[{cls}]", f"Optional[{cls}]")
    rcontent = rcontent.replace(f"Optional[{cls}] | {cls}", f"Optional[{cls}]")

with open(RESEARCH_PY, "w", encoding="utf-8") as f:
    f.write(rcontent)
print("Updated research.py")

# Part 2: Fix Routers, Main, etc.
for root, dirs, files in os.walk(BACKEND_DIR):
    # DONT Traverse into .venv or __pycache__ or .pytest_cache
    dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.pytest_cache', 'alembic']]
    for fl in files:
        if fl.endswith(".py") and fl not in ["research.py", "database.py", "models.py", "migrate_sql_to_firebase.py"]:
            filepath = os.path.join(root, fl)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    fcontent = f.read()
                
                orig = fcontent
                # Fix models import
                fcontent = re.sub(r'from repositories.research import', 'from repositories.research import', fcontent)
                # Remove database
                fcontent = re.sub(r'                # Remove sqlalchemy
                fcontent = re.sub(r'from sqlalchemy\..*?import.*?\n', '', fcontent)
                fcontent = re.sub(r'                
                if fl == "main.py":
                    fcontent = re.sub(r'if \(os.getenv\("STORAGE_BACKEND"\).*?\n\s+                    fcontent = re.sub(r'if STORAGE_BACKEND == "sqlalchemy":.*?(?=if STORAGE_BACKEND == "firebase":)', '', fcontent, flags=re.DOTALL)
                    fcontent = re.sub(r'\*\*\(\{"database_url": str\(engine\.url\)\} if engine is not None else \{\}\),', '', fcontent)
                    
                if orig != fcontent:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(fcontent)
                    print(f"Updated {filepath}")
            except Exception as e:
                print(f"Failed {filepath}: {e}")

print("Done.")
