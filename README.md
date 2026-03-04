# Advanced Orravyn Research Platform

**Orravyn** is an AI-powered research assistant that helps students, academics, and professionals conduct literature reviews more efficiently and effectively. It uses advanced natural language processing to understand research queries, search across multiple databases, and synthesize relevant information into comprehensive summaries.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Redis
- OpenAI API Key (for advanced features)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd advanced-orravyn-research-platform
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file in the `research_platform` directory:
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   
   # Database
   DB_NAME=orravyn_db
   DB_USER=orravyn_user
   DB_PASSWORD=your-password
   DB_HOST=localhost
   DB_PORT=5432
   
   # Redis
   REDIS_URL=redis://localhost:6379/0
   
   # OpenAI
   OPENAI_API_KEY=your-openai-key
   ```

5. **Apply migrations**
   ```bash
   cd research_platform
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   Open [http://localhost:8000](http://localhost:8000) in your browser.

## ✨ New Features (C12-C15)

This version includes four advanced features:

### 1. 🤝 Cross-Agent Debate (C12)
**Description:** When agents disagree on search results, they engage in a debate to resolve conflicts and improve answer quality.
**How it works:**
- Multiple agents (e.g., Web, Arxiv) search in parallel
- Results are compared for conflicts
- Conflicting results are debated using LLM
- Final answer incorporates debate resolution

**Usage:**
```python
from apps.ml_engine.agent_debate import get_debate_orchestrator

debate_orch = get_debate_orchestrator()
result = debate_orch.debate("query", agent_outputs)
```

### 2. ⏳ Temporal Tracking (C13)
**Description:** Automatically tracks temporal evolution of research topics and ranks results by relevance.
**How it works:**
- Analyzes publication dates and time trends
- Scores chunks based on recency and evolution
- Provides temporal context in answers

**Usage:**
```python
from apps.ml_engine.temporal_tracker import get_temporal_analyzer

temporal_analyzer = get_temporal_analyzer()
scored = temporal_analyzer.apply_temporal_scoring("query", chunks)
```

### 3. 🔍 Explainability (C14)
**Description:** Tracks all agent decisions for transparency and debugging.
**How it works:**
- Logs every agent decision with reasoning
- Provides full audit trail for answers
- Enables counterfactual analysis

**Usage:**
```python
from apps.ml_engine.explainability import get_decision_tracker

decision_tracker = get_decision_tracker()
decision_tracker.start_tracking("query_id", "query")
# ... agent operations ...
decision_tracker.log_decision("query_id", "Agent", "decision", "reasoning", 0.9)
explanation = decision_tracker.end_tracking("query_id", "response", [])
```

### 4. 🛡️ Adversarial Testing (C15)
**Description:** Generates adversarial queries to test system robustness.
**How it works:**
- Creates paraphrased and tricky queries
- Tests system under stress conditions
- Identifies weaknesses in search and synthesis

**Usage:**
```python
from apps.ml_engine.adversarial_testing import get_adversarial_generator

adv_generator = get_adversarial_generator()
test_queries = adv_generator.generate_adversarial_queries("original query")
```

## 📂 Project Structure

```
advanced-orravyn-research-platform/
├── research_platform/              # Django project root
│   ├── apps/
│   │   ├── accounts/             # User authentication
│   │   ├── chat/                 # Chat interface and models
│   │   ├── ml_engine/            # Core ML components
│   │   │   ├── agents/           # Search agents
│   │   │   ├── research_agents/  # Main orchestrator
│   │   │   ├── agent_debate.py   # Debate module
│   │   │   ├── temporal_tracker.py # Temporal analysis
│   │   │   ├── explainability.py # Decision tracking
│   │   │   └── adversarial_testing.py # Adversarial testing
│   │   └── web_search/           # Web search integration
│   ├── templates/                # HTML templates
│   └── static/                   # Static files
├── .env                          # Environment variables
├── requirements.txt              # Dependencies
└── README.md                     # Project documentation
```

## 🛠️ Development

### Running Tests
```bash
# Run all tests
python manage.py test

# Run specific test module
python manage.py test apps.ml_engine.test_agents
```

### Database Management
```bash
# Create migration
python manage.py makemigrations

# Apply migration
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Management Commands
```bash
# Build embeddings for all users
python manage.py build_embeddings --for-all-users

# Clear chat history
python manage.py clear_chat_history
```

## 🔌 API Endpoints

### Chat
- `POST /api/chat/`: Send message and get response
- `GET /api/chat/history/`: Get chat history
- `GET /api/chat/history/<session_id>/`: Get specific session

### Research
- `POST /api/research/`: Start research session
- `GET /api/research/sessions/`: List sessions
- `GET /api/research/sessions/<id>/`: Get session details

### Agents
- `GET /api/agents/`: List available agents
- `GET /api/agents/<name>/`: Get agent details

## 📚 Documentation

- [Full Documentation](docs/index.md) - Comprehensive guide to all features
- [API Reference](docs/api.md) - Detailed API documentation
- [Development Guide](docs/development.md) - Setup and development workflow

## 🤝 Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Support

For issues or questions, please open an issue on the GitHub repository.
