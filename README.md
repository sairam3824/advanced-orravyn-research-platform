# Orravyn Research Platform

A full-stack Django collaborative research platform with AI-powered recommendations, a LangGraph RAG chatbot (Yggdrasil), multi-agent research orchestration, peer review, research blogs, citations, real-time chat, analytics, and more. Built as a conference research paper project.

---

## Table of Contents

1. [Features Overview](#features-overview)
2. [Tech Stack](#tech-stack)
3. [Architecture](#architecture)
4. [Django Apps](#django-apps)
5. [Models](#models)
6. [URL Routes & Views](#url-routes--views)
7. [ML & AI Pipeline](#ml--ai-pipeline)
8. [WebSocket & Real-time](#websocket--real-time)
9. [Celery Tasks](#celery-tasks)
10. [Management Commands](#management-commands)
11. [REST API](#rest-api)
12. [Frontend Design System](#frontend-design-system)
13. [Setup & Installation](#setup--installation)
14. [Configuration Reference](#configuration-reference)
15. [License](#license)

---

## Features Overview

### Paper Management
- Upload, edit, archive, and delete research papers (PDF)
- Multi-version paper support with change descriptions
- Approval workflow: pending → approved / rejected (moderator/admin)
- Per-paper category assignment and category request system
- Citation tracking between papers, export in BibTeX / RIS / EndNote
- Reading progress tracking (per user, per paper)
- Paper annotations (public or private, with page number and position data)
- Paper tagging (color-coded, user-created)
- Paper comparison side-by-side view
- Citation graph visualization

### Discovery & Search
- Full-text search across title, abstract, and authors
- Advanced search with filters (category, date range, sort order)
- Live search autocomplete and search suggestions
- Search history and saved searches
- Paper bookmarking with folder support
- AI-powered hybrid recommendation engine (content + collaborative + popularity)
- AI-generated paper summaries and section-level summaries

### Social & Collaboration
- Follow / unfollow users
- Paper likes, shares (Twitter, LinkedIn, Facebook, email tracking)
- Nested paper comments (threaded replies)
- User profiles with institution, ORCID, h-index, Google Scholar, ResearchGate
- Credential verification workflow with document upload

### Research Groups
- Create public or private research groups
- Group roles: admin, moderator, member
- Group paper libraries, collections, and member management
- Group-specific chat rooms (WebSocket)

### Peer Review
- Structured peer review with scoring across originality, methodology, clarity, and significance
- Submit, complete, and list reviews per paper
- Anonymous review support

### Research Blog
- Create blog posts linked to papers and citations
- Approval workflow for blog posts (pending → approved / rejected)
- Nested blog comments
- My posts and pending moderation views

### Reading Tools
- Reading lists (public or private, shareable with specific users)
- Research projects with task tracking (to-do, in-progress, completed)
- Paper annotations with text highlight and position metadata

### Yggdrasil RAG Chatbot
- LangGraph-based RAG pipeline with hybrid retrieval, reranking, and faithfulness scoring
- Multi-turn conversation history persisted to database
- Self-RAG retrieval gating, query decomposition, citation verification
- Per-request rate limiting (10 requests/minute per user)
- Conversation management (list, browse, resume sessions)

### Multi-Agent Research Orchestration
- PlannerAgent, WebSearchAgent (SerpAPI), ArXivAgent, PlatformAgent, CitationAgent, CriticAgent, SynthesizerAgent, MemoryAgent
- Agents run in parallel and results are fused and ranked

### Analytics & Metrics
- Personal reading dashboard: papers read, total time, completion rate, reading streak
- Paper impact dashboard: views, downloads, citations, bookmarks, shares, likes, average rating, impact score
- Trending topics by week
- Research field analytics: paper count, researcher count, citation count, growth rate
- Collaboration network graph

### Direct Messaging & Notifications
- Private one-to-one conversations
- Notification system: follows, paper activity, comments, ratings, messages, mentions, project and task updates
- Unread count badge (JSON API)

### Real-time Chat
- WebSocket chat rooms per paper and per group
- Bot response integration in paper chat rooms

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | Django 4.2, Django REST Framework 3.15 |
| Frontend | Bootstrap 5.3, SweetAlert2 |
| Real-time | Django Channels 4.0 (ASGI / WebSocket) |
| Channel layer | Redis (prod) / InMemory (dev) |
| Task queue | Celery 5.3 + Redis broker |
| Vector store | ChromaDB 0.5 |
| LLM orchestration | LangChain 0.3, LangGraph 0.2, OpenAI GPT-4o-mini |
| Embeddings | SentenceTransformers 2.5 (`all-MiniLM-L6-v2`) |
| Deep learning | PyTorch 2.2, Transformers 4.38 |
| Classical ML | scikit-learn 1.4 |
| Sparse retrieval | rank-bm25 |
| Cross-encoder reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| SciBERT classification | `allenai/scibert_scivocab_uncased` |
| Fine-tuning | PEFT / LoRA |
| Search | Elasticsearch-DSL 8.0 |
| Authentication | simplejwt (JWT) + Django session auth |
| PDF processing | PyPDF2, pypdf |
| Evaluation | rouge-score, bert-score, nltk |
| Database (dev) | SQLite |
| Database (prod) | MySQL (mysqlclient 2.2) |
| External APIs | SerpAPI (web search), arXiv API, Semantic Scholar API |
| Visualization | matplotlib 3.8, seaborn 0.13, networkx 3.2 |

---

## Architecture

```
Browser / API Client
        │
        ▼
  Django ASGI App (Daphne / Uvicorn)
  ├── HTTP: Django views + DRF
  └── WebSocket: Django Channels consumers
        │
  ┌─────┴──────────────────────────────────────┐
  │ Django Apps (9)                            │
  │ accounts · papers · groups · chat          │
  │ search · ml_engine · api · messaging       │
  │ analytics                                  │
  └────────────────────────────────────────────┘
        │
  ┌─────┴──────────────────────────────────────┐
  │ ML Engine                                  │
  │ RAG Pipeline (LangGraph) ← ChromaDB        │
  │ Hybrid Retrieval (BM25 + Dense + RRF)      │
  │ Reranker (cross-encoder)                   │
  │ Multi-Agent Orchestrator                   │
  │ Recommendation Engine (attention fusion)   │
  └────────────────────────────────────────────┘
        │
  ┌─────┴─────────────────┐
  │ Infrastructure         │
  │ Redis (cache/channels) │
  │ Celery workers         │
  │ SQLite / MySQL         │
  │ ChromaDB (vectors)     │
  └────────────────────────┘
```

---

## Django Apps

| App | Responsibility |
|---|---|
| `accounts` | Custom User model, profiles, follow/unfollow, interests, auth |
| `papers` | Papers, reviews, blogs, annotations, reading lists, projects, tags, comparisons |
| `groups` | Research groups, memberships, collections |
| `chat` | WebSocket rooms, Yggdrasil chatbot, conversation history |
| `search` | Full-text search, advanced search, suggestions, saved searches |
| `ml_engine` | RAG pipeline, embeddings, recommendations, multi-agent orchestration |
| `api` | Public REST API (JWT-authenticated) |
| `messaging` | Direct conversations, notifications |
| `analytics` | Dashboards, impact metrics, trending, field analytics, collaboration networks |

---

## Models

### accounts

| Model | Key Fields |
|---|---|
| `User` | Extends AbstractUser — `user_type`, `email`, `is_verified` |
| `UserProfile` | `institution`, `research_interests`, `bio`, `avatar`, `orcid`, `h_index`, `is_credentials_verified`, `credentials_document`, `website`, `google_scholar`, `research_gate` |
| `UserFollow` | `follower`, `following` |
| `ResearchInterestTag` | `name` |
| `UserResearchInterest` | `user`, `tag` (M2M) |
| `SavedSearch` | `user`, `name`, `query`, `filters` |

### papers

| Model | Key Fields |
|---|---|
| `Category` | `name`, `description` |
| `Paper` | `title`, `abstract`, `authors`, `doi`, `pdf_path`, `uploaded_by`, `categories` (M2M), `is_approved`, `download_count`, `view_count`, `summary`, `section_summaries` (JSON), `references_list` (JSON), `is_archived`, `archived_at` |
| `Bookmark` | `user`, `paper`, `folder` |
| `Citation` | `citing_paper`, `cited_paper` |
| `Rating` | `user`, `paper`, `rating` (1–5), `review_text` |
| `ReadingProgress` | `user`, `paper`, `progress_percentage`, `last_page`, `completed`, `reading_time_minutes` |
| `PaperVersion` | `paper`, `version_number`, `pdf_path`, `changes_description` |
| `PaperAnnotation` | `paper`, `user`, `page_number`, `annotation_text`, `highlight_text`, `position_data` (JSON), `is_public` |
| `ReadingList` | `name`, `owner`, `papers` (M2M through `ReadingListPaper`), `is_public`, `shared_with` (M2M) |
| `ReadingListPaper` | `reading_list`, `paper`, `notes` |
| `PaperCollection` | `name`, `group`, `papers` (M2M), `created_by` |
| `ResearchProject` | `name`, `group`, `papers` (M2M), `status`, `start_date`, `end_date`, `members` (M2M) |
| `ProjectTask` | `project`, `title`, `assigned_to`, `status`, `due_date` |
| `PaperView` | `user`, `paper` (unique together), `viewed_at` |
| `PaperLike` | `user`, `paper` |
| `PaperShare` | `user`, `paper`, `platform` |
| `PaperComment` | `paper`, `user`, `parent` (self-FK, threaded), `content` |
| `PeerReview` | `paper`, `reviewer`, `status`, `recommendation`, `originality_score`, `methodology_score`, `clarity_score`, `significance_score`, `strengths`, `weaknesses`, `detailed_comments`, `is_anonymous` |
| `ResearchBlogPost` | `title`, `slug`, `author`, `content`, `related_papers` (M2M), `tags`, `status`, `is_approved`, `view_count` |
| `BlogComment` | `blog_post`, `user`, `parent` (self-FK, threaded) |
| `PaperTag` | `name`, `color`, `created_by` |
| `PaperTagging` | `paper`, `tag`, `tagged_by` |
| `PaperComparison` | `user`, `name`, `papers` (M2M), `notes` |
| `CategoryRequest` | `name`, `description`, `reason`, `requested_by`, `status`, `reviewed_by` |
| `RelatedPaper` | `paper`, `related_to`, `similarity_score`, `relation_type` |

### groups

| Model | Key Fields |
|---|---|
| `Group` | `name`, `description`, `created_by`, `is_private` |
| `GroupMember` | `group`, `user`, `role` (admin/moderator/member) |
| `GroupPaper` | `group`, `paper`, `added_by` |

### chat

| Model | Key Fields |
|---|---|
| `ChatRoom` | `paper`, `group`, `created_by`, `is_active` |
| `ChatMessage` | `room`, `user`, `message`, `timestamp`, `is_bot_message` |
| `YggdrasilConversation` | `user`, `title` |
| `YggdrasilMessage` | `conversation`, `role` (user/bot), `content`, `sources` (JSON), `faithfulness_score` |
| `ResearchSession` | `user`, `session_id`, `turns` (JSON) |
| `AgentDecisionLog` | `query_id`, `agent_name`, `decision_type`, `reasoning`, `confidence`, `latency_ms` |

### messaging

| Model | Key Fields |
|---|---|
| `Conversation` | `participants` (M2M) |
| `Message` | `conversation`, `sender`, `content`, `is_read` |
| `Notification` | `user`, `notification_type`, `title`, `message`, `link`, `is_read` |

Notification types: `follow`, `paper`, `comment`, `rating`, `message`, `mention`, `project`, `task`, `annotation`

### analytics

| Model | Key Fields |
|---|---|
| `PaperImpactMetrics` | `paper` (OneToOne), `total_views`, `total_downloads`, `total_citations`, `total_bookmarks`, `total_shares`, `total_likes`, `average_rating`, `impact_score` |
| `UserReadingStatistics` | `user` (OneToOne), `total_papers_read`, `total_reading_time_minutes`, `papers_completed`, `reading_streak_days` |
| `TrendingTopic` | `name`, `category`, `paper_count`, `trend_score`, `week_start` |
| `ResearchFieldAnalytics` | `field_name`, `total_papers`, `total_researchers`, `growth_rate`, `top_keywords`, `month` |
| `CollaborationNetwork` | `user`, `collaborator`, `collaboration_count`, `strength_score` |

### ml_engine

| Model | Key Fields |
|---|---|
| `UserRecommendation` | `user`, `paper`, `score`, `reason` |
| `RecommendationModel` | `name`, `version`, `model_path`, `is_active` |
| `PaperEmbedding` | `paper` (OneToOne), `embedding` (JSON vector), `model_version` |

---

## URL Routes & Views

### `/` — Core

| URL | View | Description |
|---|---|---|
| `/` | `home_view` | Homepage |
| `/about/`, `/team/`, `/faq/` | Static views | Informational pages |
| `/privacy/`, `/terms/`, `/liability/`, `/disclaimer/` | Static views | Legal pages |
| `/contact/`, `/open-source/`, `/info/` | Static views | Support pages |

### `/accounts/`

| URL | View | Description |
|---|---|---|
| `login/` | `LoginView` | Login page |
| `register/` | `RegisterView` | Registration |
| `logout/` | `LogoutView` | Logout |
| `profile/` | `ProfileView` | Current user profile |
| `profile/edit/` | `ProfileEditView` | Edit profile |
| `dashboard/` | `DashboardView` | Personal dashboard |
| `admin-dashboard/` | `AdminDashboardView` | Admin only |
| `publishers/` | `PublishersListView` | Browse all publishers |
| `publishers/search/` | `publishers_search` | Live publisher search (JSON) |
| `publishers/<pk>/` | `PublisherDetailView` | Publisher profile |
| `user/<pk>/` | `UserPublicProfileView` | Public user profile |
| `follow/<user_id>/` | `follow_user` | Toggle follow (JSON) |
| `check-username/` | `check_username` | AJAX username validation |
| `interests/` | `update_research_interests` | Update interest tags |

### `/papers/`

| URL | View | Description |
|---|---|---|
| `/` | `PaperListView` | Browse papers (search, filter, sort) |
| `upload/` | `PaperUploadView` | Upload paper |
| `<pk>/` | `PaperDetailView` | Paper detail (tracks view) |
| `<pk>/edit/` | `PaperEditView` | Edit paper |
| `<pk>/delete/` | `PaperDeleteView` | Delete paper |
| `<pk>/bookmark/` | `bookmark_paper` | Toggle bookmark |
| `<pk>/rate/` | `rate_paper` | Rate paper |
| `<pk>/view-pdf/` | `view_paper_pdf` | Inline PDF viewer |
| `<pk>/download/` | `download_paper` | Download + track count |
| `<pk>/summary/` | `PaperSummaryView` | AI section summaries |
| `<pk>/export/<format>/` | `export_citation` | Export BibTeX / RIS / EndNote |
| `<pk>/progress/` | `update_reading_progress` | Update reading progress (JSON) |
| `<pk>/approve/` | `approve_paper` | Moderator approval |
| `<pk>/reject/` | `reject_paper` | Moderator rejection |
| `<pk>/archive/` | `archive_paper` | Archive paper |
| `<pk>/like/` | `like_paper` | Toggle like (JSON) |
| `<pk>/share/` | `share_paper` | Track share (JSON) |
| `<pk>/comment/` | `add_comment` | Add comment (JSON) |
| `<pk>/comments/` | `get_comments` | Get comments (JSON) |
| `<pk>/annotate/` | `add_annotation` | Add annotation (JSON) |
| `<pk>/annotations/` | `get_annotations` | Get annotations (JSON) |
| `<pk>/related/` | `get_related_papers` | Related papers (JSON) |
| `<pk>/citations/graph/` | `CitationGraphView` | Citation graph |
| `<pk>/versions/` | `PaperVersionListView` | Version history |
| `<pk>/upload-version/` | `upload_paper_version` | Upload new version |
| `<paper_id>/review/` | `PeerReviewCreateView` | Submit peer review |
| `<paper_id>/reviews/` | `PeerReviewListView` | List peer reviews |
| `review/<review_id>/submit/` | `submit_peer_review` | Finalize review |
| `bookmarks/` | `BookmarkListView` | My bookmarks |
| `my-papers/` | `MyPapersView` | My uploaded papers |
| `archived/` | `ArchivedPapersView` | Archived papers |
| `pending-approval/` | `PendingApprovalView` | Moderator queue |
| `admin-manage/` | `AdminPaperListView` | Admin paper list |
| `categories/` | `CategoryListView` | Browse categories |
| `categories/search/` | `category_search` | Category search (JSON) |
| `categories/<pk>/` | `CategoryDetailView` | Category detail |
| `categories/request/` | `CategoryRequestCreateView` | Request new category |
| `categories/requests/` | `CategoryRequestListView` | Moderator: view requests |
| `categories/requests/<pk>/approve/` | `approve_category_request` | Approve request |
| `categories/requests/<pk>/reject/` | `reject_category_request` | Reject request |
| `recommendations/` | `get_recommendations` | AI recommendations |
| `recommendations/refresh/` | `refresh_recommendations` | Trigger recommendation rebuild |
| `reading-lists/` | `ReadingListListView` | My reading lists |
| `reading-lists/api/` | `get_user_reading_lists` | Reading lists (JSON) |
| `reading-lists/create/` | `create_reading_list` | Create reading list (JSON) |
| `reading-lists/<pk>/` | `ReadingListDetailView` | Reading list detail |
| `reading-lists/<list_id>/add/<paper_id>/` | `add_to_reading_list` | Add paper to list |
| `projects/` | `ResearchProjectListView` | Research projects |
| `projects/<pk>/` | `ResearchProjectDetailView` | Project detail |
| `projects/<pk>/tasks/create/` | `create_project_task` | Create task (JSON) |
| `projects/<pk>/tasks/<task_id>/status/` | `update_project_task_status` | Update task status (JSON) |
| `tags/` | `TagListView` | Browse tags |
| `tags/create/` | `create_tag` | Create tag (JSON) |
| `<paper_id>/tag/<tag_id>/` | `tag_paper` | Toggle tag on paper (JSON) |
| `comparisons/` | `PaperComparisonListView` | My comparisons |
| `comparisons/create/` | `create_comparison` | Create comparison |
| `comparisons/<pk>/` | `PaperComparisonDetailView` | Comparison detail |
| `comparisons/<pk>/delete/` | `delete_comparison` | Delete comparison |
| `blog/` | `BlogPostListView` | Blog posts |
| `blog/new/` | `BlogPostCreateView` | Write blog post |
| `blog/my-posts/` | `MyBlogPostsView` | My posts |
| `blog/pending/` | `PendingBlogPostsView` | Moderator: pending posts |
| `blog/<pk>/approve/` | `approve_blog_post` | Approve post |
| `blog/<pk>/reject/` | `reject_blog_post` | Reject post |
| `blog/<slug>/` | `BlogPostDetailView` | Blog post detail |
| `blog/<slug>/comment/` | `add_blog_comment` | Add blog comment (JSON) |

### `/groups/`

| URL | View | Description |
|---|---|---|
| `/` | `GroupListView` | Browse groups |
| `search/` | `group_search` | Group search (JSON) |
| `create/` | `GroupCreateView` | Create group |
| `my-groups/` | `MyGroupsView` | My groups |
| `<pk>/` | `GroupDetailView` | Group detail |
| `<pk>/edit/` | `GroupEditView` | Edit group |
| `<pk>/join/` | `join_group` | Join group |
| `<pk>/leave/` | `leave_group` | Leave group |
| `<pk>/delete/` | `delete_group` | Delete group |
| `<pk>/members/` | `GroupMembersView` | Members list |
| `<pk>/invite/` | `invite_member` | Invite member |
| `<pk>/remove/<user_id>/` | `remove_member` | Remove member |
| `<pk>/update-role/<user_id>/` | `update_member_role` | Update member role |
| `<pk>/add-paper/` | `add_paper_to_group` | Add paper to group |
| `<pk>/collections/` | `group_collections` | Group collections |
| `<pk>/collections/create/` | `create_collection` | Create collection |
| `<pk>/collections/<collection_pk>/add/` | `add_to_collection` | Add paper to collection |

### `/chat/`

| URL | View | Description |
|---|---|---|
| `paper/<paper_id>/` | `ChatRoomView` | Paper chat room (WebSocket) |
| `room/<room_id>/` | `ChatDetailView` | Chat room detail |
| `ajax/send/<room_id>/` | `send_message_ajax` | Send message (JSON) |
| `my-chats/` | `MyChatRoomsView` | My chat rooms |
| `group/<group_id>/` | `GroupChatRoomView` | Group chat room |
| `yggdrasil_chatbot/` | `yggdrasil_chatbot_view` | RAG chatbot UI |
| `yggdrasil/api/` | `yggdrasil_rag_api` | RAG query endpoint (JSON, rate-limited) |
| `yggdrasil/conversations/` | `yggdrasil_conversations_api` | List conversations (JSON) |
| `yggdrasil/conversations/<id>/messages/` | `yggdrasil_conversation_messages_api` | Conversation messages (JSON) |

### `/search/`

| URL | View | Description |
|---|---|---|
| `/` | `SearchView` | Full-text search |
| `advanced/` | `AdvancedSearchView` | Advanced search with filters |
| `suggestions/` | `search_suggestions` | Autocomplete (JSON) |
| `live/` | `live_search` | Live search (JSON) |
| `history/` | `SearchHistoryView` | Search history |
| `saved/` | `SavedSearchListView` | Saved searches |
| `save/` | `save_search` | Save a search |
| `saved/<pk>/delete/` | `delete_saved_search` | Delete saved search |

### `/messaging/`

| URL | View | Description |
|---|---|---|
| `conversations/` | `ConversationListView` | All conversations |
| `conversations/<pk>/` | `ConversationDetailView` | Conversation detail |
| `start/<user_id>/` | `start_conversation` | Start conversation |
| `send/<conversation_id>/` | `send_message` | Send message |
| `notifications/` | `NotificationListView` | Notification list |
| `notifications/<id>/read/` | `mark_notification_read` | Mark as read |
| `notifications/read-all/` | `mark_all_notifications_read` | Mark all read |
| `api/unread-count/` | `get_unread_count` | Unread count (JSON) |

### `/analytics/`

| URL | View | Description |
|---|---|---|
| `dashboard/` | `PersonalDashboardView` | Personal reading stats |
| `paper/<pk>/impact/` | `PaperImpactView` | Paper impact metrics |
| `trending/` | `TrendingTopicsView` | Trending topics |
| `trending/update/` | `update_trending_topics` | Refresh trending (POST) |
| `fields/` | `ResearchFieldAnalyticsView` | Field analytics |
| `network/` | `CollaborationNetworkView` | Collaboration network graph |
| `api/reading-stats/` | `reading_statistics_api` | Reading stats (JSON) |

### `/recommendations/`

| URL | View | Description |
|---|---|---|
| `generate/` | `generate_recommendations_for_user` | Trigger recommendation generation |
| `my/` | `user_recommendations` | My recommendations |

### `/api/` (Public REST API)

| URL | Method | Description |
|---|---|---|
| `auth/register/` | POST | Register (returns JWT) |
| `auth/login/` | POST | Login (returns JWT) |
| `auth/profile/` | GET | Authenticated user profile |
| `auth/token/` | POST | Obtain JWT token pair |
| `auth/token/refresh/` | POST | Refresh JWT access token |
| `papers/` | GET, POST | List / create papers |
| `papers/<pk>/` | GET | Paper detail |
| `papers/<pk>/approve/` | POST | Approve paper |
| `bookmarks/` | GET, POST | List / create bookmarks |
| `ratings/` | GET, POST | List / create ratings |
| `search/` | GET | Paper search |
| `search/suggestions/` | GET | Search suggestions |
| `recommendations/` | GET | User recommendations |

---

## ML & AI Pipeline

### Yggdrasil RAG Pipeline (`ml_engine/rag_pipeline.py`)

Built with LangGraph. Each query flows through these nodes:

```
decide_retrieval
    → decompose_query         (HA-RAG: heuristic complexity check → sub-question generation)
    → hybrid_retrieve         (SR-MAR routing + dense ChromaDB + BM25 + RRF fusion)
    → rerank                  (cross-encoder/ms-marco-MiniLM-L-6-v2)
    → score_chunks            (relevance threshold filtering)
    → generate                (GPT-4o-mini response generation)
    → verify_citations        (faithfulness score 0–1, stored in YggdrasilMessage)
```

**State** (`RAGState`): `query`, `response`, `sources`, `sub_queries`, `documents`, `reranked_docs`, `relevance_scores`, `faithfulness_score`

### Hybrid Retrieval (`ml_engine/hybrid_retrieval.py`)

- BM25 index built from ChromaDB chunks (`rank_bm25`)
- Dense retrieval via ChromaDB cosine similarity
- Reciprocal Rank Fusion (RRF) merges both ranked lists
- `rebuild_index()` for re-indexing after new papers

### Vector Store (`ml_engine/vector_store.py`)

- Persistent ChromaDB collection
- Papers chunked at ~400 words with sliding window
- Methodology and Results sections are duplicated (boosted) for higher recall
- Section classification applied before indexing

### Query Decomposer (`ml_engine/query_decomposer.py`)

- `is_complex(query)` — heuristic detection of multi-faceted queries
- `decompose(query)` — generates atomic sub-questions via GPT-4o-mini

### Self-RAG Modules (`ml_engine/self_reflective.py`)

- `RetrievalDecisionModule` — decides whether retrieval is necessary
- `RelevanceScorer` — scores each chunk against the query
- `CitationVerifier` — measures faithfulness of the generated response

### Reranker (`ml_engine/reranker.py`)

- `CrossEncoderReranker` using `cross-encoder/ms-marco-MiniLM-L-6-v2`

### Recommendation Engine (`ml_engine/recommendation_engine.py`)

- `SignalFusionAttention` — learned attention over three signal types
- Hybrid scoring:
  - Content similarity α=0.6 (SentenceTransformers embeddings)
  - Collaborative filtering β=0.3 (user-paper interaction matrix)
  - Popularity γ=0.1 (view/download/citation counts)
- `build_embeddings()` — embeds all approved papers
- `save_recommendations()` — persists top-N to `UserRecommendation`

### Multi-Agent Research Orchestrator (`ml_engine/research_agents.py`)

| Agent | Responsibility |
|---|---|
| `MemoryAgent` | Persist multi-turn sessions to `ResearchSession` |
| `PlannerAgent` | Chain-of-thought query decomposition |
| `WebSearchAgent` | SerpAPI web search (8 results) |
| `ArXivAgent` | arXiv API queries (8 results) |
| `PlatformAgent` | Internal SR-MAR section-weighted retrieval |
| `CitationAgent` | Semantic Scholar citation expansion (5 papers) |
| `CriticAgent` | Chunk relevance scoring (0.50 threshold) |
| `SynthesizerAgent` | Final response generation |
| `ResearchOrchestrator` | Runs agents in parallel, fuses results |

### Section-Level Analysis

| Module | Responsibility |
|---|---|
| `section_classifier.py` | Regex-based IMRaD section detection |
| `section_summarizer.py` | Weighted section summaries (Methodology=0.35, Experiments=0.30, Results=0.20, Introduction=0.15) |
| `section_weight_learner.py` | Learn per-query section importance |
| `multi_agent_retrieval.py` | Section-specific retrieval agents (MethodologyAgent, ResultsAgent, LiteratureAgent, …) + SectionRouter |

### Additional ML Modules

| Module | Responsibility |
|---|---|
| `scibert_classifier.py` | SciBERT paper field/topic classification |
| `citation_extractor.py` | Parse references from PDF text |
| `pdf_text_extractor.py` | PyPDF2 thin wrapper for text extraction |
| `explainability.py` | Reasoning traces for agent decisions |
| `temporal_tracker.py` | Publication trend tracking over time |
| `efficiency_tracker.py` | Latency, cache hit rate, throughput monitoring |
| `agent_debate.py` | Multi-agent adversarial debate / consensus |
| `adversarial_testing.py` | Robustness testing with adversarial inputs |

---

## WebSocket & Real-time

**Consumer**: `apps/chat/consumers.py` — `ChatConsumer` (AsyncWebsocketConsumer)

| Method | Description |
|---|---|
| `connect()` | Authenticate user, join channel group |
| `disconnect()` | Leave channel group |
| `receive()` | Handle incoming messages, save to DB, broadcast, optionally call bot |
| `chat_message()` | Broadcast message to group |
| `save_message()` | Async DB write |
| `generate_bot_response()` | Rule-based bot response |

**WebSocket URL**: `ws://<host>/ws/chat/<room_id>/`

**Channel layer**:
- Dev: `InMemoryChannelLayer`
- Prod: Redis channel layer (`channels-redis`) via `USE_REDIS_CHANNELS=True`

---

## Celery Tasks

**File**: `apps/ml_engine/tasks.py`

| Task | Description |
|---|---|
| `process_paper_upload(paper_id)` | Index paper into ChromaDB after approval |
| `generate_recommendations(user_id)` | Compute and persist recommendations for a user |
| `rebuild_all_embeddings()` | Bulk re-index all approved papers |

**Config** (`celery.py`):
- Broker: Redis (`REDIS_URL`)
- Result backend: Redis
- Task serializer: JSON
- Autodiscovery: enabled across all apps

---

## Management Commands

### ml_engine

| Command | Description |
|---|---|
| `build_embeddings` | Build paper embeddings and user recommendations. Use `--for-all-users` to run for all users |
| `run_ablation` | Run general ablation experiment |
| `evaluate_summarization` | Evaluate section summaries with ROUGE and BERTScore |
| `run_lora_ablation` | LoRA fine-tuning ablation study |
| `run_adversarial_eval` | Adversarial robustness evaluation of the RAG pipeline |

### papers

| Command | Description |
|---|---|
| `create_categories` | Create initial paper categories |
| `create_sample_data` | Populate sample papers and users |
| `setup_initial_data` | Full initial data setup |
| `create_pending_papers` | Create papers in pending-approval state |
| `backfill_citations` | Populate citation relationships |
| `remove_categories` | Clean up categories |
| `check_pending_papers` | Report on pending papers |

### accounts

| Command | Description |
|---|---|
| `create_test_users` | Create test users with varying roles |

---

## REST API

Base URL: `/api/`

Authentication: Bearer JWT token (`Authorization: Bearer <access_token>`)

```http
POST /api/auth/register/
POST /api/auth/login/
POST /api/auth/token/
POST /api/auth/token/refresh/
GET  /api/auth/profile/

GET  /api/papers/
POST /api/papers/
GET  /api/papers/<id>/
POST /api/papers/<id>/approve/

GET  /api/bookmarks/
POST /api/bookmarks/

GET  /api/ratings/
POST /api/ratings/

GET  /api/search/?q=<query>
GET  /api/search/suggestions/?q=<query>
GET  /api/recommendations/
```

JWT config:
- Access token lifetime: 60 minutes
- Refresh token lifetime: 7 days
- Rotate refresh tokens: enabled

---

## Frontend Design System

The UI follows the "Deep Observatory" design language.

| Token | Value |
|---|---|
| Background | `#06090f` + dot-grid `radial-gradient` (32px) |
| Card background | `--bg-card: #0d1829` |
| Border | `--border-subtle: rgba(30,58,100,0.45)` |
| Accent | `--accent: #4f9cf9` (electric blue) |
| CTA | `--cta-gradient: #f4a027` (amber) |
| Heading font | Cormorant Garamond |
| Body font | DM Sans |
| Label / mono font | JetBrains Mono |

All CSS variables are defined in `:root` in `research_platform/static/css/global.css`.  
Modals use SweetAlert2.

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- Redis
- (Production) MySQL, Elasticsearch, SerpAPI key, OpenAI API key

### Install

```bash
git clone https://github.com/your-org/advanced-orravyn-research-platform.git
cd advanced-orravyn-research-platform

conda create -n research_platform python=3.10
conda activate research_platform

pip install -r research_platform/requirements.txt
```

### Environment

Create `research_platform/research_platform/.env`:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI (used by query decomposer and synthesizer)
OPENAI_API_KEY=your-openai-api-key

# SerpAPI (web search agent)
SERPAPI_KEY=your-serpapi-key

# Production database (leave unset to use SQLite in dev)
DB_NAME=orravyn_db
DB_USER=orravyn_user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=3306

# Enable Redis channel layer for production WebSocket
USE_REDIS_CHANNELS=False
```

### Database

```bash
cd research_platform
python manage.py migrate
python manage.py createsuperuser
```

Load initial data (optional):

```bash
python manage.py create_categories
python manage.py create_sample_data
```

### Run

```bash
# Django development server
python manage.py runserver

# Celery worker (for async tasks)
celery -A research_platform worker -l info

# Build ML embeddings and user recommendations
python manage.py build_embeddings --for-all-users
```

Open [http://localhost:8000](http://localhost:8000).

---

## Configuration Reference

| Setting | Default | Description |
|---|---|---|
| `SECRET_KEY` | — | Django secret key |
| `DEBUG` | `False` | Debug mode |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `OPENAI_API_KEY` | — | OpenAI key for LLM calls |
| `SERPAPI_KEY` | — | SerpAPI key for web search agent |
| `USE_REDIS_CHANNELS` | `False` | Use Redis channel layer (production) |
| `AUTH_USER_MODEL` | `accounts.User` | Custom user model |
| `MEDIA_URL` | `/media/` | Media file URL prefix |
| `ML_MODELS_PATH` | `ml_models/` | Directory for saved ML models |
| `TRANSFORMERS_CACHE` | `transformers_cache/` | HuggingFace model cache |

Logging is written to `logs/django.log`.

CORS allowed origins: `http://localhost:3000`, `http://127.0.0.1:3000`.

---

## License

MIT — see [LICENSE](LICENSE).
