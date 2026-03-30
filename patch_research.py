import sys

repo_path = r'e:\rezsrch\ResearchHub-AI\backend\repositories\research.py'
with open(repo_path, 'r', encoding='utf-8') as f:
    content = f.read()

model_code = """
@dataclass
class ResearchReport:
    id: str
    user_id: int
    paper_ids: List[int]
    topic: Optional[str] = None
    fingerprint: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=_utcnow)
"""

protocol_code = """    def create_research_report(
        self,
        *,
        id: str,
        user_id: int,
        paper_ids: List[int],
        topic: Optional[str] = None,
        fingerprint: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> ResearchReport: ...
    def get_research_report(self, report_id: str) -> Optional[ResearchReport]: ...
    def find_research_report_by_fingerprint(self, fingerprint: str) -> Optional[ResearchReport]: ...
"""

impl_init = '        self.research_reports = self.db.collection("research_reports")\n'

impl_code = """    def create_research_report(
        self,
        *,
        id: str,
        user_id: int,
        paper_ids: List[int],
        topic: Optional[str] = None,
        fingerprint: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> ResearchReport:
        doc_ref = self.research_reports.document(id)
        now = _utcnow()
        data = {
            "id": id,
            "user_id": int(user_id),
            "paper_ids": paper_ids,
            "topic": topic,
            "fingerprint": fingerprint,
            "result": result,
            "created_at": now,
        }
        doc_ref.set(data)
        return ResearchReport(**data)

    def get_research_report(self, report_id: str) -> Optional[ResearchReport]:
        snap = self.research_reports.document(report_id).get()
        if not snap.exists:
            return None
        doc = snap.to_dict() or {}
        return ResearchReport(
            id=str(doc.get("id") or ""),
            user_id=int(doc.get("user_id") or 0),
            paper_ids=doc.get("paper_ids") or [],
            topic=doc.get("topic"),
            fingerprint=doc.get("fingerprint"),
            result=doc.get("result"),
            created_at=doc.get("created_at") or _utcnow(),
        )

    def find_research_report_by_fingerprint(self, fingerprint: str) -> Optional[ResearchReport]:
        docs = list(self.research_reports.where("fingerprint", "==", fingerprint).limit(1).stream())
        if not docs:
            return None
        doc = docs[0].to_dict() or {}
        return ResearchReport(
            id=str(doc.get("id") or ""),
            user_id=int(doc.get("user_id") or 0),
            paper_ids=doc.get("paper_ids") or [],
            topic=doc.get("topic"),
            fingerprint=doc.get("fingerprint"),
            result=doc.get("result"),
            created_at=doc.get("created_at") or _utcnow(),
        )
"""

if 'class ResearchReport' not in content:
    content = content.replace("class ResearchRepository(Protocol):", model_code + "\n\nclass ResearchRepository(Protocol):")

if 'def create_research_report' not in content[:content.find('def find_paper_comparison_by_fingerprint') + 1000]:
    target2 = "    def find_paper_comparison_by_fingerprint(self, fingerprint: str) -> Optional[PaperComparison]: ..."
    content = content.replace(target2, target2 + "\n" + protocol_code)

if 'self.research_reports' not in content:
    target3 = '        self.paper_comparisons = self.db.collection("paper_comparisons")\n'
    content = content.replace(target3, target3 + impl_init)

if 'def get_research_report' not in content:
    end_of_method = content.find('    def list_pending_jobs_for_dispatch', content.find('def find_paper_comparison_by_fingerprint(self, fingerprint: str) -> Optional[PaperComparison]:'))
    if end_of_method > -1:
        content = content[:end_of_method] + impl_code + '\n' + content[end_of_method:]

with open(repo_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Patched research.py successfully')
