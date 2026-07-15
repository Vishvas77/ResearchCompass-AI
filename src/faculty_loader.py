import os
import sys
import json
import glob
import warnings
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_chroma import Chroma

load_dotenv()

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")

CHROMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "chroma_faculty_db",
)
FACULTY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "faculty",
)

_SILENT = os.environ.get("ACADEMIMATCH_SILENT", "").strip() != ""


def _log(msg: str):
    if not _SILENT:
        print(msg)


def _build_page_content(profile: dict) -> str:
    areas = "; ".join(profile.get("research_areas", []))
    keywords = "; ".join(profile.get("keywords", []))
    return (
        f"Name: {profile['name']}. "
        f"Department: {profile['department']}. "
        f"Research Areas: {areas}. "
        f"Keywords: {keywords}. "
        f"Bio: {profile.get('bio', '')}"
    )


def _get_embedding_model():
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(model="text-embedding-3-small", api_key=openai_key)
        except Exception:
            pass
    import importlib.util
    if importlib.util.find_spec("langchain_huggingface"):
        from langchain_huggingface import HuggingFaceEmbeddings
    else:
        from langchain_community.embeddings import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )


def load_faculty_profiles() -> list[dict]:
    profiles = []
    json_files = sorted(glob.glob(os.path.join(FACULTY_DIR, "*.json")))
    for filepath in json_files:
        with open(filepath, "r", encoding="utf-8") as f:
            profile = json.load(f)
            profiles.append(profile)
    return profiles


def build_chroma_store(profiles: list[dict]) -> Chroma:
    embedding_model = _get_embedding_model()
    documents = []
    for profile in profiles:
        doc = Document(
            page_content=_build_page_content(profile),
            metadata={
                "id": profile["id"], "name": profile["name"],
                "department": profile["department"],
                "research_areas": ", ".join(profile.get("research_areas", [])),
                "keywords": ", ".join(profile.get("keywords", [])),
                "papers": profile.get("papers", 0),
                "citations": profile.get("citations", 0),
                "current_projects": profile.get("current_projects", 0),
                "max_projects": profile.get("max_projects", 0),
                "email": profile.get("email", ""),
                "bio": profile.get("bio", ""),
            },
        )
        documents.append(doc)
    vectorstore = Chroma.from_documents(
        documents=documents, embedding=embedding_model,
        persist_directory=CHROMA_PATH, collection_name="faculty",
    )
    return vectorstore


def get_or_build_retriever():
    embedding_model = _get_embedding_model()
    if os.path.exists(CHROMA_PATH) and os.listdir(CHROMA_PATH):
        vectorstore = Chroma(
            persist_directory=CHROMA_PATH,
            embedding_function=embedding_model,
            collection_name="faculty",
        )
    else:
        profiles = load_faculty_profiles()
        vectorstore = build_chroma_store(profiles)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    return vectorstore, retriever


if __name__ == "__main__":
    vs, ret = get_or_build_retriever()
    queries = [
        "who works on NLP", "computer vision medical imaging",
        "cybersecurity network attacks", "IoT embedded systems",
        "cloud computing microservices", "reinforcement learning robotics",
    ]
    for q in queries:
        results = ret.invoke(q)
        print(f"\nQuery: \"{q}\"")
        for i, doc in enumerate(results[:3], 1):
            print(f"  {i}. {doc.metadata['name']} ({doc.metadata['department']})")
