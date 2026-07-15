"""
AcademiMatch — Research Matching Agent
A conversational CLI that helps students find faculty matches and helps
professors track workload, trends, gaps, and collaboration opportunities.
"""

import os, sys, warnings, threading, time, itertools, re

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ["ACADEMIMATCH_SILENT"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore")

import logging
logging.disable(logging.CRITICAL)
for m in ("chromadb", "langchain", "langchain_core", "langchain_community",
          "langgraph", "sentence_transformers", "transformers"):
    logging.getLogger(m).setLevel(logging.CRITICAL)

import tqdm
_orig = tqdm.tqdm.__init__
def _silent(self, *a, **kw): kw["disable"] = True; return _orig(self, *a, **kw)
tqdm.tqdm.__init__ = _silent

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ════════════════════════════════════════════════════════════════════════
#  THEME — colors, symbols, layout constants
# ════════════════════════════════════════════════════════════════════════

C_RST  = "\033[0m";   C_B    = "\033[1m";   C_DIM  = "\033[2m";  C_IT = "\033[3m"
C_RED  = "\033[91m";  C_GRN  = "\033[92m";  C_YEL  = "\033[93m"
C_BLU  = "\033[94m";  C_MAG  = "\033[95m";  C_CYN  = "\033[96m"
C_BRED = "\033[1;91m";C_BGRN = "\033[1;92m";C_BYEL = "\033[1;93m"
C_BBLU = "\033[1;94m";C_BMAG = "\033[1;95m";C_BCYN = "\033[1;96m"
C_WHT  = "\033[97m";  C_BWHT = "\033[1;97m"

W = 80  # inner content width for simple boxes

# Status glyphs used consistently across every workload / capacity view
ICON_AT_CAPACITY = "●"
ICON_NEARLY_FULL = "◐"
ICON_MODERATE    = "◑"
ICON_AVAILABLE   = "○"
STATUS_ICON = {
    "AT CAPACITY": ICON_AT_CAPACITY,
    "NEARLY FULL": ICON_NEARLY_FULL,
    "MODERATE":    ICON_MODERATE,
    "AVAILABLE":   ICON_AVAILABLE,
}
STATUS_COLOR = {
    "AT CAPACITY": C_BRED,
    "NEARLY FULL": C_BYEL,
    "MODERATE":    C_DIM,
    "AVAILABLE":   C_BGRN,
}

RANK_MARK = ["1st", "2nd", "3rd", "4th", "5th"]

SPINNER = itertools.cycle(["◐", "◓", "◑", "◒"])
_spinner_running = False


def start_spinner(msg="Thinking"):
    global _spinner_running
    _spinner_running = True
    def spin():
        while _spinner_running:
            s = next(SPINNER)
            sys.stdout.write(f"\r  {C_CYN}{s}{C_RST}  {C_DIM}{msg}...{C_RST}  ")
            sys.stdout.flush()
            time.sleep(0.08)
    threading.Thread(target=spin, daemon=True).start()


def stop_spinner():
    global _spinner_running
    _spinner_running = False
    time.sleep(0.1)
    sys.stdout.write("\r" + " " * 55 + "\r")
    sys.stdout.flush()


# ════════════════════════════════════════════════════════════════════════
#  LAYOUT HELPERS
# ════════════════════════════════════════════════════════════════════════

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _vislen(s: str) -> int:
    return len(_ANSI_RE.sub("", s))


def pad(content: str, width: int) -> str:
    return content + " " * max(0, width - _vislen(content))


BOX_TOP   = f"  {C_DIM}╭{'─' * W}╮{C_RST}"
BOX_BOT   = f"  {C_DIM}╰{'─' * W}╯{C_RST}"
BOX_SEP   = f"  {C_DIM}├{'─' * W}┤{C_RST}"
BOX_SIDE  = f"  {C_DIM}│{C_RST}"


def box_line(text: str = "") -> str:
    return f"{BOX_SIDE} {pad(text, W - 2)}{BOX_SIDE}"


def box(title: str, *lines: str):
    print(BOX_TOP)
    print(box_line(f"{C_B}{title}{C_RST}"))
    if lines:
        print(BOX_SEP)
        for l in lines:
            print(box_line(l))
    print(BOX_BOT)


def divider(char: str = "─"):
    print(f"  {C_DIM}{char * W}{C_RST}")


def section(label: str, color: str = C_BBLU):
    print(f"\n  {color}▸ {label}{C_RST}")


def mode_switch(old: str, new: str):
    accent = C_BMAG if new == "PROFESSOR" else C_BBLU
    print()
    print(f"  {C_BYEL}╭{'─' * W}╮{C_RST}")
    line = f"  Switched to {new} mode"
    print(f"  {C_BYEL}│{C_RST} {accent}{pad(line.replace(new, f'{accent}{new}{C_YEL}'), W - 2)}{C_BYEL}{C_RST}")
    print(f"  {C_BYEL}╰{'─' * W}╯{C_RST}")


from src.graph import build_graph
from src.faculty_loader import load_faculty_profiles

graph = build_graph()

state = {
    'user_query': '', 'refined_query': '', 'user_mode': 'STUDENT', 'iteration_count': 0,
    'shown_faculty_ids': [], 'shortlisted_faculty': [], 'selected_faculty': None,
    'email_draft': '', 'pending_confirmation': False, 'email_sent': False,
    'email_approved': False, 'retrieved_papers': [], 'identified_gaps': [],
    'collaboration_score': 0.0, 'faculty_workload': {}, 'project_suggestions': [],
    'trending_topics': [], 'faculty_search_history': [], 'human_feedback': '',
    'session_stage': 'INIT', 'vector_store_initialized': True,
    'retriever_initialized': True, 'messages': [], 'node_history': [], 'last_node': ''
}

# ════════════════════════════════════════════════════════════════════════
#  PREFACE — banner + live stats dashboard
# ════════════════════════════════════════════════════════════════════════

TITLE_RAW = [
    "  █████╗   ██████╗  █████╗  ██████╗  ███████╗ ███╗   ███╗ ██╗ ███╗   ███╗  █████╗  ████████╗  ██████╗ ██╗  ██╗",
    "  ██╔══██╗ ██╔════╝ ██╔══██╗ ██╔══██╗ ██╔════╝ ████╗ ████║ ██║ ████╗ ████║ ██╔══██╗ ╚══██╔══╝ ██╔════╝ ██║  ██║",
    "  ███████║ ██║      ███████║ ██║  ██║ █████╗   ██╔████╔██║ ██║ ██╔████╔██║ ███████║    ██║    ██║      ███████║",
    "  ██╔══██║ ██║      ██╔══██║ ██║  ██║ ██╔══╝   ██║╚██╔╝██║ ██║ ██║╚██╔╝██║ ██╔══██║    ██║    ██║      ██╔══██║",
    "  ██║  ██║ ╚██████╗ ██║  ██║ ██████╔╝ ███████╗ ██║ ╚═╝ ██║ ██║ ██║ ╚═╝ ██║ ██║  ██║    ██║    ╚██████╗ ██║  ██║",
    "  ╚═╝  ╚═╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚══════╝ ╚═╝     ╚═╝ ╚═╝ ╚═╝     ╚═╝ ╚═╝  ╚═╝    ╚═╝     ╚═════╝ ╚═╝  ╚═╝",
]
W_INNER = max(len(r) for r in TITLE_RAW)
TITLE = [f"{C_B}{r:<{W_INNER}}{C_RST}" for r in TITLE_RAW]
SUB = f"{C_BMAG}ACADEMIMATCH{C_RST}  {C_DIM}│{C_RST}  Research Matching Agent  {C_DIM}│{C_RST}  {C_DIM}ReAct Graph v1.0{C_RST}"
SUB = f"  {SUB}{' ' * max(0, W_INNER - _vislen(SUB) - 2)}"
BDR_TOP = "╔" + ("═" * (W_INNER + 2)) + "╗"
BDR_MID = "╠" + ("═" * (W_INNER + 2)) + "╣"
BDR_BOT = "╚" + ("═" * (W_INNER + 2)) + "╝"

print(f"\n{C_B}{C_BCYN}  {BDR_TOP}{C_RST}")
for row in TITLE:
    print(f"  {C_B}{C_BCYN}║{C_RST} {row} {C_B}{C_BCYN}║{C_RST}")
print(f"  {C_B}{C_BCYN}{BDR_MID}{C_RST}")
print(f"  {C_B}{C_BCYN}║{C_RST} {SUB} {C_B}{C_BCYN}║{C_RST}")
print(f"  {C_B}{C_BCYN}{BDR_BOT}{C_RST}\n")

start_spinner("Loading faculty database")
graph.invoke(dict(state, user_query="boot", session_stage="INIT"))
state["shown_faculty_ids"] = []
state["shortlisted_faculty"] = []
stop_spinner()

# ──── Live stats dashboard ────
profiles = load_faculty_profiles()
cse = [p for p in profiles if p["department"] == "CSE"]
ece = [p for p in profiles if p["department"] == "ECE"]
areas = {a for p in profiles for a in p.get("research_areas", [])}
total_pubs = sum(p.get("papers", 0) for p in profiles)
total_cites = sum(p.get("citations", 0) for p in profiles)
avail_count = len([p for p in profiles if p.get("current_projects", 0) < p.get("max_projects", 1)])

COL1, COL2, COL3 = 23, 23, 22
widths = [COL1, COL2, COL3]


def cell(contents, ws):
    return " | ".join(f"  {pad(c, w)}  " for c, w in zip(contents, ws))


# inner_w is the *visible* width of a full content row (between the outer
# "| " and " |"), derived from cell()'s own layout instead of a separate
# hand-computed formula. This guarantees it can never drift out of sync
# with what cell() actually prints.
inner_w = _vislen(cell(["" for _ in widths], widths))


def row_line(content: str = "") -> str:
    return f"  {C_DIM}|{C_RST} {pad(content, inner_w)} {C_DIM}|{C_RST}"


# Build the top/bottom border by mechanically converting a blank content
# row into dashes/plus-signs, character for character — so it is always
# exactly as wide as the rows it wraps, no matter what the column widths
# or padding are.
_blank_row = row_line()
_plain_row = _ANSI_RE.sub("", _blank_row)
_border = "".join("+" if ch == "|" else ("-" if ch != " " else "-") for ch in _plain_row)
# keep the leading indent as plain spaces, only the boxed part becomes dashes
_indent_len = len(_plain_row) - len(_plain_row.lstrip(" "))
border_line = f"  {C_DIM}{_border[_indent_len:]}{C_RST}"

print(border_line)
print(row_line(f"{C_B}YOUR RESEARCH FACULTY{C_RST}"))
print(row_line())
r1 = cell([f"{C_B}{len(profiles)} Professors{C_RST}",
           f"{C_BBLU}{len(cse)} in Computer Science{C_RST}",
           f"{C_BMAG}{len(ece)} in Electronics{C_RST}"], widths)
print(row_line(r1))
r2 = cell([f"{C_B}{len(areas)} Research Areas{C_RST}",
           f"{C_B}{total_pubs} Publications{C_RST}",
           f"{C_B}{total_cites:,} Citations{C_RST}"], widths)
print(row_line(r2))
r3 = cell([f"{C_BGRN}{avail_count} Accepting Projects{C_RST}",
           f"{C_DIM}Both modes active{C_RST}",
           f"{C_DIM}Natural language{C_RST}"], widths)
print(row_line(r3))
print(border_line)
print(f"\n  {C_DIM}Hey! Just talk naturally — I'll figure out what you need.{C_RST}")
print(f"  {C_DIM}Your mode: {C_BBLU}STUDENT{C_RST}{C_DIM}. Type 'help' or ask me anything.{C_RST}\n")


# ════════════════════════════════════════════════════════════════════════
#  HELP SCREEN
# ════════════════════════════════════════════════════════════════════════

def help_screen(mode: str):
    box(f"What can I help with? ({mode} mode)")
    if mode == "STUDENT":
        rows = [
            ("'who works on NLP?'",          "find professors by research area"),
            ("'tell me about Dr. Sharma'",   "get a professor's full profile"),
            ("'list all professors'",        "see all 15 faculty members"),
            ("'what topics are there?'",     "browse all research areas"),
            ("'show me another one'",        "see the next match"),
            ("'what project could I do?'",   "get research project ideas"),
            ("'I want to email Dr. Sharma'", "draft a message to a professor"),
        ]
        accent = C_BBLU
    else:
        rows = [
            ("'what's trending in AI?'",        "latest research papers and trends"),
            ("'who works on NLP?'",             "map faculty expertise"),
            ("'can I collaborate with Dr. X?'", "find complementary partners"),
            ("'what are we missing?'",          "research gap analysis"),
            ("'how busy is Dr. Iyer?'",         "check one person's workload"),
            ("'who is busy?'",                  "all 15, busiest first, color-coded"),
            ("'who is the least busy?'",        "all 15, most available first"),
            ("'who is working on most projects?'", "all 15 with project counts"),
            ("'who has the most citations?'",   "top 5 most-cited faculty"),
            ("'who has the most papers?'",      "top 5 most-published faculty"),
            ("'who has the most score?'",       "top 5 match scores from last search"),
            ("'list all professors'",           "see all faculty"),
            ("'what topics are covered?'",      "browse research areas"),
        ]
        accent = C_BMAG

    # Column width is derived from the longest command string (+2 for a
    # guaranteed gap) instead of a hardcoded number, so a command that is
    # exactly as long as the old fixed width can never collide with the
    # description column again.
    cmd_col = max(max(len(c) for c, _ in rows), len("switch to professor / student")) + 2

    for cmd, desc in rows:
        print(box_line(f"  {accent}{pad(cmd, cmd_col)}{C_RST} {C_DIM}{desc}{C_RST}"))
    print(box_line())
    print(box_line(f"  {C_BYEL}{pad('switch to professor / student', cmd_col)}{C_RST} {C_DIM}change your mode{C_RST}"))
    print(BOX_BOT)


# ════════════════════════════════════════════════════════════════════════
#  DISPLAY — renders the result of every graph turn
# ════════════════════════════════════════════════════════════════════════

def _workload_row(r: dict) -> str:
    color = STATUS_COLOR.get(r["status"], C_DIM)
    icon = STATUS_ICON.get(r["status"], "○")
    name_col = f"{color}{icon} {r['name']:<26s}{C_RST}"
    dept_col = f"{C_DIM}({r['department']}){C_RST}"
    load_col = f"{color}{r['current_projects']}/{r['max_projects']}{C_RST} projects"
    return f"  {name_col} {dept_col}  —  {load_col}  {C_DIM}[{r['status']}]{C_RST}"


def display(state: dict):
    stage = state.get("session_stage", "?")

    if stage in ("MATCH", "AFTER_MATCH", "MAP", "AFTER_MAP"):
        results = state.get("shortlisted_faculty", [])
        if not results:
            print(f"\n  {C_DIM}Hmm, I couldn't find anyone for that. Want to try a different area?{C_RST}\n")
            return
        section(f"Here's who I found ({len(results)} matches)")
        for i, r in enumerate(results, 1):
            pct = r["hybrid_pct"]
            print(f"\n  {C_B}{i}. {C_BBLU}{r['name']}{C_RST}  {C_DIM}({r['department']}){C_RST}  —  {C_BGRN}{pct}% match{C_RST}")
            print(f"     {C_DIM}{', '.join(r['research_areas'][:3])}{C_RST}")
            print(f"     {r['papers']} papers  |  {r['citations']:,} citations  |  {r['current_projects']}/{r['max_projects']} projects")

    elif stage == "AFTER_DETAIL":
        detail = state.get("_detail_result", {})
        matches = detail.get("all_matches", [])
        if detail.get("ambiguous"):
            section("I found a few people with that name — which one?", C_BYEL)
            for i, m in enumerate(matches, 1):
                print(f"  {C_B}{i}.{C_RST} {m['name']} ({m['department']}) — {C_DIM}{', '.join(m.get('research_areas', [])[:3])}{C_RST}")
        elif matches:
            p = matches[0]
            print(f"\n  {C_B}{p['name']}{C_RST}  {C_DIM}│  {p['department']}{C_RST}")
            divider()
            print(f"  {C_BBLU}Research:{C_RST}")
            for ra in p.get("research_areas", []):
                print(f"    {C_DIM}~{C_RST} {ra}")
            print(f"\n  {C_BBLU}About:{C_RST}")
            for s in p.get("bio", "").replace("Dr. ", "").split(". "):
                if s.strip():
                    print(f"    {C_DIM}{s.strip()}.{C_RST}")
            print(f"\n  {p.get('papers', 0)} papers  |  {p.get('citations', 0):,} citations  |  {p.get('current_projects', 0)}/{p.get('max_projects', 0)} projects")
            print(f"  {C_DIM}{p.get('email', '')}{C_RST}")
        else:
            print(f"\n  {C_DIM}I don't know that professor. Try 'tell me about Dr. Priya Sharma'?{C_RST}")

    elif stage == "AFTER_ALTERNATE":
        alt = state.get("_alternate_faculty", {})
        if alt:
            print(f"\n  {C_BGRN}▸{C_RST} How about {C_BBLU}{alt['name']}{C_RST} ({C_DIM}{alt['department']}{C_RST})?")
            print(f"     {C_DIM}{', '.join(alt.get('research_areas', [])[:3])}{C_RST}")
        else:
            print(f"\n  {C_DIM}That's everyone from this search. Try a new query!{C_RST}")

    elif stage == "ALL_SHOWN":
        print(f"\n  {C_DIM}You've seen everyone from this search. Try a new query!{C_RST}")

    elif stage == "AFTER_PROJECTS":
        projects = state.get("project_suggestions", [])
        section(f"Here are {len(projects)} project ideas for you")
        for i, p in enumerate(projects, 1):
            print(f"\n  {C_B}{i}. {p.get('title', '?')}{C_RST}")
            print(f"     {C_DIM}With:{C_RST} {', '.join(p.get('related_faculty', []))}  |  {C_DIM}{p.get('difficulty', '')}{C_RST}")
            print(f"     {C_DIM}Skills: {', '.join(p.get('required_skills', []))}{C_RST}")

    elif stage == "AFTER_PAPER_SEARCH":
        papers = state.get("retrieved_papers", [])
        pr = state.get("_paper_result", {})
        section(f"Here's what's trending ({len(papers)} papers found)")
        syn = pr.get("synthesis", "")
        if syn:
            print(f"\n  {C_DIM}{syn[:400]}{C_RST}")
        print()
        for i, p in enumerate(sorted(papers, key=lambda x: x.get("citations", 0), reverse=True)[:5], 1):
            print(f"  {C_B}{i}.{C_RST} {p.get('title', '?')}  {C_DIM}({p.get('year', '?')}){C_RST}")
            print(f"     {C_GRN}{p.get('citations', 0):,}{C_RST} citations")

    elif stage == "AFTER_GAP_ANALYSIS":
        gr = state.get("_gap_result", {})
        gaps, covered = gr.get("gaps", []), gr.get("covered", [])
        if gaps:
            section("Areas nobody covers yet", C_BRED)
            for g in gaps:
                print(f"    {C_BYEL}!{C_RST} {C_B}{g['subtopic']}{C_RST} — {g['paper_count']} trending papers, no faculty covering it")
        if covered:
            section("Areas with active faculty", C_BGRN)
            for c in covered:
                names = ", ".join(c.get("faculty_covering", [])[:2])
                print(f"    {C_BGRN}+{C_RST} {C_B}{c['subtopic']}{C_RST} — {c['faculty_count']} faculty ({C_DIM}{names}{C_RST})")

    elif stage == "AFTER_COLLAB_MATCH":
        cr = state.get("_collab_result", {})
        section(f"People who complement {cr.get('target_name', '?')}'s expertise")
        for i, m in enumerate(cr.get("matches", [])[:5], 1):
            pct = round(m.get("collaboration_score", 0) * 100, 1)
            cap = f" {C_BRED}[at capacity]{C_RST}" if m.get("at_capacity") else ""
            print(f"\n  {C_B}{i}. {C_BBLU}{m['name']}{C_RST}  {C_DIM}({m['department']}){C_RST}  —  {C_BGRN}{pct}%{C_RST}{cap}")
            print(f"     {C_DIM}{', '.join(m['research_areas'][:3])}  |  Projects: {m['workload_ratio']}{C_RST}")

    elif stage == "AFTER_WORKLOAD_CHECK":
        # Single-person workload lookup: "how busy is Dr. X?"
        wr = state.get("_workload_result", {})
        if not wr.get("found"):
            print(f"\n  {C_DIM}I couldn't find that person. Try 'how busy is Dr. Iyer?' or 'who is busy?'{C_RST}")
        else:
            color = STATUS_COLOR.get(wr.get("status", ""), C_YEL)
            icon = STATUS_ICON.get(wr.get("status", ""), "○")
            print(f"\n  {C_B}{icon} {wr.get('target_name', '?')}{C_RST}  {C_DIM}({wr.get('department', '?')}){C_RST}")
            print(f"  {color}{wr.get('current_projects', '?')}/{wr.get('max_projects', '?')}{C_RST} projects — {color}{wr.get('status', '')}{C_RST}")
            for alt in wr.get("alternatives", [])[:3]:
                print(f"  {C_DIM}▸ Alternative:{C_RST} {alt['name']} — {alt['current_projects']}/{alt['max_projects']} projects")

    elif stage == "AFTER_WORKLOAD_LIST":
        # "who is busy" / "who is the least busy" / "who is working on most projects"
        # These always show ALL 15 faculty, sorted, color-coded — never truncated.
        wr = state.get("_workload_result", {})
        if not wr.get("found"):
            print(f"\n  {C_DIM}I couldn't find any workload data. Try 'who is busy?'{C_RST}")
        else:
            all_rows = wr.get("all", [])
            sort_dir = state.get("_workload_sort", "busiest")
            sort_label = {
                "least": "Least busy first",
                "most_projects": "Most projects first",
                "busiest": "Busiest first",
            }.get(sort_dir, "Busiest first")

            n_cap = len(wr.get("at_capacity", []))
            n_near = len(wr.get("nearly_full", []))
            n_avail = len(wr.get("available", []))

            section(f"Workload Overview — {len(all_rows)} professors ({sort_label})")
            print(f"  {C_DIM}{ICON_AT_CAPACITY} {n_cap} at capacity"
                  f"   {ICON_NEARLY_FULL} {n_near} nearly full"
                  f"   {ICON_AVAILABLE} {n_avail} available{C_RST}\n")
            for r in all_rows:
                print(_workload_row(r))

    elif stage == "AFTER_LIST":
        results = state.get("shortlisted_faculty", [])
        section(f"All {len(results)} professors")
        for i, r in enumerate(results, 1):
            dc = C_BBLU if r["department"] == "CSE" else C_BMAG
            print(f"\n  {C_B}{i:>2}.{C_RST} {dc}{r['name']:<27s}{C_RST} {C_DIM}({r['department']}){C_RST}  {r['current_projects']}/{r['max_projects']} projects")
            print(f"      {C_DIM}{', '.join(r['research_areas'][:3])}{C_RST}")

    elif stage == "AFTER_TOPICS":
        tr = state.get("_topics_result", {})
        area_map = tr.get("area_map", {})
        section(f"{tr.get('total_areas', 0)} research areas across {tr.get('total_faculty', 0)} professors")
        for area, names in sorted(area_map.items(), key=lambda x: x[0].lower()):
            print(f"  {C_BBLU}{area:<42s}{C_RST} {C_DIM}{len(names)} professor{'s' if len(names) > 1 else ''}{C_RST}")

    elif stage == "AFTER_SELECT":
        sel = state.get("selected_faculty", {})
        if sel:
            print(f"\n  {C_BGRN}▸{C_RST} Got it — {C_BBLU}{sel['name']}{C_RST} ({C_DIM}{sel['department']}{C_RST})")
            print(f"     {C_DIM}{', '.join(sel.get('research_areas', []))}{C_RST}")
            print(f"  {C_DIM}Say 'email' and I'll draft a message for you.{C_RST}")
        else:
            print(f"\n  {C_DIM}Nothing to select yet — try a search first?{C_RST}")

    elif stage == "AWAITING_EMAIL_CONFIRMATION":
        draft = state.get("email_draft", "")
        section("Here's the draft")
        divider()
        for dl in draft.split("\n"):
            if dl.strip():
                print(f"  {C_DIM}{dl}{C_RST}")
        divider()
        print(f"  {C_BYEL}Type YES to send, EDIT or NO to cancel.{C_RST}")

    elif stage == "EMAIL_SENT":
        print(f"\n  {C_BGRN}✓ Email sent! [SIMULATED]{C_RST}")

    elif stage in ("EMAIL_CANCELLED", "EMAIL_NOT_SENT", "NO_CONFIRMATION", "NO_DRAFT",
                   "NO_FACULTY_SELECTED", "INVALID_SELECT", "NO_FACULTY_TO_SELECT"):
        msg = state.get("_email_message") or state.get("_select_message") or "That didn't work — try again?"
        print(f"\n  {C_BRED}{msg}{C_RST}")

    elif stage == "AFTER_STATS":
        sr = state.get("_stats_result", {})
        if sr:
            section(sr.get("title", "Stats"), C_BMAG)
            for rank, item in enumerate(sr.get("items", [])[:5]):
                medal = f"{C_BYEL}{RANK_MARK[rank]}{C_RST}" if rank < len(RANK_MARK) else "  "
                print(f"  {medal}  {C_B}{item}{C_RST}")

    elif stage == "AFTER_REPORT":
        report = state.get("_report", "")
        if report:
            print()
            for l in report.split("\n"):
                print(f"  {C_DIM}{l}{C_RST}")

    elif stage == "AFTER_CHAT":
        reply = state.get("_chat_reply", "I'm here to help with research matching! Try asking about faculty, topics, projects, or research trends.")
        print(f"\n  {C_DIM}{reply}{C_RST}")

    elif stage == "AFTER_MODE_SWITCH":
        mode_switch("STUDENT" if state.get("user_mode") == "PROFESSOR" else "PROFESSOR",
                    state.get("user_mode", "STUDENT"))


def main():
    prompt_color = C_BBLU
    print(f"{C_B}{prompt_color}  You:{C_RST} ", end="")
    iteration = 0

    while True:
        try:
            cmd = input().strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {C_DIM}Goodbye!{C_RST}\n")
            break

        if not cmd:
            print(f"{C_B}{prompt_color}  You:{C_RST} ", end="")
            continue
        if cmd.lower() in ("exit", "quit", "bye"):
            print(f"\n  {C_DIM}Goodbye!{C_RST}\n")
            break
        if cmd.lower() in ("help", "h", "?"):
            help_screen(state.get("user_mode", "STUDENT"))
            print(f"{C_B}{prompt_color}  You:{C_RST} ", end="")
            continue

        iteration += 1
        prev_stage = state.get("session_stage", "")
        state["user_query"] = cmd
        state["iteration_count"] = iteration

        if cmd.strip().lower() in ("yes", "no", "send", "edit", "cancel"):
            state["session_stage"] = "APPROVE_EMAIL" if prev_stage == "AWAITING_EMAIL_CONFIRMATION" else "PENDING"
        else:
            state["session_stage"] = "PENDING"
        state["pending_confirmation"] = False

        start_spinner()
        try:
            result = graph.invoke(state)
        except Exception as e:
            stop_spinner()
            print(f"\n  {C_BRED}Something went wrong: {e}{C_RST}")
            print(f"{C_B}{prompt_color}  You:{C_RST} ", end="")
            continue
        stop_spinner()

        for k, v in result.items():
            state[k] = v
        display(state)

        new_mode = state.get("user_mode", "STUDENT")
        prompt_color = C_BMAG if new_mode == "PROFESSOR" else C_BBLU
        print(f"\n{C_B}{prompt_color}  You:{C_RST} ", end="")


if __name__ == "__main__":
    main()
