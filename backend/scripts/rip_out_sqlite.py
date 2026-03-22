import os
import re

BACKEND_DIR = r"e:\rezsrch\ResearchHub-AI\backend"
RESEARCH_PY = os.path.join(BACKEND_DIR, "repositories", "research.py")

# 1. Refactor research.py
with open(RESEARCH_PY, "r", encoding="utf-8") as f:
    content = f.read()

# Remove SqlAlchemyResearchRepository entirely
content = re.sub(r'class SqlAlchemyResearchRepository:.*?(?=class FirebaseResearchRepository:)', '', content, flags=re.DOTALL)
# It's possible the class name is just FirebaseResearchRepository, let's just find "class SqlAlchemy" to "class [SomethingElse]"
# Actually, let's find the exact boundaries.
content = re.sub(r'class SqlAlchemyResearchRepository:.*?\n\n\nclass ', '\n\n\nclass ', content, flags=re.DOTALL)

# Also remove SqlAlchemyResearchRepository from the factory
content = re.sub(r'def _optional_db.*?\n\ndef', 'def', content, flags=re.DOTALL)
content = re.sub(r'if backend == "firebase":\n\s+return FirebaseResearchRepository\(\)\n.*?return SqlAlchemyResearchRepository\(db\)', 'return FirebaseResearchRepository()', content, flags=re.DOTALL)
content = re.sub(r'db: Optional\[Session\] = Depends\(_optional_db\),\n\s+\)', ')', content, flags=re.DOTALL)

# Change Repo* names to their standard names
dataclasses = ["User", "Workspace", "Paper", "Chat", "SearchHistory", "SessionState", "WorkspaceDocument", "WorkspaceFile", "DataRightsRequest"]
for cls in dataclasses:
    content = re.sub(rf'\bRepo{cls}\b', cls, content)

# Remove `from repositories.research import ...`
content = re.sub(r'from repositories.research import \([^)]+\)', '', content, flags=re.DOTALL)
content = re.sub(r'content = re.sub(r'try:\n    with open(RESEARCH_PY, 'w', encoding='utf-8') as f:
    f.write(content)

# 2. Refactor routers and main
for root, _, files in os.walk(BACKEND_DIR):
    for fl in files:
        if fl.endswith(".py") and fl not in ["research.py"]:
            filepath = os.path.join(root, fl)
            with open(filepath, "r", encoding="utf-8") as f:
                f_content = f.read()
            
            orig = f_content
            # Replace `from repositories.research import ...` with `from repositories.research import ...`
            f_content = re.sub(r'from repositories.research import', 'from repositories.research import', f_content)
            # Remove `            f_content = re.sub(r'            # Find and remove any leftover sqlalchemy imports
            f_content = re.sub(r'from sqlalchemy\..*?import.*?\n', '', f_content)
            f_content = re.sub(r'            
            if f_content != orig:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f_content)

print("Refactoring complete.")
