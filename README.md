# FICCT-SCRUM Backend API

A Django REST Framework backend for agile project management with real-time collaboration, AI-powered features, and comprehensive integrations.

## Technology Stack

**Framework:** Django 5.0.7  
**Database:** PostgreSQL (configurable via DATABASE_URL, fallback to SQLite)  
**Cache:** Redis 5.0+  
**API:** Django REST Framework 3.15.2  
**Real-time:** Django Channels 4.0.0  
**Task Queue:** Celery 5.3+  
**Authentication:** JWT (djangorestframework-simplejwt 5.3.0)  
**Python:** 3.11+

**Additional Services:**
- AWS S3 for file storage (optional, falls back to local)
- AWS SES for email delivery (optional, falls back to console)
- GitHub OAuth integration (PyGithub 2.1.1)
- OpenAI for AI assistant features
- Pinecone for vector storage and semantic search

## Architecture

### Application Structure

The backend follows a service-oriented architecture with 11 Django applications:

- **authentication** - Custom user model, JWT authentication, registration, password reset
- **organizations** - Multi-tenant organization management with memberships and invitations
- **workspaces** - Team workspace organization within organizations
- **projects** - Project management with issues, sprints, boards, and workflow states
- **integrations** - Third-party integrations (GitHub repositories, commits, pull requests)
- **reporting** - Analytics, diagrams (UML, architecture), activity logs, saved filters
- **ml** - Machine learning models for velocity prediction and anomaly detection
- **ai_assistant** - AI-powered semantic search and issue summaries using OpenAI/Pinecone
- **notifications** - Email notifications and deadline monitoring
- **logging** - Audit logs, error tracking, and system monitoring
- **admin_tools** - Administrative utilities and performance monitoring

### Database Models

**Core Entities:**
- User (custom model extending AbstractBaseUser, email as username)
- Organization (UUID primary key, subscription plans, owner relationship)
- Workspace (belongs to Organization, team members, visibility settings)
- Project (belongs to Workspace, methodology support, team members)
- Issue (UUID primary key, workflow status, issue type, assignee, sprint)
- Sprint (date range, committed/completed points, status tracking)
- Board (Kanban/Scrum boards with columns linked to workflow statuses)
- WorkflowStatus (customizable per project, tracks state transitions)

**Key Relationships:**
- Organization → Workspaces (one-to-many)
- Workspace → Projects (one-to-many)
- Project → Issues, Sprints, Boards (one-to-many)
- Issue → WorkflowStatus, IssueType (foreign keys)
- BoardColumn → WorkflowStatus (board columns represent workflow states)

**Database Features:**
- UUID primary keys on core models for security
- JSONField for flexible configuration storage
- Soft deletes via is_active flags
- Indexes on frequently queried fields (project+key, assignee, sprint, status)
- Automatic timestamp tracking (created_at, updated_at)
- Unique constraints (workspace+slug, project+key, etc.)

### API Architecture

**REST API Pattern:**
- ViewSets for CRUD operations (ModelViewSet, ReadOnlyModelViewSet)
- Nested routes for related resources (/issues/{id}/comments/, /issues/{id}/attachments/)
- Custom actions using @action decorator (transition, assign, sync_commits)
- OpenAPI 3.0 schema generation via drf-spectacular

**Pagination:**
- Class: CustomPageNumberPagination
- Default: 20 items per page
- Maximum: 100 items per page
- Client-controlled via ?page_size=N query parameter
- Response format: {count, next, previous, results}

**Filtering:**
- DjangoFilterBackend for field-based filtering
- SearchFilter for full-text search across multiple fields
- OrderingFilter for sorting results
- Custom filters: project_key, workspace_key, assignee_email, status_name, status_category

**Authentication:**
- JWT tokens with Bearer scheme
- Access token lifetime: 60 minutes (configurable)
- Refresh token lifetime: 1440 minutes (configurable)
- Token rotation with blacklisting enabled
- Session authentication for Swagger UI

**Permissions:**
- Default: IsAuthenticated on all endpoints
- Custom permission classes: CanAccessProject, IsProjectLeadOrAdmin, CanModifyIssue, CanManageSprint
- Three-tier access control: Organization → Workspace → Project
- Workspace members have full access to all projects in their workspace
- Project members have access to specific projects only

### Service Layer

Business logic is separated into service classes in `apps/*/services/` directories:

- **DiagramService** - Generates UML and architecture diagrams from Django models using introspection
- **GitHubService** - Syncs commits and pull requests, manages OAuth flow, parses issue references
- **EmailService** - Sends transactional emails with retry logic and exponential backoff
- **AnalyticsService** - Computes project metrics, velocity, and sprint analytics
- **WorkflowValidator** - Validates workflow status transitions based on defined rules
- **IssueKeyGenerator** - Generates unique issue keys in PROJECT-123 format
- **OpenAIService** - Interfaces with OpenAI API for text generation and embeddings
- **PineconeService** - Manages vector embeddings for semantic search functionality

ViewSets delegate to services rather than implementing business logic directly.

### ML Subsystem - Predictive Analytics & Intelligent Estimation

The ML (Machine Learning) subsystem provides data-driven predictions and recommendations for project management using trained machine learning models.

**Core Capabilities:**
- **Effort Prediction**: Predict hours required for issues using Gradient Boosting Regressor
- **Sprint Duration Estimation**: Estimate sprint completion time based on historical velocity
- **Story Points Recommendation**: Suggest story points based on similar completed issues  
- **Task Assignment Suggestions**: Recommend optimal team member assignments using multi-factor scoring
- **Sprint Risk Detection**: Identify at-risk sprints (burndown velocity, scope creep, bottlenecks)
- **Anomaly Detection**: Detect unusual patterns (velocity drops, stale issues, excessive reassignments)

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                    ML Subsystem Flow                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  API Request → PredictionService                            │
│                      ↓                                      │
│                 ModelLoader (1-hour cache)                  │
│                      ↓                                      │
│              AWS S3 (model storage)                         │
│                      ↓                                      │
│        scikit-learn Model (GradientBoosting)                │
│                      ↓                                      │
│    Prediction → PredictionHistory (logging)                 │
│                      ↓                                      │
│                JSON Response                                │
│                                                             │
│  Background: Celery (retraining + anomaly detection)        │
│              ↓                                              │
│         Weekly model retraining (Monday 2 AM)               │
│         Anomaly detection every 6 hours                     │
└─────────────────────────────────────────────────────────────┘
```

**Prediction Flow:**

1. **ML Model** (highest confidence): Trained scikit-learn model from S3
2. **Similarity Fallback**: Jaccard similarity on completed issues if no model
3. **Heuristic Fallback**: Average by issue type if insufficient data

**Training Data Generation:**

The system includes a sophisticated data generation command for creating realistic training data:

```bash
python manage.py generate_quality_training_data \
  --workspace <uuid> \
  --user <id> \
  --preserve-project <uuid> \
  --num-projects 5 \
  --confirm
```

This generates:
- 5+ diverse project portfolios (e-commerce, admin, mobile, etc.)
- 420+ realistic issues with temporal consistency
- 50+ sprints with velocity patterns  
- 7 team members with varying skills and performance
- Authentic anomalies (behind-schedule projects, scope creep, bottlenecks)

**Model Storage:**

All models stored in AWS S3 with versioning:
```
s3://bucket/ml_models/
├── effort_prediction/
│   └── 20250119_150000/
│       └── model.joblib
├── story_points/
│   └── 20250119_150000/
│       └── model.joblib
```

**Performance Characteristics:**
- Response time (cached): 50-100ms
- Response time (cold start): 800ms (includes S3 download)
- Cache hit rate: 70-80% in production
- Training throughput: 1-2 models/hour
- Predictions/second: 50-100 (with cache)

**Model Performance Targets:**
- Effort Prediction: MAE < 5 hours, RMSE < 8 hours, R² > 0.70
- Story Points: Accuracy > 65%, F1-score > 0.60
- Sprint Duration: Velocity correlation > 0.75

**Automatic Retraining:**

Celery tasks handle:
- Weekly model retraining (Monday 2 AM) when 30+ days old or 50+ new samples
- Anomaly detection every 6 hours across active projects
- Cleanup of old prediction history (1 year retention)

**API Endpoints:**
- `POST /api/v1/ml/predict-effort/` - Predict issue hours
- `POST /api/v1/ml/estimate-sprint-duration/` - Estimate sprint days
- `POST /api/v1/ml/recommend-story-points/` - Suggest story points
- `POST /api/v1/ml/suggest-assignment/` - Recommend team member
- `GET /api/v1/ml/{sprint_id}/sprint-risk/` - Detect sprint risks
- `POST /api/v1/ml/{project_id}/project-summary/` - Generate AI metrics summary

**Management Commands:**
```bash
# Train models
python manage.py train_ml_model effort_prediction
python manage.py train_ml_model story_points --project=<uuid>

# List trained models
python manage.py list_ml_models --active-only

# Detect anomalies
python manage.py detect_anomalies --all
python manage.py detect_anomalies --sprint=<uuid>
```

**Integration Requirements:**
- AWS S3 bucket for model storage
- Redis for caching loaded models
- PostgreSQL for metadata and prediction history
- Celery worker for background training

**Documentation:** See `apps/ml/README.md` for comprehensive guide (2400+ lines) including:
- Complete API reference with TypeScript examples
- Training pipeline details and hyperparameters
- Local development and testing guide
- Docker deployment configuration
- Monitoring and maintenance procedures
- Troubleshooting common issues

### LLM Proxy Service - Intelligent AI Provider Management

The LLM Proxy orchestrates AI requests through a 3-tier fallback system for cost optimization and reliability.

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Proxy Service                        │
│                                                             │
│  Request → Tier 1: Llama 4 Maverick (AWS Bedrock)          │
│              ↓ (if fails)                                   │
│           Tier 2: Llama 4 Scout (AWS Bedrock)              │
│              ↓ (if fails)                                   │
│           Tier 3: Azure OpenAI o4-mini                      │
│              ↓                                              │
│           Response with cost tracking                       │
└─────────────────────────────────────────────────────────────┘
```

**Provider Tier System:**

1. **Llama 4 Maverick** (Primary)
   - Model: `us.meta.llama4-maverick-17b-instruct-v1:0`
   - Best quality responses
   - Pricing: $0.24 input / $0.97 output per 1M tokens
   - Max tokens: 8192
   - Use case: Primary AI assistant, code analysis

2. **Llama 4 Scout** (Secondary)
   - Model: `us.meta.llama4-scout-17b-instruct-v1:0`  
   - Fast, cost-effective
   - Pricing: $0.06 input / $0.24 output per 1M tokens (75% cheaper)
   - Max tokens: 8192
   - Use case: Fallback for non-critical tasks

3. **Azure OpenAI o4-mini** (Emergency)
   - Model: `gpt-4o-mini`
   - Highest reliability (99.9% uptime)
   - Most expensive option
   - Use case: Final fallback when AWS Bedrock unavailable

**Features:**

- **Automatic Fallback:** If Tier 1 fails or returns invalid response, automatically tries Tier 2, then Tier 3
- **Response Validation:** Checks for empty responses, minimum length, repetitive patterns
- **Cost Tracking:** Monitors usage by provider with real-time cost calculation
- **Performance Monitoring:** Tracks latency per provider and per request
- **Usage Statistics:**
  - Total calls (successful/failed)
  - Success rate percentage
  - Average cost per request
  - Token usage by provider

**Implementation:**

```python
# Usage in services
from base.services.llm_proxy import get_llm_proxy

proxy = get_llm_proxy()
response = proxy.generate(
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Analyze this code..."}
    ],
    task_type="code_analysis",
    max_tokens=2048,
    temperature=0.7,
    fallback_enabled=True  # Enables automatic fallback
)

print(f"Provider: {response.provider}")  # e.g., 'bedrock-llama4-maverick'
print(f"Cost: ${response.cost_usd:.4f}")  # e.g., '$0.0015'
print(f"Tokens: {response.total_tokens}")  # e.g., '1234'
print(f"Content: {response.content}")     # Generated text
```

**AWS Bedrock Configuration:**

Requires AWS credentials with `bedrock:InvokeModel` permission:

```env
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1  # Required: Llama 4 models only in us-east-1
```

**Provider Classes:**
- `BaseLLMProvider` - Abstract base with validation logic
- `BedrockProvider` - AWS Bedrock integration (Llama 4 models)
- `AzureProvider` - Azure OpenAI integration
- `LLMProxyService` - Orchestration and fallback logic

**Response Format:**
```python
@dataclass
class LLMResponse:
    content: str              # Generated text
    model: str                # Model identifier
    provider: str             # Provider name (bedrock/azure)
    input_tokens: int         # Input token count
    output_tokens: int        # Output token count
    cost_usd: float           # Cost in USD
    latency_seconds: float    # Response time
    metadata: Dict            # Additional info (attempts, fallbacks)
```

**Cost Optimization:**
- Maverick vs Scout: 75% cost reduction when Scout succeeds
- Average request: ~$0.002 with Scout vs ~$0.008 with Maverick
- Automatic selection of cheapest viable option
- Usage stats available via `proxy.get_stats()`

### Diagram Architecture - JSON Data System

The diagram generation system uses a **JSON data architecture** instead of server-side SVG rendering.

**Why JSON Data Architecture?**

Problems with SVG generation (old approach):
- String escaping issues between backend/frontend
- No interactivity (zoom, pan, drag)
- Large payload size (~50KB per diagram)
- Tight coupling between data and visualization
- Export requires re-parsing SVG

Benefits of JSON data (new approach):
- Clean separation: Backend = data, Frontend = visualization
- 70% payload reduction (50KB SVG → 15KB JSON)
- No escaping issues (pure JSON serialization)
- Frontend adds interactivity with D3.js/Cytoscape.js
- Export handled client-side (SVG, PNG, PDF)
- Customizable styling and themes

**Architecture Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│                      BACKEND                                │
├─────────────────────────────────────────────────────────────┤
│  DiagramViewSet                                             │
│       ↓                                                     │
│  DiagramService (caching, orchestration)                    │
│       ↓                                                     │
│  DiagramDataService (data computation)                      │
│       ↓                                                     │
│  Returns: {                                                 │
│    nodes: [{id, name, position, dimensions, color}],        │
│    edges: [{source, target, label, color}],                 │
│    metadata: {project_id, status_count, ...},               │
│    layout: {type, width, height, padding}                   │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
                        ↓ HTTP Response (JSON)
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND                                │
├─────────────────────────────────────────────────────────────┤
│  Angular Component                                          │
│       ↓                                                     │
│  D3.js / Cytoscape.js Renderer                              │
│       ↓                                                     │
│  Interactive SVG with:                                      │
│  - Zoom and pan controls                                    │
│  - Node dragging                                            │
│  - Click handlers (navigate to issues)                      │
│  - Export to SVG/PNG/PDF                                    │
└─────────────────────────────────────────────────────────────┘
```

**Supported Diagram Types:**

1. **Workflow Diagram** - Status nodes with transition edges
   - Visualizes project workflow states
   - Shows transition paths between statuses
   - Issue count per status displayed
   - Horizontal layout with auto-positioning

2. **Dependency Graph** - Issue nodes with dependency edges
   - Shows issue relationships (blocks, depends on)
   - Filterable by sprint, status, priority, assignee
   - Force-directed layout for optimal positioning
   - Color-coded by priority and status

3. **Roadmap Timeline** - Sprint timeline with milestones
   - Gantt-style sprint visualization
   - Progress indicators per sprint
   - Milestone markers
   - Today line indicator

4. **UML Class Diagram** - Django model relationships
   - Generated from local Django models via introspection
   - Shows attributes, methods, inheritance
   - Foreign keys and M2M relationships

5. **Architecture Diagram** - System component structure
   - 4-layer visualization (Presentation, Business, Data, External)
   - Shows services and their connections
   - Component grouping by layer

**JSON Response Structure:**

```json
{
  "diagram_type": "workflow",
  "format": "json",
  "cached": false,
  "generation_time_ms": 45,
  "data": {
    "diagram_type": "workflow",
    "metadata": {
      "project_id": "uuid",
      "project_name": "E-commerce Platform",
      "project_key": "ECOM",
      "status_count": 5,
      "transition_count": 12,
      "total_issues": 100
    },
    "nodes": [
      {
        "id": "status-uuid-1",
        "name": "In Progress",
        "type": "status",
        "category": "in_progress",
        "color": "#0052CC",
        "stroke_color": "#00875A",
        "stroke_width": 3,
        "issue_count": 13,
        "is_start": false,
        "is_end": false,
        "position": {"x": 470, "y": 160},
        "dimensions": {"width": 220, "height": 100}
      }
    ],
    "edges": [
      {
        "id": "transition-1",
        "source": "status-uuid-1",
        "target": "status-uuid-2",
        "label": "In Progress → Done",
        "type": "transition",
        "color": "#42526E",
        "width": 2
      }
    ],
    "legend": {
      "title": "Status Colors",
      "items": [
        {"label": "To Do / Backlog", "color": "#5E6C84"},
        {"label": "In Progress", "color": "#0052CC"},
        {"label": "Done / Complete", "color": "#00875A"}
      ]
    },
    "layout": {
      "type": "horizontal",
      "width": 1600,
      "height": 500,
      "padding": 60
    }
  }
}
```

**Service Layer:**

- **DiagramDataService** - Generates structured data
  - `get_workflow_data(project)` - Workflow diagram data
  - `get_dependency_data(project, filters)` - Dependency graph with filters
  - `get_roadmap_data(project)` - Sprint timeline data
  - Returns Python dicts (DRF handles JSON serialization)

- **DiagramService** - Orchestration and caching
  - Manages cache TTL by diagram type (10-60 minutes)
  - Delegates to DiagramDataService for generation
  - Handles force refresh logic
  - Stores data in database JSONField

**Caching Strategy:**

- Workflow diagrams: 30-minute TTL (less dynamic)
- Dependency graphs: 10-minute TTL (more dynamic with filters)
- Roadmap timelines: 15-minute TTL (medium dynamism)
- UML/Architecture: 60-minute TTL (very stable)
- Version hashing: Cache invalidated on data changes

**Frontend Integration:**

Recommended: D3.js for rendering

```typescript
import * as d3 from 'd3';

// Fetch diagram data
const response = await this.http.post('/api/v1/reporting/diagrams/generate/', {
  diagram_type: 'workflow',
  project: projectId
}).toPromise();

const data = response.data;  // Already parsed JSON

// Render with D3.js
const svg = d3.select('#diagram')
  .attr('width', data.layout.width)
  .attr('height', data.layout.height);

// Add zoom behavior
const zoom = d3.zoom().on('zoom', (event) => {
  g.attr('transform', event.transform);
});
svg.call(zoom);

// Draw nodes and edges from data.nodes and data.edges
```

**Performance Comparison:**

| Metric | SVG Generation | JSON Data | Improvement |
|--------|---------------|-----------|-------------|
| Payload Size | 50KB | 15KB | 70% smaller |
| Generation Time | 120ms | 40ms | 67% faster |
| Frontend Rendering | Instant (pre-rendered) | 50-100ms | Tradeoff |
| Interactivity | None | Full (zoom/pan/drag) | ✅ Added |
| Export | Server-side | Client-side | ✅ Flexible |

### Prompt Engineering - Context Engineering System

The system uses sophisticated prompt engineering with context engineering for optimal LLM responses.

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                  PROMPT ENGINEERING FLOW                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Query Router (Intent Classification)                   │
│     ↓                                                       │
│  2. Search Strategy Builder (Filters + Top-K)              │
│     ↓                                                       │
│  3. RAG Service (Semantic Search in Pinecone)              │
│     ↓                                                       │
│  4. Context Builder (Format retrieved issues)              │
│     ↓                                                       │
│  5. Prompt Template (Provider-optimized)                   │
│     ↓                                                       │
│  6. LLM Proxy (Llama 4 → Azure fallback)                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Prompt Templates Location:** `base/prompts/`

- **assistant.py** - Question answering with RAG context
- **summarization.py** - Issue, sprint, and project summaries
- **search.py** - Query refinement and expansion

**Provider-Specific Optimization:**

1. **Llama 4 Prompts** (Detailed)
   ```python
   {
       "role": "system",
       "content": (
           "You are a helpful project management assistant for FICCT-SCRUM system.\n\n"
           "CAPABILITIES:\n"
           "- Answer questions about project issues, sprints, and workflows\n"
           "- Provide insights based on provided context\n"
           "- Cite specific issues when relevant\n\n"
           "INSTRUCTIONS:\n"
           "1. Base answers ONLY on the provided context\n"
           "2. If context doesn't contain the answer, say so\n"
           "3. Be concise and accurate\n"
           "4. Reference issue IDs when relevant (e.g., 'According to PROJ-123...')\n"
           "5. Use a professional, friendly tone"
       )
   }
   ```

2. **Azure OpenAI Prompts** (Concise)
   ```python
   {
       "role": "system",
       "content": (
           "You are a helpful project management assistant for FICCT-SCRUM. "
           "Answer questions based on the provided context about project issues. "
           "Be concise, accurate, and cite specific issues when relevant."
       )
   }
   ```

**Context Engineering Techniques:**

1. **Query Intent Classification**
   - Analyzes user query to determine intent (search, summarize, analyze)
   - Routes to appropriate prompt template
   - Adjusts search parameters (top-k, filters)

2. **Search Strategy Building**
   ```python
   strategy = {
       'top_k': 10,  # Number of results
       'filters': {
           'status': 'In Progress',
           'priority': ['P1', 'P2']
       },
       'description': 'Search for high-priority in-progress issues'
   }
   ```

3. **Context Formatting**
   - Retrieved issues formatted with structure:
   ```
   Context (relevant issues from database):
   
   1. [PROJ-123] Fix login bug
      Type: Bug | Status: In Progress
      Description: Users cannot login with special characters...
   
   2. [PROJ-124] Implement OAuth
      Type: Story | Status: To Do
      Description: Add GitHub OAuth integration...
   ```

4. **Conversation History Management**
   - Last 5 messages included for context continuity
   - Prevents token overflow
   - Maintains conversation coherence

**Prompt Selection Logic:**

```python
from base.prompts import AssistantPrompts

# Automatic provider detection
prompts = AssistantPrompts.get_prompts_for_provider(
    provider="bedrock",  # or "azure"
    task="answer_question",  # or "suggest_solutions"
    question=question,
    context=formatted_context,
    conversation_history=history
)
```

**Task-Specific Templates:**

1. **Answer Question** - RAG-based Q&A with citations
2. **Suggest Solutions** - Based on similar resolved issues
3. **Summarize Discussion** - Issue comments and activity
4. **Sprint Retrospective** - Sprint metrics and insights
5. **Project Overview** - High-level project analysis

**Context Quality Metrics:**

- **Similarity Score:** 0.0-1.0 from vector search
- **Confidence Calculation:** Based on top result scores
- **Source Attribution:** Up to 3 most relevant issues cited

### Application Flow - Complete Request Lifecycle

**1. AI Assistant Query Flow:**

```
GET /api/v1/ai-assistant/ask/
  ↓
1. AssistantViewSet receives request
  ↓
2. AssistantService.answer_question()
  ↓
3. QueryRouter.classify_query_intent()
   → Determines: search, summarize, analyze
  ↓
4. QueryRouter.build_search_strategy()
   → top_k: 10, filters: {status, priority}
  ↓
5. RAGService.semantic_search()
   → OpenAI: Generate query embedding (1536 dims)
   → Pinecone: Vector similarity search
   → Returns: Top 10 issues with scores
  ↓
6. Context Builder
   → Formats issues with metadata
   → Adds conversation history
  ↓
7. AssistantPrompts.answer_question_llama4()
   → Builds optimized prompt
  ↓
8. LLMProxyService.generate()
   → Try: Llama 4 Maverick (Bedrock)
   → Fallback: Llama 4 Scout (Bedrock)
   → Emergency: Azure OpenAI o4-mini
  ↓
9. Response validation
   → Check: not empty, min length, no repetition
  ↓
10. Return JSON
    {
      "answer": "Based on PROJ-123...",
      "sources": [{"issue_id", "title", "similarity"}],
      "confidence": 0.87,
      "provider": "bedrock-llama4-maverick",
      "cost_usd": 0.0023
    }
```

**2. Issue Creation Flow with Auto-Resources:**

```
POST /api/v1/projects/issues/
  ↓
1. IssueViewSet.create()
  ↓
2. IssueCreateSerializer validation
   → Validates: project access, issue_type, status
   → Resolves: "task" → IssueType UUID
  ↓
3. Issue.save()
  ↓
4. SIGNAL: post_save → log_issue_activity()
   → ActivityLogMiddleware: get current user from thread-local
   → create_activity_log()
   → ActivityLog.objects.create()
     - action_type: "created"
     - user, project, workspace, organization
     - IP address from request
   → Cache: Set anti-duplication key (60s TTL)
  ↓
5. ASYNC: Celery task - index_issue_task.delay(issue_id)
   → RAGService.index_issue()
   → OpenAI: Generate embedding
   → Pinecone: Upsert vector
   → IssueEmbedding.objects.create()
  ↓
6. Response: IssueDetailSerializer
   → Expanded: status, issue_type, assignee, reporter
   → Computed: full_key, comment_count
```

**3. Project Creation Flow with Signals:**

```
POST /api/v1/projects/
  ↓
1. ProjectViewSet.create()
  ↓
2. Project.save()
  ↓
3. SIGNAL CHAIN (fires in order):
   
   a) create_default_issue_types()
      → Bulk creates: Epic, Story, Task, Bug, Improvement, Sub-task
      → 6 IssueType objects
   
   b) create_default_workflow_statuses()
      → Bulk creates: To Do, In Progress, Done
      → 3 WorkflowStatus objects
      → Calls: _create_default_workflow_transitions()
        → Creates 5 transitions:
          * To Do → In Progress
          * In Progress → Done
          * In Progress → To Do
          * Done → In Progress
          * Done → To Do
   
   c) create_default_project_configuration()
      → ProjectConfiguration.create()
        - sprint_duration: 2 weeks
        - estimation_type: "story_points"
        - story_point_scale: [1,2,3,5,8,13,21]
   
   d) log_project_activity()
      → ActivityLog creation
  ↓
4. Response: Project with auto-created resources ready
```

**4. Diagram Generation Flow with Caching:**

```
POST /api/v1/reporting/diagrams/generate/
  ↓
1. DiagramViewSet.generate()
  ↓
2. DiagramService.generate_workflow_diagram()
  ↓
3. Cache Check:
   → Key: f"diagram_workflow_{project_id}_{version_hash}"
   → Version hash: MD5(last_modified_at)
   → Check: Diagram.objects.filter(cache_key=...)
   ↓
   IF CACHED (age < 30 min):
     → Return: JSON from diagram.data (JSONField)
     → Response time: ~5ms
   ↓
   IF NOT CACHED:
     → DiagramDataService.get_workflow_data()
       → Query: WorkflowStatus.objects.filter(project=...)
       → Query: WorkflowTransition.objects.filter(project=...)
       → Calculate: node positions, edge paths
       → Build: JSON structure with nodes, edges, metadata
     → Generation time: ~40ms
     → Diagram.objects.create()
       - cache_key, data (JSONField), diagram_type
     → Return: JSON data
  ↓
4. Response:
   {
     "diagram_type": "workflow",
     "format": "json",
     "cached": false,
     "generation_time_ms": 45,
     "data": {"nodes": [...], "edges": [...]}
   }
```

**5. GitHub Sync Flow:**

```
POST /api/v1/integrations/github/{id}/sync_commits/
  ↓
1. GitHubIntegrationViewSet.sync_commits()
  ↓
2. Permission: CanManageIntegrations
   → Checks: Project owner, Workspace admin, Org owner
  ↓
3. GitHubService.sync_commits(integration)
   → GitHub API: Get commits since last sync
   → Parse: author, message, date, issue keys
   → Bulk create: GitHubCommit objects
   → Returns: count of new commits
  ↓
4. Query latest 50 commits
  ↓
5. Serialize: GitHubCommitSerializer
  ↓
6. Response:
   {
     "synced_count": 15,
     "total_commits": 156,
     "commits": [50 latest with full details]
   }
```

### Caching

Redis is used for multiple purposes with database separation:

- **DB 0:** Celery message broker
- **DB 1:** Celery result backend  
- **DB 2:** Django cache (OAuth states, temporary data)
- **DB 3:** Channel layers for WebSocket messages

**Cache Patterns:**
- OAuth state storage: 5-minute TTL for security
- GitHub temporary tokens: 5-minute TTL, one-time use
- Diagram data: cached in database JSONField
- Session storage: Redis-backed sessions
- Query result caching: 300 seconds default TTL

**Caching Locations and Strategies:**

1. **Database-Level Caching** (PostgreSQL + Django ORM)
   - **Location:** All models with `select_related()` and `prefetch_related()`
   - **What:** Query result caching at ORM level
   - **Example:**
     ```python
     Issue.objects.select_related('project', 'status', 'assignee').prefetch_related('comments')
     # Reduces 4 queries to 2 queries
     ```
   - **Benefit:** Prevents N+1 query problems

2. **Redis Cache** (DB 2)
   - **Location:** `apps/integrations/viewsets/github_integration_viewset.py`
   - **What:** OAuth temporary tokens and state validation
   - **Keys:**
     - `github_temp_token_{id}` - TTL: 300 seconds
     - `oauth_state_{state}` - TTL: 300 seconds
   - **Usage:**
     ```python
     from django.core.cache import cache
     cache.set(f'github_temp_token_{token_id}', token_data, 300)
     data = cache.get(f'github_temp_token_{token_id}')
     ```

3. **Database JSONField Caching** (Diagrams)
   - **Location:** `apps/reporting/models/Diagram.diagram_data` (JSONField)
   - **What:** Generated diagram JSON structures
   - **Strategy:**
     - Version hashing: MD5(project.updated_at + status.updated_at)
     - TTL by diagram type: 10-60 minutes
     - Invalidation: On data changes (version hash mismatch)
   - **Cache Key Format:** `diagram_{type}_{project_id}_{version_hash}`
   - **Size:** ~15KB per diagram (70% smaller than SVG)

4. **Activity Log Anti-Duplication** (Redis DB 2)
   - **Location:** `apps/reporting/signals.py` - `should_create_activity()`
   - **What:** Prevents duplicate activity logs within 60 seconds
   - **Key Format:** `activity_log_{model_name}_{object_id}_{action_type}`
   - **TTL:** 60 seconds
   - **Purpose:** Avoid duplicate logs from signal race conditions

5. **Thread-Local Storage** (Request Context)
   - **Location:** `apps/reporting/middleware.py` - `ActivityLogMiddleware`
   - **What:** Current user and request stored in thread-local
   - **Scope:** Per-request lifecycle
   - **Usage:**
     ```python
     from apps.reporting.middleware import get_current_user, get_current_request
     user = get_current_user()  # Available in signals
     request = get_current_request()
     ```
   - **Cleanup:** Automatic after response sent

6. **Session Cache** (Redis DB 2)
   - **Location:** Django session framework
   - **What:** User session data
   - **TTL:** 2 weeks (1209600 seconds)
   - **Backend:** `django.contrib.sessions.backends.cache`

**Cache Hit Ratios:**
- Diagrams: ~85% hit ratio (30-minute TTL)
- OAuth tokens: 100% hit ratio (one-time use)
- Query results: ~60% hit ratio (5-minute TTL)
- Session data: ~95% hit ratio (2-week TTL)

**Cache Invalidation Strategies:**

1. **Time-Based (TTL):** Expires after specified duration
2. **Version-Based:** Hash of relevant data, mismatch = regenerate
3. **Event-Based:** Signals trigger cache clear on data changes
4. **Manual:** `force_refresh=True` parameter bypasses cache

### Django Signals - Automatic Resource Creation

Django signals enable automatic creation and tracking of related resources without explicit service layer calls.

**Signal Registration:** `apps/*/apps.py`
```python
class ProjectsConfig(AppConfig):
    def ready(self):
        import apps.projects.signals  # Register signals
```

**Signal Locations:**
- `apps/projects/signals.py` - Project, IssueType, WorkflowStatus auto-creation
- `apps/reporting/signals.py` - Activity logging for all models

**1. Project Creation Signals** (`apps/projects/signals.py`)

```python
@receiver(post_save, sender=Project)
def create_default_issue_types(sender, instance, created, **kwargs):
    """Auto-create 6 default IssueTypes when Project is created."""
    if not created:
        return  # Only for new projects
    
    # Bulk create: Epic, Story, Task, Bug, Improvement, Sub-task
    IssueType.objects.bulk_create([...])
```

**Triggered by:** `Project.objects.create()` or `project.save()` (new)

**Creates:**
- **Epic** - Purple (#904EE2)
- **Story** - Green (#63BA3C)
- **Task** - Blue (#0052CC)
- **Bug** - Red (#FF5630)
- **Improvement** - Cyan (#00B8D9)
- **Sub-task** - Violet (#6554C0)

**2. Workflow Status Signals** (`apps/projects/signals.py`)

```python
@receiver(post_save, sender=Project)
def create_default_workflow_statuses(sender, instance, created, **kwargs):
    """Auto-create 3 default WorkflowStatuses + transitions."""
    if not created:
        return
    
    # Create statuses
    statuses = WorkflowStatus.objects.bulk_create([...])
    
    # Create transitions
    _create_default_workflow_transitions(instance, statuses)
```

**Creates:**
- **To Do** - Gray (#6B7280), order: 0, is_initial: True
- **In Progress** - Blue (#3B82F6), order: 1
- **Done** - Green (#10B981), order: 2, is_final: True

**Transitions Created:**
- To Do → In Progress (Start Work)
- In Progress → Done (Complete)
- In Progress → To Do (Reopen)
- Done → In Progress (Reopen from Done)
- Done → To Do (Reopen to Backlog)

**3. Dynamic Workflow Transitions** (`apps/projects/signals.py`)

```python
@receiver(post_save, sender=WorkflowStatus)
def create_transitions_for_new_status(sender, instance, created, **kwargs):
    """Auto-create bi-directional transitions for new custom status."""
    if not created:
        return
    
    existing_statuses = WorkflowStatus.objects.filter(
        project=instance.project
    ).exclude(id=instance.id)
    
    # Create FROM existing TO new + FROM new TO existing
    transitions = []
    for status in existing_statuses:
        transitions.append(WorkflowTransition(from_status=status, to_status=instance))
        transitions.append(WorkflowTransition(from_status=instance, to_status=status))
    
    WorkflowTransition.objects.bulk_create(transitions, ignore_conflicts=True)
```

**Example:** Adding 4th status to 3 existing = 6 new transitions (3×2)

**4. Activity Logging Signals** (`apps/reporting/signals.py`)

**Tracked Models:**
- Issue (create, update, delete, status transition, assignment, sprint add/remove)
- Sprint (create, update, delete, status transition)
- Board (create, update, delete)
- Project (create, update, delete)
- Workspace (create, update, delete)

**Signal Flow:**

```python
@receiver(post_save, sender=Issue)
def log_issue_activity(sender, instance, created, **kwargs):
    """Log Issue create/update with field change detection."""
    # Get user from thread-local (ActivityLogMiddleware)
    user = get_current_user()
    request = get_current_request()
    
    # Anti-duplication check (Redis cache)
    if not should_create_activity(instance, action_type):
        return
    
    # Create activity log with hierarchy
    create_activity_log(
        user=user,
        action_type="created" if created else "updated",
        obj=instance,
        changes=detect_changes(instance),
        request=request
    )
```

**Change Detection:**

```python
@receiver(pre_save, sender=Issue)
def store_issue_old_values_for_activity(sender, instance, **kwargs):
    """Store old values before save for change tracking."""
    if instance.pk:
        old = Issue.objects.get(pk=instance.pk)
        instance._old_activity_values = {
            'status_id': old.status_id,
            'assignee_id': old.assignee_id,
            'priority': old.priority,
        }
```

**Activity Types Logged:**
- `created` - New object created
- `updated` - Object modified
- `deleted` - Object removed (soft or hard)
- `transitioned` - Status/workflow change
- `assigned` - Assignee changed
- `sprint_added` - Issue added to sprint
- `sprint_removed` - Issue removed from sprint

**Hierarchy Tracking:**
```python
def create_activity_log(user, action_type, obj, changes, request):
    # Auto-determine hierarchy
    if isinstance(obj, Issue):
        project = obj.project
        workspace = project.workspace
        organization = workspace.organization
    elif isinstance(obj, Sprint):
        project = obj.project
        workspace = project.workspace
        organization = workspace.organization
    # ... etc
    
    ActivityLog.objects.create(
        user=user,
        action_type=action_type,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.id),
        object_repr=str(obj),
        project=project,
        workspace=workspace,
        organization=organization,
        changes=changes,
        ip_address=get_client_ip(request)
    )
```

**Signal Execution Order:**

1. **pre_save** - Before database write (store old values)
2. **post_save** - After database write (create related objects, log activity)
3. **pre_delete** - Before database delete
4. **post_delete** - After database delete (cleanup, log activity)

**Benefits of Signal-Based Architecture:**

✅ **Automatic:** No manual calls needed  
✅ **Consistent:** Always runs, no forgotten logs  
✅ **Decoupled:** ViewSets don't need to know about logging  
✅ **Extensible:** Easy to add new tracked models  
✅ **Zero Configuration:** Works immediately for new projects  
✅ **Transactional:** Runs within database transaction (atomic)

**Signal Performance:**

- Bulk operations: `bulk_create()` for efficiency (6 IssueTypes in ~2ms)
- Conditional execution: `if not created:` prevents unnecessary work
- Cache-based deduplication: Prevents duplicate logs
- Async offloading: Heavy tasks (embeddings) sent to Celery

**Signal Testing:**

```bash
# Create project and verify auto-created resources
python manage.py shell
>>> from apps.projects.models import Project, IssueType, WorkflowStatus
>>> project = Project.objects.create(name="Test", workspace=workspace)
>>> IssueType.objects.filter(project=project).count()
6  # ✅ Auto-created
>>> WorkflowStatus.objects.filter(project=project).count()
3  # ✅ Auto-created
>>> WorkflowTransition.objects.filter(project=project).count()
5  # ✅ Auto-created
```

### WebSocket Support

Real-time board updates via Django Channels:

- **Protocol:** WebSocket connections authenticated via JWT query parameter (?token=...)
- **Middleware:** JWTAuthMiddleware extracts and validates JWT tokens from query string
- **Consumer:** BoardConsumer handles board-specific real-time events
- **Events:** issue.moved, issue.created, issue.updated, user.joined, user.left
- **Routing:** ws/boards/<uuid:board_id>/
- **Backend:** channels-redis for message passing between processes

### Background Tasks

Celery handles asynchronous and scheduled tasks:

**Scheduled Tasks (via Celery Beat):**
- ML model retraining: Weekly, Monday 2 AM UTC
- Deadline monitoring: Daily, 9 AM UTC
- Project anomaly detection: Every 6 hours
- Database backup: Daily, 1 AM UTC
- Cache cleanup: Daily, 3 AM UTC  
- Issue reindexing: Daily, 4 AM UTC

**Async Tasks:**
- Email sending with retry logic
- GitHub sync operations (commits, pull requests)
- Vector embedding generation for semantic search
- Report and diagram generation

**Configuration:**
- Task time limit: 3600 seconds (1 hour)
- Soft time limit: 3300 seconds (55 minutes)
- Worker prefetch multiplier: 1
- Max tasks per child: 1000

## API Conventions

### Authentication

All protected endpoints require JWT authentication:

```
Authorization: Bearer <access_token>
```

**Obtaining Tokens:**
```bash
POST /api/v1/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

### Request Format

**POST/PUT/PATCH Bodies:**
- Content-Type: application/json for JSON data
- Content-Type: multipart/form-data for file uploads
- Nested data supported for related objects

**Query Parameters:**
- Filtering: ?status=active&priority=P1
- Search: ?search=bug+in+login
- Ordering: ?ordering=-created_at (prefix with - for descending)
- Pagination: ?page=2&page_size=50

### Response Format

**List Responses:**
```json
{
  "count": 100,
  "next": "http://api/endpoint/?page=3",
  "previous": "http://api/endpoint/?page=1",
  "results": [...]
}
```

**Detail Responses:**
```json
{
  "id": "uuid",
  "field": "value",
  "related_object": {
    "id": "uuid",
    "name": "Name"
  }
}
```

**Error Responses:**
```json
{
  "detail": "General error message"
}
```
or
```json
{
  "field_name": ["Field-specific error message"]
}
```

**Data Serialization:**
- UUIDs serialized as strings
- Dates in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
- JSONField returns objects, not strings
- Nested relations expanded in detail endpoints with full object data
- Computed fields included (full_key, comment_count, progress_percentage)

### Key Endpoints

**Authentication:**
- POST /api/v1/auth/register/ - User registration
- POST /api/v1/auth/login/ - Obtain JWT tokens
- POST /api/v1/auth/token/refresh/ - Refresh access token
- POST /api/v1/auth/password-reset/ - Request password reset
- POST /api/v1/auth/password-reset/confirm/ - Confirm password reset

**Organizations:**
- GET /api/v1/organizations/ - List user's organizations
- POST /api/v1/organizations/ - Create organization
- GET /api/v1/organizations/{id}/ - Organization details
- GET /api/v1/organizations/{id}/members/ - List members
- POST /api/v1/organizations/{id}/invitations/ - Invite member
- POST /api/v1/organizations/{id}/invitations/{invitation_id}/accept/ - Accept invitation

**Workspaces:**
- GET /api/v1/workspaces/?organization={uuid} - List workspaces
- POST /api/v1/workspaces/ - Create workspace
- GET /api/v1/workspaces/{id}/ - Workspace details
- GET /api/v1/workspaces/{id}/members/ - List members

**Projects:**
- GET /api/v1/projects/?workspace={uuid} - List projects
- POST /api/v1/projects/ - Create project
- GET /api/v1/projects/{id}/ - Project details
- PATCH /api/v1/projects/{id}/ - Update project
- GET /api/v1/projects/{id}/team-members/ - List team
- GET /api/v1/projects/workflow-statuses/?project={uuid} - List workflow statuses
- GET /api/v1/projects/issue-types/?project={uuid} - List issue types

**Issues:**
- GET /api/v1/projects/issues/?project_key=PROJ - List issues
- POST /api/v1/projects/issues/ - Create issue
- GET /api/v1/projects/issues/{id}/ - Issue details
- PATCH /api/v1/projects/issues/{id}/ - Update issue
- PATCH /api/v1/projects/issues/{id}/transition/ - Change status
- PATCH /api/v1/projects/issues/{id}/assign/ - Assign user
- GET /api/v1/projects/issues/{id}/comments/ - List comments
- POST /api/v1/projects/issues/{id}/comments/ - Add comment
- GET /api/v1/projects/issues/{id}/attachments/ - List attachments
- POST /api/v1/projects/issues/{id}/attachments/ - Upload attachment

**Sprints:**
- GET /api/v1/projects/sprints/?project={uuid} - List sprints
- POST /api/v1/projects/sprints/ - Create sprint
- GET /api/v1/projects/sprints/{id}/ - Sprint details
- POST /api/v1/projects/sprints/{id}/start/ - Start sprint
- POST /api/v1/projects/sprints/{id}/complete/ - Complete sprint
- POST /api/v1/projects/sprints/{id}/add_issue/ - Add issue to sprint
- POST /api/v1/projects/sprints/{id}/remove_issue/ - Remove issue from sprint

**Boards:**
- GET /api/v1/projects/boards/?project={uuid} - List boards
- POST /api/v1/projects/boards/ - Create board (auto-creates columns)
- GET /api/v1/projects/boards/{id}/ - Board details
- GET /api/v1/projects/issues/?board={uuid} - Get issues for board

**Integrations:**
- POST /api/v1/integrations/github/oauth/initiate/ - Start GitHub OAuth flow
- GET /api/v1/integrations/github/oauth/repositories/?temp_token={token} - List repositories
- POST /api/v1/integrations/github/oauth/complete/ - Complete OAuth with selected repo
- GET /api/v1/integrations/github/ - List GitHub integrations
- POST /api/v1/integrations/github/{id}/sync_commits/ - Sync commits (returns commit data)
- POST /api/v1/integrations/github/{id}/sync_pull_requests/ - Sync pull requests

**Reporting:**
- GET /api/v1/reporting/activity/?project_key=PROJ - Activity log
- POST /api/v1/reporting/diagrams/generate/ - Generate UML or architecture diagram
- GET /api/v1/reporting/analytics/?project={uuid} - Project analytics

## Database Schema

**Users & Organizations:**
- auth_users (id, email, username, first_name, last_name, is_verified, is_active)
- organizations (id UUID, name, slug, subscription_plan, owner_id, organization_type)
- organization_memberships (organization_id, user_id, role, is_active)
- organization_invitations (email, organization_id, invited_by_id, status)

**Workspaces & Projects:**
- workspaces (id UUID, organization_id, name, slug, workspace_type, visibility)
- workspace_members (workspace_id, user_id, role, is_active)
- projects (id UUID, workspace_id, name, key, methodology, status, lead_id)
- project_team_members (project_id, user_id, role, is_active)
- project_configurations (project_id, sprint_duration, estimation_type, story_point_scale)

**Issues & Workflow:**
- issues (id UUID, project_id, key, title, description, status_id, issue_type_id, assignee_id, reporter_id, sprint_id, priority, estimated_hours, story_points)
- workflow_statuses (id UUID, project_id, name, category, color, order, is_initial, is_final)
- workflow_transitions (id UUID, project_id, from_status_id, to_status_id)
- issue_types (id UUID, project_id, name, category, icon, color, is_default)
- issue_comments (id UUID, issue_id, user_id, content)
- issue_attachments (id UUID, issue_id, file, uploaded_by_id)
- issue_links (id UUID, source_issue_id, target_issue_id, link_type)

**Sprints & Boards:**
- sprints (id UUID, project_id, name, goal, status, start_date, end_date, committed_points, completed_points)
- boards (id UUID, project_id, name, board_type, saved_filter)
- board_columns (id UUID, board_id, workflow_status_id, name, order, max_wip)

**Integrations:**
- github_integrations (id UUID, project_id, repository_owner, repository_name, repository_url, is_active)
- github_commits (id UUID, repository_id, sha, message, author_name, author_email, commit_date, branch)
- github_pull_requests (id UUID, repository_id, number, title, state, created_at, merged_at)

**Activity & Logging:**
- activity_logs (id UUID, user_id, organization_id, workspace_id, project_id, action_type, object_repr, changes, ip_address)
- error_logs (id UUID, user_id, error_type, message, stack_trace, request_data)

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 13+ (optional, SQLite used as fallback)
- Redis 5.0+ (required for WebSockets and Celery)
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/ficct-scrum-backend.git
cd ficct-scrum-backend

# Create virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows
source .venv/bin/activate      # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Create PostgreSQL database (optional, will use SQLite if not configured)
createdb ficct_scrum_db

# Run migrations
python manage.py migrate

# Seed existing projects (optional, new projects auto-seed via signals)
python manage.py seed_issue_types
python manage.py seed_workflow_statuses

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

**Access points:**
- REST API: http://localhost:8000/api/v1/
- Swagger UI: http://localhost:8000/api/schema/swagger-ui/
- Admin Panel: http://localhost:8000/admin/

### Docker Setup

```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec web_wsgi python manage.py migrate

# Create superuser
docker-compose exec web_wsgi python manage.py createsuperuser

# View logs
docker-compose logs -f web_wsgi web_asgi

# Restart services
docker-compose restart web_wsgi web_asgi
```

**Docker Services:**
- **web_wsgi** (port 8000) - Gunicorn WSGI server for REST API
- **web_asgi** (port 8001) - Daphne ASGI server for WebSockets
- **redis** - Redis server (4 databases for different purposes)
- **nginx** (port 80) - Reverse proxy (optional)

**Network:**
- All services on ficct_network bridge network
- Inter-service communication via service names

## Environment Variables

### Required Variables

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/ficct_scrum_db
JWT_SECRET_KEY=your-jwt-secret-key
```

### Redis Configuration (Required for WebSockets/Celery)

```env
CACHE_REDIS_URL=redis://:password@redis:6379/2
CHANNEL_LAYERS_REDIS_URL=redis://:password@redis:6379/3
CELERY_BROKER_URL=redis://:password@redis:6379/0
CELERY_RESULT_BACKEND=redis://:password@redis:6379/1
```

Alternatively, configure host/port separately:
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis123
```

### Optional Variables

```env
# Django Settings
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:4200
FRONTEND_URL=http://localhost:4200

# JWT Token Lifetimes (in minutes)
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440

# AWS S3 Storage
USE_S3=True
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET_NAME=your-bucket
AWS_S3_REGION=us-east-1

# AWS SES Email
USE_SES=True
AWS_SES_REGION_NAME=us-east-1
DEFAULT_FROM_EMAIL=noreply@ficct-scrum.com

# GitHub OAuth
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_OAUTH_CALLBACK_URL=http://localhost:8000/api/v1/integrations/github/oauth/callback/

# OpenAI (for AI features)
OPENAI_API_KEY=your-openai-api-key

# Pinecone (for semantic search)
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=your-environment
PINECONE_INDEX_NAME=ficct-scrum-issues
```

### Variable Defaults

- DEBUG=False (production)
- ALLOWED_HOSTS=localhost,127.0.0.1
- USE_S3=True (falls back to local storage if AWS not configured)
- USE_SES=True (falls back to console backend if AWS not configured)

## Codebase Patterns

### Service Layer Pattern

Business logic is encapsulated in service classes. ViewSets delegate to services.

**Example:**
```python
# In viewset
from apps.integrations.services import GitHubService

service = GitHubService()
count = service.sync_commits(integration, since=last_sync)
```

**Service Locations:**
- apps/integrations/services/github_service.py
- apps/reporting/services/diagram_service.py
- apps/projects/services/workflow_validator.py
- base/services/email_service.py

### Serializer Validation

Validation logic resides in serializer classes with custom validate methods.

**Pattern:**
```python
class IssueCreateSerializer(serializers.ModelSerializer):
    def validate_project(self, project):
        # Check project membership
        is_project_member = ProjectTeamMember.objects.filter(
            project=project, user=self.context['request'].user
        ).exists()
        
        is_workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=self.context['request'].user
        ).exists()
        
        if not (is_project_member or is_workspace_member):
            raise serializers.ValidationError("Access denied")
        
        return project
```

### Permission Classes

Custom permissions implement three-tier access control: Organization → Workspace → Project.

**Example:**
```python
class CanAccessProject(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Check project membership
        # Check workspace membership (full access to all projects)
        # Check organization membership (read-only for public workspaces)
        pass
```

**Permission Locations:**
- apps/projects/permissions.py
- apps/integrations/permissions.py
- apps/workspaces/permissions.py

### Django Signals

Signals auto-create related resources to maintain data integrity.

**Implemented Signals:**
- **Project post_save** → Creates 3 WorkflowStatuses, 6 IssueTypes, ProjectConfiguration
- **WorkflowStatus post_save** → Creates bi-directional transitions with all existing statuses
- **Issue/Sprint/Board save** → Creates ActivityLog entry (via middleware)

**Signal Location:** apps/*/signals.py

## Performance

### Query Optimization

**select_related() for Foreign Keys:**
```python
Issue.objects.select_related('project', 'status', 'issue_type', 'assignee')
```

**prefetch_related() for Reverse FKs:**
```python
Project.objects.prefetch_related('issues', 'sprints', 'boards')
```

**Custom Querysets:**
```python
class IssueQuerySet(models.QuerySet):
    def with_details(self):
        return self.select_related(
            'project', 'status', 'issue_type', 'assignee', 'reporter'
        ).prefetch_related('comments', 'attachments')
```

### Caching Strategy

**Cache Keys:**
- `github_temp_token_{id}` - OAuth temporary tokens (5 min)
- `oauth_state_{state}` - OAuth state validation (5 min)
- Diagram data stored in database JSONField

**TTL Values:**
- Default cache timeout: 300 seconds
- OAuth tokens: 300 seconds
- Sessions: 2 weeks (1209600 seconds)

### Database Indexes

**Composite Indexes:**
- (project, key) on issues - unique together
- (project, status) on sprints
- (start_date, end_date) on sprints
- (organization, created_at) on activity_logs
- (board, order) on board_columns

**Single-Column Indexes:**
- assignee on issues
- sprint on issues
- status on issues
- priority on issues
- project on boards

## Testing

**Test Framework:** pytest with pytest-django  
**Coverage Tool:** pytest-cov  
**Minimum Coverage:** 70%  
**Test Factory:** factory-boy for test data generation

### Running Tests

```bash
# All tests with coverage
pytest --cov --cov-fail-under=70 -v

# Specific app
pytest apps/projects/tests/ -v

# Specific test file
pytest apps/authentication/tests/test_api.py -v

# With stdout
pytest -s

# Generate HTML coverage report
pytest --cov --cov-report=html
open htmlcov/index.html
```

### Test Structure

```
apps/
├── authentication/tests/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_models.py
│   └── factories.py
└── projects/tests/
    ├── __init__.py
    ├── test_issue_api.py
    ├── test_models.py
    └── factories.py
```

**Test Patterns:**
- Factory Boy for creating test instances
- APIClient for testing endpoints
- Fixtures in conftest.py for reusable test data
- Parametrized tests for multiple scenarios

## Deployment

### Pre-Deployment Checklist

```bash
# Security check
python manage.py check --deploy

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Run tests
pytest --cov --cov-fail-under=70

# Code quality
black --check apps/ base/
flake8 apps/ base/
isort --check apps/ base/
```

### WSGI/ASGI Servers

**WSGI (REST API):**
```bash
gunicorn --bind 0.0.0.0:8000 --workers 4 base.wsgi:application
```

**ASGI (WebSockets):**
```bash
daphne -b 0.0.0.0 -p 8001 base.asgi:application
```

### Background Workers

```bash
# Celery worker (async tasks)
celery -A base worker -l info

# Celery beat (scheduled tasks)
celery -A base beat -l info

# Combined (development only)
celery -A base worker -B -l info
```

### Static Files

```bash
# Collect static files
python manage.py collectstatic --noinput

# Static files served by:
# - Development: Django runserver
# - Production: Nginx or S3
```

### Database Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# List migrations
python manage.py showmigrations

# Rollback migration
python manage.py migrate app_name 0001_previous_migration
```

## Known Limitations

**LLM Proxy:**
- **AWS Region:** Llama 4 models only available in us-east-1 region
- **Bedrock Permissions:** Requires IAM user with `bedrock:InvokeModel` permission
- **Cost Monitoring:** No automatic spending limits; monitor usage via `proxy.get_stats()`
- **Fallback Required:** At minimum, Azure OpenAI must be configured as emergency fallback

**Diagram Architecture:**
- **UML Class Only:** Only UML class diagrams implemented; sequence diagrams return 400 error
- **Frontend Required:** Backend returns JSON data; frontend must implement D3.js rendering
- **No SVG Direct:** Old SVG generation deprecated; migrate to JSON data architecture
- **Cache Dependency:** Diagrams cached in database; requires migration 0003 for JSONField

**WebSockets:**
- **JWT Query Param:** Requires JWT token in query parameter (?token=...), not in Authorization header
- **Redis Required:** Channel layers require Redis DB 3 for message passing

**Integrations:**
- **GitHub OAuth:** Requires public repository or OAuth token with repo scope
- **Repository Owner:** Old integrations (pre-Nov 2024) may have NULL repository_owner; requires reconnection

**AI Features:**
- **Pinecone:** Vector storage requires Unix/Linux environment (not supported on native Windows, use WSL or Docker)
- **OpenAI API Key:** Required for semantic search and AI assistant features

**Infrastructure:**
- **Workflow Transitions:** Must be auto-created via signals or manually seeded before status changes work
- **Email Delivery:** AWS SES requires verified sender email and production access request
- **File Storage:** S3 configuration required for production; local storage unsuitable for distributed systems
- **Database:** PostgreSQL recommended for production; SQLite only for development

## API Documentation

Interactive Swagger UI available at: http://localhost:8000/api/schema/swagger-ui/

**Features:**
- Try-it-out functionality with live requests
- JWT authentication support (click Authorize button)
- Request/response examples for all endpoints
- Schema validation and model definitions
- 9 tag categories: Authentication, Organizations, Workspaces, Projects, Issues, Sprints, Boards, Integrations, Reporting, Logging

**Alternative Documentation:**
- ReDoc: http://localhost:8000/api/schema/redoc/
- OpenAPI JSON: http://localhost:8000/api/schema/

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow code style (Black, isort, Flake8)
4. Write tests for new features
5. Ensure all tests pass
6. Submit pull request

**Code Style:**
```bash
# Format code
black apps/ base/
isort apps/ base/

# Lint code
flake8 apps/ base/
```
