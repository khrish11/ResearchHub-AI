import sys

pc_path = r'e:\rezsrch\ResearchHub-AI\backend\services\paper_check_service.py'
with open(pc_path, 'r', encoding='utf-8') as f:
    content = f.read()

report_task = """
def aggregate_and_generate_report(
    *,
    repo: ResearchRepository,
    user_id: str,
    paper_ids: List[int],
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    sorted_pids = sorted(paper_ids)
    fp_base = f"{','.join(map(str, sorted_pids))}|{topic or ''}"
    fingerprint = hashlib.sha256(fp_base.encode("utf-8")).hexdigest()

    existing = repo.find_research_report_by_fingerprint(fingerprint)
    if existing and existing.result:
        return existing.result

    context_chunks = []
    
    for pid in sorted_pids:
        paper = repo.find_paper_for_user(pid, int(user_id))
        if not paper:
            continue
        
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            query = repo.db.collection("paper_check_jobs").where(filter=FieldFilter("paper_id", "==", pid)).where(filter=FieldFilter("status", "==", "completed")).limit(1)
            docs = list(query.stream())
            result_data = docs[0].to_dict().get("result") if docs else None
        except Exception:
            result_data = None
            
        chunk = f"Paper ID: {pid}\\nTitle: {paper.title}\\nAuthors: {paper.authors}\\nAbstract: {paper.abstract}\\n"
        
        if result_data:
            key_claims = result_data.get("key_claims", [])
            methods = result_data.get("methodology_summary", "")
            chunk += f"AI Extracted Claims: {json.dumps(key_claims)}\\nAI Methods summary: {methods}\\n"
            
        context_chunks.append(chunk)

    if not context_chunks and not topic:
        raise ValueError("You must provide either papers or a topic to generate a report.")
    
    papers_context = "\\n---\\n".join(context_chunks)
    papers_context = papers_context[:25000]
    
    from services.ai_service import generate_research_report_task
    ai_result = generate_research_report_task(
        groq_client=groq_client,
        db=repo.db,
        user_id=str(user_id),
        context=papers_context,
        topic=topic,
    )
    
    if ai_result.get("error") and not ai_result.get("parsed"):
        raise RuntimeError(f"AI Report Generation Failed: {ai_result['error']}")

    result_data = ai_result.get("parsed") or {}

    report_id = uuid4().hex
    repo.create_research_report(
        id=report_id,
        user_id=int(user_id),
        paper_ids=sorted_pids,
        topic=topic,
        fingerprint=fingerprint,
        result=result_data,
    )
    
    return result_data
"""

if 'def aggregate_and_generate_report' not in content:
    content += "\n" + report_task
    with open(pc_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched paper_check_service.py successfully")
else:
    print("Already patched paper_check_service.py")

router_path = r'e:\rezsrch\ResearchHub-AI\backend\routers\papers.py'
with open(router_path, 'r', encoding='utf-8') as f:
    router_content = f.read()

router_task = """
class GenerateReportRequest(BaseModel):
    paper_ids: List[int] = Field(default_factory=list, max_length=15)
    topic: Optional[str] = Field(default=None, max_length=1000)

@router.post("/generate-report")
async def generate_report_endpoint(
    request: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    try:
        from services.paper_check_service import aggregate_and_generate_report
        result = await asyncio.to_thread(
            aggregate_and_generate_report,
            repo=repo,
            user_id=str(current_user.id),
            paper_ids=request.paper_ids,
            topic=request.topic,
        )
        return {"result": result}
    except Exception as e:
        logger.exception("generate_report error")
        raise HTTPException(status_code=400, detail=str(e))
"""

if 'def generate_report_endpoint' not in router_content:
    if 'class ComparePapersRequest(BaseModel):' in router_content:
        target = 'class ComparePapersRequest(BaseModel):'
        router_content = router_content.replace(target, router_task + "\n" + target)
        with open(router_path, 'w', encoding='utf-8') as f:
            f.write(router_content)
        print("Patched papers.py successfully")
else:
    print("Already patched papers.py")

