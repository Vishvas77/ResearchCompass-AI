import os
import sys
import re

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from dotenv import load_dotenv
load_dotenv()

# Patterns are regex-matched against the full query for flexible NL understanding
STUDENT_PATTERNS = [
    # --- CHAT (casual conversation - check first) ---
    ("CHAT", r"^(hi|hey|hello|yo|sup|good\s*(morning|afternoon|evening))\b"),
    ("CHAT", r"\b(how\s*(are|r)\s*(you|u)|what('?s|s)\s*up|how('?s|s)\s*(it|things)\s*going)\b"),
    ("CHAT", r"\b(thanks?|thank\s*you|thx|ty|appreciate\s*(it|that)|cool|nice|great|awesome|wow)\b"),
    ("CHAT", r"\b(what|who)\s*(are|r)\s*(you|u)\??\s*$"),
    ("CHAT", r"\b(your\s*name|what\s*do\s*you\s*do|what\s*can\s*you\s*do)\b"),

    # --- LIST / TOPICS (most specific, check first) ---
    ("LIST", r"\b(list|show)\s+(all\s+)?(faculty|professors?|everyone|everybody)\b"),
    ("LIST", r"\b(all|every)\s+(faculty|professors?)\b"),
    ("TOPICS", r"\b(what|which|list|show)\s+(topics?|research\s*areas?|areas?|fields?|subjects?|domains?)\s*(are\s+)?(available|present|covered|offered|there)?\b"),
    ("TOPICS", r"\b(available|present|covered)\s+(topics?|research\s*areas?)\b"),
    ("TOPICS", r"\b(research\s*areas?|topics?)\s*(available|present|covered|list)?\b"),

    # --- MODE SWITCH (very specific keywords) ---
    ("MODE_SWITCH", r"\b(switch|change|go)\s+(to|into)\s+(professor|faculty|student)\s*(mode)?\b"),
    ("MODE_SWITCH", r"\b(i('?m| am)\s+(a\s+)?(professor|faculty))\b"),
    ("MODE_SWITCH", r"\b(i('?m| am)\s+(a\s+)?(student))\s*$"),
    ("MODE_SWITCH", r"\b(use|using)\s+(professor|student)\s*mode\b"),

    # --- EMAIL (specific action before general search) ---
    ("EMAIL", r"\b(want|trying|need|like)\s+to\s+(email|mail|contact|reach|write|send|draft|compose|message)\b"),
    ("EMAIL", r"\b(email|mail|contact|reach|write|draft|compose|message)\s+(dr\.?|prof(essor)?|faculty|him|her|them)\b"),
    ("EMAIL", r"\b(send|compose|draft)\s+(an?\s+)?(email|mail|message)\b"),

    # --- WORKLOAD (before DETAIL to avoid "who is" collision) ---
    ("WORKLOAD", r"\b(who|whom|which)\s+(all\s+)?(is|are)\s+(busy|at\s+capacity|full|overloaded|maxed|least\s+busy|most\s+busy|most\s+loaded|least\s+loaded)\b"),
    ("WORKLOAD", r"\b(workload|capacity|how\s+(busy|loaded|full|occupied|many\s+projects))\b"),
    ("WORKLOAD", r"\b(show|give|list|display)\s+(me\s+)?(all\s+)?(workloads?|capacity|who\s+is\s+busy)\b"),
    ("WORKLOAD", r"\b(who|whom)\s+(is|are|has|have)\s+(the\s+)?(least|most|fewest)\s+(busy|projects?|loaded|capacity|workload)\b"),
    ("WORKLOAD", r"\b(who|whom)\s+(is\s+)?(working\s+on|doing)\s+(the\s+)?(most|least|fewest)\s+projects?\b"),

    # --- STATS (who has the most X type queries) ---
    ("STATS", r"\b(who|whom)\s+(has|have|got)\s+(the\s+)?(most|least|highest|lowest|best|top)\s+(score|citations?|papers?|publications?)\b"),
    ("STATS", r"\b(most|top|highest)\s+(cited|published|citations?|papers?|score)\b"),

    # --- DETAIL (person-specific, before generic MATCH) ---
    ("DETAIL", r"\b(tell|know|learn|information|info|details?)\s+(me\s+)?(about|on|regarding)\b"),
    ("DETAIL", r"\b(who|what)\s+is\s+(dr\.?\s*)?\w+\b"),
    ("DETAIL", r"\b(profile|bio(graphy)?|background)\s+(of|on|for)\b"),
    ("DETAIL", r"\b(describe|explain|elaborate)\b.*\b(dr\.?|professor|faculty)\b"),

    # --- ALTERNATE ---
    ("ALTERNATE", r"\b(show|give)\s+me\s+(the\s+)?(next|another|other)\b"),
    ("ALTERNATE", r"\b(not|don'?t|skip)\s+(this|that)\b.*\b(show|give|next)\b"),
    ("ALTERNATE", r"\b(another|alternate)\s+(one|faculty|prof|match|result)\b"),

    # --- PROJECT ---
    ("PROJECT", r"\b(what|which|suggest|recommend|any|some)\s*(projects?|ideas?)\b"),
    ("PROJECT", r"\b(generate|suggest|give\s+me|recommend)\s+(project|idea)s?\b"),
    ("PROJECT", r"\b(what|something|anything)\s+.*\b(can|could|should)\s+(i|we)\s+(do|work\s+on|research|explore|build)\b"),

    # --- SELECT (STUDENT) ---
    ("SELECT", r"\b(select|choose|pick|go\s+with)\s*(\d+|number\s*\d+|the\s+\d+(st|nd|rd|th))\b"),

    # --- MATCH (broad search, catches remaining area/name queries) ---
    ("MATCH", r"\b(who|anyone|anybody|someone|somebody)\s+(works?|does|speciali[sz]es?|researches?|focuses?|deals?)\s+(on|in|with)\b"),
    ("MATCH", r"\b(find|search|looking\s+for|need|want|seeking)\b"),
    ("MATCH", r"\b(show|give)\s+me\b"),
    ("MATCH", r"\b(i('?m| am)\s+(looking|searching|interested)\s+(for|in))\b"),
    ("MATCH", r"\b(do you|does anyone|is there|are there).*\b(work|research|speciali[sz]e|focus)\b"),
    ("MATCH", r"\b(can you|could you)\s+(find|search|recommend|suggest)\b"),
    ("MATCH", r"\b(nlp|cv|iot|ml|ai|hci|vlsi|sdn|5g)\b"),

    # --- HELP / EXIT (last, generic) ---
    ("HELP", r"\b(help|commands?|what\s+can\s+you\s+do|how\s+do\s+(i|you)|options?|menu|guide)\b"),
    ("EXIT", r"\b(exit|quit|bye|goodbye|leave|stop|end)\b"),
]

PROFESSOR_PATTERNS = [
    # --- CHAT (casual conversation - check first) ---
    ("CHAT", r"^(hi|hey|hello|yo|sup|good\s*(morning|afternoon|evening))\b"),
    ("CHAT", r"\b(how\s*(are|r)\s*(you|u)|what('?s|s)\s*up|how('?s|s)\s*(it|things)\s*going)\b"),
    ("CHAT", r"\b(thanks?|thank\s*you|thx|ty|appreciate\s*(it|that)|cool|nice|great|awesome|wow)\b"),
    ("CHAT", r"\b(what|who)\s*(are|r)\s*(you|u)\??\s*$"),
    ("CHAT", r"\b(your\s*name|what\s*do\s*you\s*do|what\s*can\s*you\s*do)\b"),

    # --- LIST / TOPICS ---
    ("LIST", r"\b(list|show)\s+(all\s+)?(faculty|professors?|everyone|everybody)\b"),
    ("LIST", r"\b(all|every)\s+(faculty|professors?)\b"),
    ("TOPICS", r"\b(what|which|list|show)\s+(topics?|research\s*areas?|areas?|fields?|subjects?|domains?)\s*(are\s+)?(available|present|covered|offered|there)?\b"),
    ("TOPICS", r"\b(available|present|covered)\s+(topics?|research\s*areas?)\b"),
    ("TOPICS", r"\b(research\s*areas?|topics?)\s*(available|present|covered|list)?\b"),

    # --- MODE SWITCH ---
    ("MODE_SWITCH", r"\b(switch|change|go)\s+(to|into)\s+(professor|faculty|student)\s*(mode)?\b"),
    ("MODE_SWITCH", r"\b(i('?m| am)\s+(a\s+)?(professor|faculty|student))\b"),

    # --- EMAIL ---
    ("EMAIL", r"\b(want|trying|need|like)\s+to\s+(email|mail|contact|reach|write|send|draft|compose|message)\b"),
    ("EMAIL", r"\b(email|mail|contact|reach|write|draft|compose|message)\s+(dr\.?|prof(essor)?|faculty|him|her|them)\b"),
    ("EMAIL", r"\b(send|compose|draft)\s+(an?\s+)?(email|mail|message)\b"),

    # --- TREND (specific to research news) ---
    ("TREND", r"\b(what('?s| is)\s+(trending|new|hot|latest|recent|popular|emerging))\b"),
    ("TREND", r"\b(trend|latest|recent|new|emerging)\s+(papers?|research|publications?|work|developments?)\b"),
    ("TREND", r"\b(what|anything)\s+(is\s+)?(new|happening|going\s+on)\b.*\b(research|ai|field|area)\b"),
    ("TREND", r"\b(keep|stay)\s+(me\s+)?(updated|informed)\b"),

    # --- GAP ---
    ("GAP", r"\b(gaps?|missing|uncovered|lacking|absent|nonexistent|under[\-\s]?represented)\b"),
    ("GAP", r"\b(what|where)\s+(are|is)\s+(we|our|the)\s+(gaps?|missing|weaknesses)\b"),
    ("GAP", r"\b(not\s+(covered|present|available|doing|researching))\b"),

    # --- COLLAB ---
    ("COLLAB", r"\b(collaborate|collaboration|partner|work\s+(with|together)|co[\-\s]?author|joint)\b"),
    ("COLLAB", r"\b(who|whom)\s+(can|could|should)\s+(i|we)\s+(collaborate|partner|work)\s+with\b"),

    # --- STATS (comparative queries) ---
    ("STATS", r"\b(who|whom)\s+(has|have|got)\s+(the\s+)?(most|least|highest|lowest|best|top)\s+(score|citations?|papers?|publications?)\b"),
    ("STATS", r"\b(most|top|highest)\s+(cited|published|citations?|papers?|score)\b"),

    # --- WORKLOAD ---
    ("WORKLOAD", r"\b(who|whom|which)\s+(all\s+)?(is|are)\s+(busy|at\s+capacity|full|overloaded|maxed|least\s+busy|most\s+busy|most\s+loaded|least\s+loaded)\b"),
    ("WORKLOAD", r"\b(workload|capacity|availability|how\s+(busy|loaded|full|occupied|many\s+projects))\b"),
    ("WORKLOAD", r"\b(show|give|list|display)\s+(me\s+)?(all\s+)?(workloads?|capacity|who\s+is\s+busy)\b"),
    ("WORKLOAD", r"\b(who|whom)\s+(is|are|has|have)\s+(the\s+)?(least|most|fewest)\s+(busy|projects?|loaded|capacity|workload)\b"),
    ("WORKLOAD", r"\b(who|whom)\s+(is\s+)?(working\s+on|doing)\s+(the\s+)?(most|least|fewest)\s+projects?\b"),
    ("WORKLOAD", r"\b(can|available|free)\s+(to|for)\s+(take|accept|supervise)\b"),

    # --- SELECT ---
    ("SELECT", r"\b(select|choose|pick|go\s+with)\s*(\d+|number\s*\d+|the\s+\d+(st|nd|rd|th))\b"),

    # --- MAP (catch-all for search queries) ---
    ("MAP", r"\b(who|anyone|anybody)\s+(works?|does|speciali[sz]es?|researches?|focuses?)\s+(on|in|with)\b"),
    ("MAP", r"\b(map|landscape|overview|picture)\s+(of|on)?\b"),
    ("MAP", r"\b(find|search|looking\s+for|need|want|seeking)\b"),
    ("MAP", r"\b(show|give)\s+me\b"),
    ("MAP", r"\b(i('?m| am)\s+(looking|searching|interested)\s+(for|in))\b"),

    # --- HELP / EXIT ---
    ("HELP", r"\b(help|commands?|what\s+can\s+you\s+do|how\s+do\s+(i|you)|options?|menu|guide)\b"),
    ("EXIT", r"\b(exit|quit|bye|goodbye|leave|stop|end)\b"),
]


def classify_intent(query: str, mode: str) -> str:
    q = query.lower().strip()

    # Mode-specific intent matching
    patterns = STUDENT_PATTERNS if mode == "STUDENT" else PROFESSOR_PATTERNS

    # Also check for MODE_SWITCH across all patterns, but only switch if changing modes
    for intent, pat in STUDENT_PATTERNS + PROFESSOR_PATTERNS:
        if intent == "MODE_SWITCH" and re.search(pat, q):
            # Only activate switch if user is actually changing modes
            is_professor_switch = bool(re.search(r"(professor|faculty)", q))
            is_student_switch = bool(re.search(r"(student)", q))
            if mode == "STUDENT" and is_professor_switch and not is_student_switch:
                return "MODE_SWITCH"
            if mode == "PROFESSOR" and is_student_switch and not is_professor_switch:
                return "MODE_SWITCH"
            if re.search(r"(switch|change|go)\s+(to|into)", q):
                return "MODE_SWITCH"

    for intent, pat in patterns:
        if intent == "MODE_SWITCH":
            continue
        if re.search(pat, q):
            return intent

    # --- Fuzzy fallback: extract what the user is probably asking ---
    # "I want to..." / "I'd like to..." / "Can you..."
    has_name = bool(re.search(r"\b(dr\.?\s*\w+|prof(essor)?\s*\w+)\b", q))
    has_area = bool(re.search(
        r"\b(nlp|ml|ai|cv|iot|hci|cloud|security|cyber|network|data|signal|"
        r"embedded|vlsi|algorithm|theory|database|software|language\s*model|"
        r"machine\s*learning|deep\s*learning|computer\s*vision|reinforcement|"
        r"robotics|5g|mimo|sdn|chip|circuit|ux|accessibility)\b", q))

    if has_name:
        return "DETAIL" if mode == "STUDENT" else "COLLAB"
    if has_area:
        return "MATCH" if mode == "STUDENT" else "MAP"

    # Nothing specific detected -> casual chat, don't force search
    return "CHAT"


def llm_classify_intent(query: str, mode: str) -> str:
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_key:
        return classify_intent(query, mode)

    try:
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel

        class IntentOutput(BaseModel):
            intent: str

        all_intents = (
            "CHAT, LIST, TOPICS, MATCH, DETAIL, ALTERNATE, PROJECT, SELECT, EMAIL, HELP, EXIT, MODE_SWITCH"
            if mode == "STUDENT" else
            "CHAT, LIST, TOPICS, TREND, MAP, COLLAB, GAP, WORKLOAD, SELECT, EMAIL, HELP, EXIT, MODE_SWITCH"
        )

        llm = ChatOpenAI(api_key=openai_key, model="gpt-4.1-mini")
        structured = llm.with_structured_output(IntentOutput)
        result = structured.invoke(
            f"User: \"{query}\"\nMode: {mode}\nIntents: {all_intents}\n"
            f"Return ONLY the intent name, nothing else."
        )
        valid = [i.strip() for i in all_intents.split(",")]
        if result.intent in valid:
            return result.intent
    except Exception:
        pass
    return classify_intent(query, mode)


def format_help(mode: str) -> list[str]:
    lines = []
    if mode == "STUDENT":
        lines.extend([
            "I can help you with:",
            "  - Finding professors by research area (e.g. 'who works on NLP?')",
            "  - Listing all 15 faculty members ('list all professors')",
            "  - Showing available research topics ('what topics are there?')",
            "  - Getting a professor's full profile ('tell me about Dr. Sharma')",
            "  - Generating project ideas ('what project could I do?')",
            "  - Drafting emails to professors ('email Dr. Sharma')",
            "",
            "Natural language works too: 'I'm looking for someone in ML'",
            "'Can you find me a cybersecurity expert?'",
            "'What can I work on?'  'Show me another one'",
            "",
            "Type 'switch to professor' to change modes, 'exit' to quit.",
        ])
    else:
        lines.extend([
            "I can help you with:",
            "  - Research trends & papers ('what's trending in AI?')",
            "  - Finding collaborators ('who can I work with on NLP?')",
            "  - Analyzing research gaps ('what are we missing?')",
            "  - Checking workloads ('how busy is Dr. Iyer?')",
            "  - Listing all faculty ('list all professors')",
            "  - Showing research topics ('what topics are covered?')",
            "  - Drafting collaboration emails",
            "",
            "Natural language works too: 'Find me someone doing computer vision'",
            "'What's new in cybersecurity?'  'Who's not at full capacity?'",
            "",
            "Type 'switch to student' to change modes, 'exit' to quit.",
        ])
    return lines


if __name__ == "__main__":
    tests = [
        # Natural speech tests
        ("who works on NLP", "STUDENT"),
        ("i'm looking for someone in computer vision", "STUDENT"),
        ("can you find me a cybersecurity expert", "STUDENT"),
        ("tell me about Dr. Priya Sharma", "STUDENT"),
        ("what projects could I work on", "STUDENT"),
        ("show me the next one", "STUDENT"),
        ("i'm a professor", "STUDENT"),
        ("switch to professor mode", "STUDENT"),
        ("what's trending in AI lately", "PROFESSOR"),
        ("who can I collaborate with on NLP", "PROFESSOR"),
        ("what gaps do we have", "PROFESSOR"),
        ("how busy is Kavita Iyer", "PROFESSOR"),
        ("list all faculty", "PROFESSOR"),
        ("what topics are available", "STUDENT"),
        ("research areas", "STUDENT"),
        ("I want to email Dr. Sharma", "STUDENT"),
        ("do you know anyone doing IoT", "STUDENT"),
        ("help", "STUDENT"),
        ("bye", "PROFESSOR"),
    ]
    for q, m in tests:
        intent = classify_intent(q, m)
        print(f"  {q:50s} -> {intent}")
