import re
import os

files_to_fix = [
    'e:/rezsrch/ResearchHub-AI/backend/routers/research_agent.py',
    'e:/rezsrch/ResearchHub-AI/backend/routers/papers.py',
]

for filepath in files_to_fix:
    print(f"Processing {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Endpoints: `db: Session = Depends(get_db),` -> usually on its own line
    # Sometimes it's `    db: Session = Depends(get_db),`
    content = re.sub(r'^\s*db:\s*Session\s*=\s*Depends\(get_db\),?\s*\n?', '', content, flags=re.MULTILINE)

    # 2. Function definitions: `db: Session, ` -> empty
    content = re.sub(r'db:\s*Session,?\s*', '', content)

    # 3. Handle specific function calls that used to receive `db` as first argument
    funcs_with_db = [
        '_repo_for_db',
        '_research_repo',
        '_owned_workspace_or_404',
        '_find_workspace_paper',
        '_setup_workspace_context',
        '_get_workspace_paper',
        '_assign_citations'
    ]
    for func in funcs_with_db:
        # e.g., `_setup_workspace_context(db, ` -> `_setup_workspace_context(`
        # but also `db` could be just `db` (if it was the only argument), e.g., `_repo_for_db(db)` -> `_repo_for_db()`
        content = re.sub(fr'{func}\(\s*db,\s*', f'{func}(', content)
        content = re.sub(fr'{func}\(\s*db\s*\)', f'{func}()', content)

    # 4. _repo_for_db and _research_repo are now useless, we can just replace calls to them with get_research_repository().
    # But wait, they are already defined without `db`. It's easier to just leave their definitions returning `get_research_repository()` without `db`.
    content = re.sub(r'get_research_repository\(\s*db\s*\)', r'get_research_repository()', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("done")
