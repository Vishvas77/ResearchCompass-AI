 █████╗  ██████╗ █████╗ ██████╗ ███████╗███╗   ███╗██╗
██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝████╗ ████║██║
███████║██║     ███████║██║  ██║█████╗  ██╔████╔██║██║
██╔══██║██║     ██╔══██║██║  ██║██╔══╝  ██║╚██╔╝██║██║
██║  ██║╚██████╗██║  ██║██████╔╝███████╗██║ ╚═╝ ██║██║
╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝     ╚═╝╚═╝

         AI-Powered Research Matching Assistant
         # 🎓 ResearchCompass AI

> An AI-powered research assistant that connects students with faculty, recommends research opportunities, and supports academic collaboration using Retrieval-Augmented Generation (RAG) and intelligent workflow orchestration.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![LangChain](https://img.shields.io/badge/LangChain-Framework-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent-orange)
![ChromaDB](https://img.shields.io/badge/ChromaDB-VectorDB-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

# 📖 Overview

ResearchCompass AI is an intelligent academic research assistant designed to simplify the process of discovering faculty members, exploring research domains, and identifying collaboration opportunities.

Using Retrieval-Augmented Generation (RAG), semantic vector search, and live academic search, the system delivers personalized recommendations based on user interests while automating research assistance tasks through a LangGraph workflow.

The application currently runs through a command-line interface and demonstrates how modern LLM-powered agents can support students and researchers in academic environments.

---

# ✨ Key Features

- 🔍 AI-powered faculty recommendation
- 📚 Hybrid RAG-based semantic search
- 🧠 Research paper retrieval
- 🤝 Collaboration opportunity analysis
- 💡 Project idea recommendation
- 📈 Research gap analysis
- 📧 AI-generated faculty outreach emails
- 👨‍🏫 Faculty workload analysis
- 🧭 LangGraph agent workflow
- 🗂️ ChromaDB vector database
- 🌐 Live web search using Tavily
- 💻 Interactive command-line interface

---

# 🛠️ Technology Stack

| Technology | Purpose |
|------------|---------|
| Python | Backend Development |
| LangChain | Retrieval-Augmented Generation |
| LangGraph | AI Workflow Orchestration |
| ChromaDB | Vector Database |
| OpenAI | LLM & Embeddings |
| Tavily | Live Web Search |
| Semantic Scholar | Academic Paper Retrieval |
| python-dotenv | Environment Variables |

---

# 🏗️ System Architecture

```
            User Query
                 │
                 ▼
          Intent Router
                 │
     ┌───────────┴───────────┐
     ▼                       ▼
 Student Mode          Faculty Mode
     │                       │
     ▼                       ▼
 Hybrid RAG            Paper Search
     │                       │
     └───────────┬───────────┘
                 ▼
      Recommendation Engine
                 │
                 ▼
        Email Generator
                 │
                 ▼
       Human Confirmation
                 │
                 ▼
          Final Response
```

---

# 📂 Project Structure

```
ResearchCompass-AI/
│
├── data/
├── eval/
├── src/
├── main.py
├── demo.py
├── requirements.txt
└── README.md
```

---

# 🚀 Installation

```bash
git clone https://github.com/yourusername/ResearchCompass-AI.git

cd ResearchCompass-AI

python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

---

# 🔑 Environment Variables

Create a `.env` file in the project root.

```env
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
```

---

# ▶️ Run

```bash
python main.py
```

or

```bash
python demo.py
```

---

# 🔄 Workflow

```
Load Faculty Database
        │
        ▼
Create Vector Database
        │
        ▼
Receive User Query
        │
        ▼
Intent Classification
        │
        ▼
Hybrid Retrieval
        │
        ▼
Recommendation Engine
        │
        ▼
Research Analysis
        │
        ▼
Email Generation
        │
        ▼
Human Approval
        │
        ▼
Final Response
```

---

# 💬 Example

```
User:
Find professors working in NLP.

↓

Recommended Faculty

↓

Research Papers

↓

Suggested Projects

↓

Generate Email

↓

Human Approval

↓

Response Completed
```

---

# 🔮 Future Enhancements

- Web dashboard
- Gmail API integration
- PDF research paper parsing
- Multi-university knowledge base
- Citation graph visualization
- User authentication
- Research proposal generation
- Real-time faculty profile updates

---

# 👥 Team

**Team Name:** AI For Good

- Rachamalla Sai Arnav Goud (Team Lead)
- Mohammed Faroz Khan
- Vishvas Polepaka
- Kunduru Bharath Reddy

---

# 📄 License

This project is released under the MIT License.