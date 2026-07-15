import os, sys, warnings

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ["ACADEMIMATCH_SILENT"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
warnings.filterwarnings("ignore")

import logging
logging.disable(logging.CRITICAL)
for m in ("chromadb","langchain","langchain_core","langchain_community",
          "langgraph","sentence_transformers","transformers"):
    logging.getLogger(m).setLevel(logging.CRITICAL)

import tqdm
_orig = tqdm.tqdm.__init__
def _silent(self, *a, **kw): kw["disable"]=True; return _orig(self,*a,**kw)
tqdm.tqdm.__init__ = _silent

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

C_RST  = "\033[0m";   C_B    = "\033[1m";   C_DIM  = "\033[2m"
C_RED  = "\033[91m";  C_GRN  = "\033[92m";  C_YEL  = "\033[93m"
C_BLU  = "\033[94m";  C_MAG  = "\033[95m";  C_CYN  = "\033[96m"
C_BRED = "\033[1;91m";C_BGRN = "\033[1;92m";C_BYEL = "\033[1;93m"
C_BBLU = "\033[1;94m";C_BMAG = "\033[1;95m";C_BCYN = "\033[1;96m"

D1 = "="*72; D2 = "-"*72
def hdr(title, color=C_BCYN):
    print(f"\n{C_B}{color}  +{D1}+{C_RST}")
    print(f"  {C_B}{color}|{C_RST} {title:<70s} {C_B}{color}|{C_RST}")
    print(f"  {C_B}{color}+{D1}+{C_RST}\n")
def sub(title):
    print(f"\n  {C_DIM}.{'-'*70}.{C_RST}")
    print(f"  {C_DIM}|{C_RST} {C_B}{title}{C_RST}")
    print(f"  {C_DIM}`{'-'*70}'{C_RST}\n")
def phase(label, color=C_CYN):
    print(f"  {color}{C_B}[{label}]{C_RST} ", end="")
def info(t):    print(f"  {C_DIM}{t}{C_RST}")
def ok(t):      print(f"  {C_BGRN} > {C_RST} {t}")
def warn(t):    print(f"  {C_BYEL} ! {C_RST} {t}")
def item(n, name, dept, score, extra=""):
    print(f"  {C_B}{n:>2}.{C_RST} {C_BBLU}{name:<27s}{C_RST} {C_DIM}({dept}){C_RST}  {C_BGRN}{score}{C_RST}{extra}")
def l(t):       print(f"       {C_DIM}{t}{C_RST}")

def mode_banner(old, new):
    c = C_BMAG if new=="PROFESSOR" else C_BBLU
    print(f"\n{C_B}{C_YEL}  +{D1}+{C_RST}")
    print(f"  {C_B}{C_YEL}|{C_RST}     {C_B}MODE SWITCH{C_RST}    {C_DIM}{old}{C_RST}  {C_BYEL}>>>{C_RST}  {c}{C_B}{new}{C_RST}")
    print(f"  {C_B}{C_YEL}+{D1}+{C_RST}\n")

from src.graph import build_graph
graph = build_graph()

state = {
    'user_query':'','refined_query':'','user_mode':'STUDENT','iteration_count':0,
    'shown_faculty_ids':[],'shortlisted_faculty':[],'selected_faculty':None,
    'email_draft':'','pending_confirmation':False,'email_sent':False,
    'email_approved':False,'retrieved_papers':[],'identified_gaps':[],
    'collaboration_score':0.0,'faculty_workload':{},'project_suggestions':[],
    'trending_topics':[],'faculty_search_history':[],'human_feedback':'',
    'session_stage':'INIT','vector_store_initialized':True,
    'retriever_initialized':True,'messages':[],'node_history':[],'last_node':''
}

def invoke(state, query, stage_override=None):
    state['user_query'] = query
    state['iteration_count'] += 1
    if stage_override: state['session_stage'] = stage_override
    result = graph.invoke(state)
    for k, v in result.items(): state[k] = v
    return state

# ──── TITLE ────
TITLE_RAW = [
    "                                                                                                  ",
    "  ▄▄▄▄▄▄                                           ▄   ▄▄▄▄                                       ",
    " █▀██▀▀▀█▄                                     █▄  ▀██████▀                                       ",
    "   ██▄▄▄█▀                          ▄          ██    ██           ▄                               ",
    "   ██▀▀█▄   ▄█▀█▄ ▄██▀█ ▄█▀█▄ ▄▀▀█▄ ████▄▄███▀ ████▄ ██     ▄███▄ ███▄███▄ ████▄ ▄▀▀█▄ ▄██▀█ ▄██▀█",
    " ▄ ██  ██   ██▄█▀ ▀███▄ ██▄█▀ ▄█▀██ ██   ██    ██ ██ ██     ██ ██ ██ ██ ██ ██ ██ ▄█▀██ ▀███▄ ▀███▄",
    " ▀██▀  ▀██▀▄▀█▄▄▄█▄▄██▀▄▀█▄▄▄▄▀█▄██▄█▀  ▄▀███▄▄██ ██ ▀█████▄▀███▀▄██ ██ ▀█▄████▀▄▀█▄███▄▄██▀█▄▄██▀",
    "                                                                           ██                     ",
    "                                                                           ▀                      ",
]
W_INNER = max(len(r) for r in TITLE_RAW)
TITLE   = [f"{C_B}{r:<{W_INNER}}{C_RST}" for r in TITLE_RAW]
SUB_LINE = f"  {C_BMAG}ACADEMIMATCH{C_RST}  |  {C_DIM}Research Matching Agent{C_RST}  |  {C_DIM}ReAct Graph v1.0{C_RST}"
SUB_LINE = f"{SUB_LINE:<{W_INNER}}"

BORDER = f"{'+' * (W_INNER + 2)}"
print(f"\n{C_B}{C_BCYN}  +{BORDER}+{C_RST}")
for row in TITLE:
    print(f"  {C_B}{C_BCYN}|{C_RST} {row} {C_B}{C_BCYN}|{C_RST}")
print(f"  {C_B}{C_BCYN}|{C_RST} {SUB_LINE} {C_B}{C_BCYN}|{C_RST}")
print(f"  {C_B}{C_BCYN}+{BORDER}+{C_RST}\n")

# Warm up silently
graph.invoke(dict(state, user_query="boot", session_stage="INIT"))
state["shown_faculty_ids"] = []; state["shortlisted_faculty"] = []

# ══ TURN 1 ══
hdr("MATCH  |  STUDENT MODE  |  Find Faculty by Research Area", C_BBLU)
phase("INPUT", C_DIM); print(f"{C_B}who works on NLP{C_RST}")
state = invoke(state, "who works on NLP")
results = state.get("shortlisted_faculty", [])
phase("RETRIEVE", C_CYN)
print(f"Hybrid search  |  {len(results)} matches  |  0.6 * vector + 0.4 * keyword")
sub("TOP MATCHES")
for i, r in enumerate(results, 1):
    item(i, r["name"], r["department"], f"{r['hybrid_pct']}%")
    l(f"{', '.join(r['research_areas'][:3])}")
    l(f"Papers: {r['papers']}  |  Citations: {r['citations']}  |  Load: {r['current_projects']}/{r['max_projects']}")
    l(f"Score: {r['score_breakdown']}")

# ══ TURN 2 ══
hdr("DETAIL  |  STUDENT MODE  |  Full Faculty Profile", C_BBLU)
phase("INPUT", C_DIM); print(f"{C_B}tell me about Dr. Priya Sharma{C_RST}")
state = invoke(state, "tell me about Dr. Priya Sharma")
detail = state.get("_detail_result", {})
matches = detail.get("all_matches", [])
if matches:
    p = matches[0]
    phase("READ", C_GRN)
    print(f"Profile loaded: {C_BBLU}{p['name']}{C_RST}  |  {C_DIM}{p['department']}{C_RST}")
    sub(f"{p['name']}  |  {p['department']}")
    print(f"  {C_BBLU}Research Areas:{C_RST}")
    for ra in p.get("research_areas", []):
        print(f"    {C_DIM}-{C_RST} {ra}")
    print(f"\n  {C_BBLU}Bio:{C_RST}")
    for sentence in p.get("bio","").replace("Dr. ","").split(". "):
        if sentence.strip(): print(f"    {C_DIM}{sentence.strip()}.{C_RST}")
    print(f"\n  {C_BBLU}Metrics:{C_RST}  Papers: {C_GRN}{p.get('papers',0)}{C_RST}  |  Citations: {C_GRN}{p.get('citations',0)}{C_RST}  |  Load: {C_YEL}{p.get('current_projects',0)}/{p.get('max_projects',0)}{C_RST}")
    print(f"  {C_BBLU}Contact:{C_RST}  {C_DIM}{p.get('email','N/A')}{C_RST}")

# ══ TURN 3 ══
hdr("PROJECT  |  STUDENT MODE  |  Research Project Suggestions", C_BBLU)
phase("INPUT", C_DIM); print(f"{C_B}what project could I do{C_RST}")
state = invoke(state, "what project could I do")
projects = state.get("project_suggestions", [])
phase("PLAN", C_MAG); print(f"Generated {len(projects)} project ideas from matched faculty")
sub("PROJECT IDEAS")
for i, proj in enumerate(projects, 1):
    print(f"  {C_B}{i}.{C_RST} {proj.get('title','?')}")
    print(f"     {C_DIM}Faculty:{C_RST} {', '.join(proj.get('related_faculty',[]))}")
    print(f"     {C_DIM}Difficulty:{C_RST} {proj.get('difficulty','N/A')}  |  {C_DIM}Skills:{C_RST} {', '.join(proj.get('required_skills',[]))}")
    print(f"     {C_DIM}{proj.get('description','')[:140]}...{C_RST}\n")

# ══ TURN 4 ══
hdr("TRANSITION  |  Switching Context", C_BYEL)
phase("INPUT", C_DIM); print(f"{C_B}switch to professor{C_RST}")
state = invoke(state, "switch to professor")
mode_banner("STUDENT", "PROFESSOR")
ok("Commands: TREND | MAP | COLLAB | GAP | WORKLOAD | EMAIL")
info("Type 'help' anytime for the full command list")

# ══ TURN 5 ══
hdr("SENSE  |  PROFESSOR MODE  |  Research Trend Analysis", C_BMAG)
phase("INPUT", C_DIM); print(f"{C_B}what's trending in AI{C_RST}")
state = invoke(state, "what's trending in AI")
papers = state.get("retrieved_papers", [])
pr = state.get("_paper_result", {})
phase("SENSE", C_CYN)
print(f"Source: {C_DIM}{pr.get('source','local')}{C_RST}  |  Papers: {len(papers)}")
syn = pr.get("synthesis","")
if syn:
    print(f"\n  {C_BBLU}Trend Synthesis:{C_RST}")
    for sl in syn.split("\n"):
        print(f"  {C_DIM}{sl.strip()}{C_RST}")
sub("SUPPORTING PAPERS")
for i, p in enumerate(sorted(papers, key=lambda x: x.get("citations",0), reverse=True)[:7], 1):
    print(f"  {C_B}{i}.{C_RST} {p.get('title','?')}")
    l(f"{p.get('year','?')}  |  {C_GRN}{p.get('citations',0)}{C_RST} citations")

# ══ TURN 6 ══
hdr("ANALYZE  |  PROFESSOR MODE  |  Collaboration Match", C_BMAG)
phase("INPUT", C_DIM); print(f"{C_B}could I collaborate with Dr. Priya Sharma{C_RST}")
state = invoke(state, "could I collaborate with Dr. Priya Sharma")
cr = state.get("_collab_result", {})
phase("ANALYZE", C_MAG)
print(f"Target: {C_BBLU}{cr.get('target_name','?')}{C_RST}  |  Scoring: complementarity + area + keyword + dept")
info("0.35 * complementarity + 0.25 * area_sim + 0.2 * kw_adjacency + dept_bonus")
info("Workload penalty applied when > 80% capacity")
sub("COLLABORATION CANDIDATES")
for i, m in enumerate(cr.get("matches",[])[:5], 1):
    pct = round(m["collaboration_score"]*100,1)
    cap = f" {C_BRED}[FULL]{C_RST}" if m.get("at_capacity") else ""
    item(i, m["name"], m["department"], f"{C_BGRN}{pct}%{C_RST}", cap)
    l(f"Areas: {', '.join(m['research_areas'][:3])}")
    l(f"Workload: {m['workload_ratio']}")

# ══ TURN 7 ══
hdr("ANALYZE  |  PROFESSOR MODE  |  Research Gap Analysis", C_BMAG)
phase("INPUT", C_DIM); print(f"{C_B}what are we missing{C_RST}")
state = invoke(state, "what are we missing")
gr = state.get("_gap_result", {})
phase("ANALYZE", C_MAG)
print(f"Cross-referencing trending topics against {gr.get('total_subtopics','?')} faculty profiles")

gaps = gr.get("gaps", [])
covered = gr.get("covered", [])
if gaps:
    print(f"\n  {C_BRED}GAPS: No faculty covers these emerging areas{C_RST}")
    for gap in gaps:
        warn(f"{C_B}{gap['subtopic']}{C_RST}: {gap['paper_count']} papers, {C_BRED}0{C_RST}/{gap['total_faculty']} faculty cover it")
if covered:
    print(f"\n  {C_BGRN}COVERED: Faculty expertise exists{C_RST}")
    for c in covered:
        names = ", ".join(c.get("faculty_covering", [])[:2])
        ok(f"{C_B}{c['subtopic']}{C_RST}: {c['faculty_count']} of {c['total_faculty']} faculty ({C_DIM}{names}{C_RST})")

phase("SELECT", C_YEL); print(f"select 1")
state = invoke(state, "select 1")
sel = state.get("selected_faculty", {})
if sel:
    print(f"{C_BGRN}  >{C_RST}  Selected: {C_BBLU}{sel['name']}{C_RST} ({C_DIM}{sel['department']}{C_RST})")
    l(f"Areas: {', '.join(sel.get('research_areas',[]))}")
    l(f"Email: {sel.get('email','N/A')}")

phase("ACT", C_GRN); print(f"email")
state = invoke(state, "email")
draft = state.get("email_draft","")
if draft:
    print(f"  Drafting email for {C_BBLU}{sel.get('name','faculty')}{C_RST}")
    sub("EMAIL DRAFT")
    for dl in draft.split("\n"):
        if dl.strip(): print(f"  {C_DIM}{dl}{C_RST}")
    print(f"\n  {C_B}{C_YEL}[PENDING CONFIRMATION]{C_RST}  Reply {C_BGRN}YES{C_RST} to send, {C_RED}EDIT/NO{C_RST} to cancel.")

# ══ TURN 8 ══
hdr("ACT  |  PROFESSOR MODE  |  Email Confirmation", C_BGRN)
phase("INPUT", C_DIM); print(f"{C_B}YES{C_RST}")
state = invoke(state, "YES", stage_override="APPROVE_EMAIL")
if state.get("email_sent"):
    phase("ACT", C_GRN); print(f"{C_BGRN}Email sent successfully [SIMULATED]{C_RST}")
    print(f"\n  {C_BGRN}To:{C_RST} {state['selected_faculty'].get('email','recipient')}")
    print(f"  {C_BGRN}Recipient:{C_RST} {state['selected_faculty'].get('name','Dr. Kapoor')}")
    print(f"\n{C_B}{C_BGRN}  +{'+'*56}+{C_RST}")
    print(f"{C_B}{C_BGRN}  |{C_RST}  {C_B} DEMO COMPLETE -- 8 of 8 turns executed successfully  {C_B}{C_BGRN}|{C_RST}")
    print(f"{C_B}{C_BGRN}  +{'+'*56}+{C_RST}\n")

# ══ HARD GATE ══
hdr("SECURITY  |  Hard Gate Verification", C_BRED)
info("Gate condition:  pending_confirmation == True  AND  user_reply == 'YES'")
info(f"{'-'*70}")

tests = [
    ("'send' instead of 'YES'   ", True,  "send",  False),
    ("'maybe' instead of 'YES'  ", True,  "maybe", False),
    ("'YES' without draft       ", False, "YES",   False),
]
all_pass = True
for desc, pending, reply, should_send in tests:
    ts = {
        'user_query': reply, 'session_stage': 'APPROVE_EMAIL',
        'pending_confirmation': pending,
        'email_draft': 'Test draft' if pending else '',
        'email_sent': False, 'selected_faculty': {},
        'user_mode': 'PROFESSOR', 'iteration_count': 1,
    }
    r = graph.invoke(ts)
    sent = r.get("email_sent", False)
    passed = sent == should_send
    all_pass = all_pass and passed
    status = f"{C_BGRN}PASS{C_RST}" if passed else f"{C_BRED}FAIL{C_RST}"
    print(f"  [{status}] {desc} email_sent={sent} (expected={should_send})")

if all_pass:
    print(f"\n{C_B}{C_BGRN}  +{'+'*56}+{C_RST}")
    print(f"{C_B}{C_BGRN}  |{C_RST}  {C_B} ALL HARD GATE EDGE CASES VERIFIED - Gate intact   {C_B}{C_BGRN}|{C_RST}")
    print(f"{C_B}{C_BGRN}  +{'+'*56}+{C_RST}\n")
