# 🚀 ResearchFlow AI

> **Enterprise Multi-Agent AI Research Assistant**

ResearchFlow AI is an intelligent multi-agent research system that automates the complete research workflow using AI agents. It searches trusted web sources, extracts meaningful information, generates professional research reports, and evaluates the report quality using autonomous AI agents.

---

## ✨ Features

### 🔍 Search Agent
- Searches the web for relevant information.
- Finds trusted and reliable sources.
- Prioritizes official websites and authoritative content.
- Filters duplicate results.
- Returns structured search results.

### 📖 Reader Agent
- Scrapes webpages from selected sources.
- Cleans HTML and extracts useful information.
- Summarizes the content into a structured format.
- Removes irrelevant text and advertisements.

### ✍️ Writer Agent
- Generates a professional research report.
- Creates well-structured sections with headings.
- Produces introductions, key findings, conclusions, and references.
- Combines information from multiple trusted sources.

### 🧠 Critic Agent
- Reviews the generated report.
- Identifies strengths and weaknesses.
- Suggests improvements.
- Assigns an overall quality score.

---

# 🏗️ Multi-Agent Workflow

```text
                User Query
                     │
                     ▼
             🔍 Search Agent
                     │
         Trusted Search Results
                     │
                     ▼
              📖 Reader Agent
                     │
        Extracted & Cleaned Content
                     │
                     ▼
              ✍️ Writer Agent
                     │
       Professional Research Report
                     │
                     ▼
              🧠 Critic Agent
                     │
                     ▼
              Final Reviewed Report
```

---

# ⚙️ Tech Stack

- Python 3.x
- LangGraph
- LangChain
- Mistral AI
- BeautifulSoup4
- Requests
- Streamlit (UI)
- Python Dotenv

---

# 📂 Project Structure

```text
ResearchFlow-AI/
│
├── pipeline.py          # Main research workflow
├── agents.py            # AI agent implementations
├── tools.py             # Search and utility functions
├── app.py               # Streamlit UI
├── requirements.txt
├── README.md
├── .gitignore
└── .env
```

---

# 🚀 Installation

## 1. Clone the Repository

```bash
git clone https://github.com/akashgoswami139/ResearchFlow-AI.git
cd ResearchFlow-AI
```

---

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
MISTRAL_API_KEY=your_api_key
TAVILY_API_KEY=your_api_key
```

---

# ▶️ Run the Application

### Run the Research Pipeline

```bash
python pipeline.py
```

### Run the Streamlit UI

```bash
streamlit run app.py
```

---

# 📖 Example Usage

```
Enter a research topic:

Artificial Intelligence in Healthcare
```

The system will:

- 🔍 Search trusted sources
- 📖 Read and summarize webpages
- ✍️ Generate a research report
- 🧠 Critically evaluate the report
- 📄 Produce the final result

---

# 📊 Example Output

```
Research Topic:
Artificial Intelligence in Healthcare

✔ Search Completed
✔ Sources Collected
✔ Content Extracted
✔ Report Generated
✔ Report Reviewed

Overall Score:
9/10
```

---

# 📈 Current Features

- ✅ Multi-Agent Architecture
- ✅ Intelligent Web Search
- ✅ Trusted Source Discovery
- ✅ Web Content Extraction
- ✅ AI-Powered Report Generation
- ✅ Automated Report Evaluation
- ✅ Modular Design
- ✅ Environment Variable Support
- ✅ Streamlit User Interface

---

# 🚀 Future Roadmap

- PDF Report Export
- DOCX Report Export
- FastAPI Backend
- Citation Generator (APA, MLA, IEEE)
- Google Scholar Integration
- ArXiv Integration
- Vector Database Support
- Retrieval-Augmented Generation (RAG)
- Research History
- Multi-Language Research
- Parallel Agent Execution
- Source Reliability Scoring
- Interactive Dashboard
- Cloud Deployment

---

# 👨‍💻 Developer

## Akash Goswami

**AI & Machine Learning Developer**

I am passionate about Artificial Intelligence, Machine Learning, Large Language Models (LLMs), and Multi-Agent Systems. I enjoy building intelligent applications that solve real-world problems using modern AI technologies.

### 🌐 Connect with Me

- 🐙 GitHub: https://github.com/akashgoswami139
- 💼 LinkedIn: https://www.linkedin.com/in/akashgoswami-/
- 🐦 X (Twitter): https://x.com/akashgoswami
- 📧 Email: akashhgoswami26@gmail.com

---

# 🤝 Contributing

Contributions are welcome!

1. Fork this repository.
2. Create a new feature branch.
3. Commit your changes.
4. Push your branch.
5. Open a Pull Request.

---

# 📜 License

This project is licensed under the **MIT License**.

---

# ⭐ Support

If you found this project helpful, please consider giving it a ⭐ on GitHub. Your support helps improve the project and motivates future development.

---

<div align="center">

### 🚀 ResearchFlow AI

**Enterprise Multi-Agent AI Research Assistant**

*Built with ❤️ by Akash Goswami*
