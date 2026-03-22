import os
import re

BACKEND_DIR = r"e:\rezsrch\ResearchHub-AI\backend"
RESEARCH_PY = os.path.join(BACKEND_DIR, "repositories", "research.py")

print("Starting refactor...")

with open(RESEARCH_PY, "r", encoding="utf-8") as f:
    rcontent = f.read()

# 1. Strip SqlAlchemyResearchRepository
idx1 = rcontent.find("class SqlAlchemyResearchRepository:")
idx2 = rcontent.find("class FirebaseResearchRepository:")
if idx1 != -1 and idx2 != -1 and idx1 < idx2:
    rcontent = rcontent[:idx1] + rcontent[idx2:]
    print("Removed SqlAlchemyResearchRepository.")

# 2. Cleanup `get_research_repository`
repo_func_start = rcontent.find("def get_research_repository(")
if repo_func_start != -1:
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

# 5. Rename Repo* to original
# Also fix the type hints: e.g. `Optional[User | RepoUser]` -> `Optional[User]`
# Wait, if we rename RepoUser to User, `User | User` is redundant, but it's fine.
dataclasses = ["User", "Workspace", "Paper", "Chat", "SearchHistory", "SessionState", "WorkspaceDocument", "WorkspaceFile", "DataRightsRequest"]
for cls in dataclasses:
    rcontent = re.sub(rf'\bRepo{cls}\b', cls, rcontent)

# Clean up redundant unions like `User | User`
for cls in dataclasses:
    rcontent = rcontent.replace(f"{cls} | {cls}", cls)

with open(RESEARCH_PY, "w", encoding="utf-8") as f:
    f.write(rcontent)
print("Updated research.py")

# 6. Process Routers and Main
for root, _, files in os.walk(BACKEND_DIR):
    for fl in files:
        if fl.endswith(".py") and fl not in ["research.py", "database.py", "models.py", "migrate_sql_to_firebase.py"]:
            filepath = os.path.join(root, fl)
            with open(filepath, "r", encoding="utf-8") as f:
                fcontent = f.read()
            
            orig = fcontent
            # Replace `from repositories.research import` with `from repositories.research import`
            # Wait, `research.py` now exports User, Workspace etc.
            fcontent = re.sub(r'from repositories.research import', 'from repositories.research import', fcontent)
            
            # Remove `            fcontent = re.sub(r'            
            # Remove any left-over sqlalchemy depending on the file
            fcontent = re.sub(r'from sqlalchemy\..*?import.*?\n', '', fcontent)
            fcontent = re.sub(r'            
            # Special logic for main.py
            if fl == "main.py":
                fcontent = re.sub(r'if \(os.getenv\("STORAGE_BACKEND"\).*?\n\s+                fcontent = re.sub(r'if STORAGE_BACKEND == "sqlalchemy":.*?(?=if STORAGE_BACKEND == "firebase":)', '', fcontent, flags=re.DOTALL)
                # Cleanup the health check outputs to not use engine
                fcontent = re.sub(r'\*\*\(\{"database_url": str\(engine\.url\)\} if engine is not None else \{\}\),', '', fcontent)
                
            if orig != fcontent:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(fcontent)
                print(f"Updated {fl}")

print("Done.")
