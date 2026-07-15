from typing import TypedDict, Annotated
from operator import add


class SessionState(TypedDict, total=False):
    user_query: str
    refined_query: str
    user_mode: str
    retrieved_papers: list
    shortlisted_faculty: list
    shown_faculty_ids: list
    identified_gaps: list
    human_feedback: str
    session_stage: str
    iteration_count: int
    selected_faculty: dict | None
    email_draft: str
    email_approved: bool
    email_sent: bool
    collaboration_score: float
    faculty_workload: dict
    project_suggestions: list
    trending_topics: list
    faculty_search_history: list
    pending_confirmation: bool
    vector_store_initialized: bool
    retriever_initialized: bool
    messages: Annotated[list, add]
    node_history: list
    last_node: str
    _detail_result: dict
    _paper_result: dict
    _gap_result: dict
    _collab_result: dict
    _project_suggestions: list
    _workload_result: dict
    _workload_sort: str
    _alternate_faculty: dict
    _alternate_message: str
    _select_message: str
    _email_message: str
    _validator_message: str
    _report: str
    _topics_result: dict
    _chat_reply: str
    _stats_result: dict
