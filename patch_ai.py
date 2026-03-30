import sys

ai_path = r'e:\rezsrch\ResearchHub-AI\backend\services\ai_service.py'
with open(ai_path, 'r', encoding='utf-8') as f:
    content = f.read()

task_config = """    "research_report": {
        "route": "research_report",
        "task_slot": "pipeline",
        "longform": True,
        "temperature": 0.25,
        "max_tokens": 6000,
        "timeout_seconds": max(30, int(os.getenv("AI_RESEARCH_REPORT_TIMEOUT_SECONDS", "120") or 120)),
        "cacheable": True,
    },
"""

if '"research_report": {' not in content:
    target1 = '    "compare_papers": {'
    content = content.replace(target1, task_config + target1)

report_task = """
def generate_research_report_task(
    *,
    groq_client: Any,
    db: Any,
    user_id: str,
    context: str,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    \"\"\"
    Generate a highly structured JSON multi-paper research report.
    \"\"\"
    system_prompt = (
        "You are an expert AI research scientist producing a comprehensive literature review. "
        "Synthesize the provided research papers into a structured report. "
        "DO NOT hallucinate. Do not make up citations. "
        "You MUST return the output strictly as a valid JSON object matching this schema exactly:\\n"
        "{\\n"
        '  "title": "Generated title of the report",\\n'
        '  "abstract": "Executive summary...",\\n'
        '  "key_themes": ["Theme 1", "Theme 2"],\\n'
        '  "literature_overview": "Overview of the landscape...",\\n'
        '  "methodology_trends": "Trends in methods...",\\n'
        '  "consensus_findings": "What papers agree on...",\\n'
        '  "conflicting_views": "Where the papers disagree...",\\n'
        '  "research_gaps": ["Gap 1", "Gap 2"],\\n'
        '  "future_directions": ["Direction 1", "Direction 2"],\\n'
        '  "conclusion": "Final concluding remarks..."\\n'
        "}"
    )

    query = "Synthesize the following research context into a report:\\n\\n"
    if topic:
        query += f"Focus Topic / Query: {topic}\\n\\n"
    query += f"Context:\\n{context}\\n"

    return run_structured_json_task(
        groq_client=groq_client,
        db=db,
        user_id=user_id,
        task_type="research_report",
        query=query,
        system_prompt=system_prompt,
        model_overrides={"response_format": {"type": "json_object"}},
        timeout_seconds=120,
    )
"""

if 'def generate_research_report_task' not in content:
    content += report_task

with open(ai_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Patched ai_service.py successfully')
