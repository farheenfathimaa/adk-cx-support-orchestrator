# ADK CX Support Orchestrator

**Status: Complete** — fully implemented, tested (16 unit tests + live E2E verified on `gemini-3.5-flash-lite`), and pushed.

Multi-agent customer-support triage system built with **Google's Agent Development Kit (ADK 2.0+)** and **Gemini 3.5 Flash Lite** (configurable via `ADK_MODEL`).

Classifies incoming support tickets, fans out to specialist sub-agents for ambiguous cases, refines draft replies through a generator/critic loop, and grounds responses in knowledge-base articles and CRM data via MCP tool integration.

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │          CXSupportTriageAgent (root)        │
                    │                 Agent (LlmAgent)            │
                    └──────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │          CXSupportOrchestrator              │
                    │              SequentialAgent                │
                    └──────────────────┬──────────────────────────┘
                                       │
          ┌────────────────────────────┼─────────────────────────────┐
          │                            │                             │
 ┌────────▼─────────┐   ┌──────────────▼──────────────┐   ┌────────▼──────────┐
 │  IntakePipeline  │   │       RoutingDecision       │   │  ParallelSpecial- │
 │ SequentialAgent  │   │      (BaseAgent — LLM)      │   │  istFanOut        │
 │                  │   │  Confidence ≥ 0.6? ──────── │   │ ParallelAgent     │
 │ ┌──────────────┐ │   │  Yes → skip fan-out          │   │ ┌───────────────┐ │
 │ │ExtractorAgent│ │   │  No  → fan-out to 3 agents   │   │ │BillingSpecial.│ │
 │ │  (LLM)       │ │   └──────────────┬──────────────┘   │ │TechnicalSpec. │ │
 │ └──────┬───────┘ │                  │                   │ │RefundSpecial. │ │
 │ ┌──────▼───────┐ │   ┌──────────────▼──────────────┐   │ └───────┬───────┘ │
 │ │ClassifierAgt│ │   │  GatherSpecialistScores      │   │         │         │
 │ │  (LLM)       │ │   │  (BaseAgent — deterministic) │   │         │         │
 │ └──────┬───────┘ │   │  Pick highest confidence     │   └─────────┼─────────┘
 └────────┼─────────┘   └──────────────┬──────────────┘             │
          │                            │                             │
          └────────────────────────────┼─────────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │           DraftCriticLoop                   │
                    │              LoopAgent (max 3)              │
                    │                                             │
                    │  ┌─────────────────┐   ┌─────────────────┐  │
                    │  │DraftResponseAgent│◄──│   CriticAgent   │  │
                    │  │  (LLM + tools)  │──►│    (LLM)        │  │
                    │  └────────┬────────┘   └────────┬────────┘  │
                    │           │                     │            │
                    │           └──────┬──────────────┘            │
                    │           ┌──────▼──────────┐                │
                    │           │LoopTerminator   │                │
                    │           │(BaseAgent)      │                │
                    │           │escalate=True    │                │
                    │           │  → stop loop    │                │
                    │           └─────────────────┘                │
                    └──────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │        FinalResponseAssembler               │
                    │           (BaseAgent — deterministic)        │
                    │  If critic passed → return draft as-is      │
                    │  If loop exhausted → add human-review note  │
                    └──────────────────┬──────────────────────────┘
                                       │
                              Final Response

  ──────────── MCP Server (stdio subprocess) ────────────
  ┌──────────────────────────────────────────────────────┐
  │  knowledge_base_search(query, category) → articles   │
  │  get_customer_info(customer_id) → profile + orders   │
  └──────────────────────────────────────────────────────┘
```

### Agent Composition Patterns Used

| Pattern | Where | Why |
|---|---|---|
| **SequentialAgent** | `IntakePipeline` | Extract → classify must be ordered; later step needs earlier output |
| **ParallelAgent** | `ParallelSpecialistFanOut` | 3 specialists run concurrently for speed; deterministic gather picks winner |
| **LoopAgent** | `DraftCriticLoop` | Iterative refinement with explicit loop-limit (max 3) and escalation |
| **BaseAgent** (custom) | `RoutingDecision`, `ConditionalSpecialistFanOut`, `Gatherer`, `LoopTerminator`, `FinalAssembler` | Deterministic logic — no LLM cost for gating, parsing, merging, or control flow |

### Example Trace

Real (slightly abridged) run of `python scripts/test_live.py billing` on
`gemini-3.5-flash-lite`. Input: `"I was charged twice for my subscription this
month. My account is CUST-001."`

```
INFO: RoutingDecision: category=refund confidence=0.95 ambiguous=False   ← classifier
INFO: ConditionalSpecialistFanOut: skipping fan-out (not ambiguous)      ← saved 3 LLM calls
INFO: KB search: query='double charge refund subscription' category='refund'   ← tool 1
INFO: CRM lookup: customer_id='CUST-001'                                 ← tool 2
INFO: CriticStatusChecker: stopping loop — passed                        ← critic OK
INFO: FinalResponseAssembler: draft approved on iteration 1

→ "Hello Alice,
   I am very sorry to hear that you were accidentally charged twice for your
   subscription this month. I have located your account (CUST-001) and reviewed
   your recent transaction history. According to our refund policy, eligible
   refunds are fully processed within 5–10 business days. I have initiated the
   review for your duplicate charge..."
```

Notable points:
- The reply **names the customer** — that comes from the `get_customer_info`
  CRM tool call, not from the model hallucinating.
- The classifier judged the ticket a refund at 0.95 confidence, so the
  parallel specialist fan-out was **skipped** entirely (~60% request-cost saving).
- The critic approved the draft on the **first iteration**; no rewrite loop needed.

---

## Project Structure

```
adk-cx-support-orchestrator/
├── src/adk_cx_support_orchestrator/
│   ├── __init__.py              # Package metadata
│   ├── agent.py                 # root_agent (ADK entry point)
│   ├── server.py                # FastAPI server for Cloud Run
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Environment-sourced settings
│   │   ├── types.py             # Pydantic models & enums
│   │   └── exceptions.py        # Exception hierarchy
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── intake.py            # SequentialAgent: extract + classify
│   │   ├── specialists.py       # 3 specialist agents for fan-out
│   │   ├── draft.py             # Draft response generator
│   │   ├── critic.py            # Quality-assurance critic
│   │   └── orchestrator.py      # Full orchestration graph
│   ├── tools/
│   │   ├── __init__.py
│   │   └── crm_tools.py         # FunctionTool wrappers for KB + CRM
│   └── mcp_server/
│       ├── __init__.py
│       └── server.py            # Mock MCP server (JSON-RPC 2.0 / stdio)
├── evals/
│   ├── eval_dataset.json        # 25 sample tickets with expected outputs
│   ├── test_config.json         # ADK evaluation criteria + rubrics
│   └── run_eval.py              # Evaluation runner + mock report
├── infra/
│   └── cloud_run.yaml           # Cloud Run service manifest
├── .github/workflows/
│   └── deploy.yml               # CI: lint → test → build → deploy
├── Dockerfile                   # Production container image
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.10+
- A Google API key (for Gemini) — get one at [Google AI Studio](https://aistudio.google.com/apikey)
- (Optional) Docker & gcloud CLI for deployment

### Install

```bash
# Clone the repo
git clone https://github.com/your-org/adk-cx-support-orchestrator.git
cd adk-cx-support-orchestrator

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env and set your GOOGLE_API_KEY
```

### Run Locally

```bash
# Option 1: ADK web UI (requires `adk` CLI)
adk web src/adk_cx_support_orchestrator

# Option 2: FastAPI server
python -m adk_cx_support_orchestrator.server
# → http://localhost:8080

# Test it
curl -X POST http://localhost:8080/triage \
  -H "Content-Type: application/json" \
  -d '{"ticket_id": "T-001", "text": "I was charged twice this month", "customer_id": "CUST-001"}'
```

### Run MCP Server Standalone

```bash
# The MCP server communicates via JSON-RPC 2.0 over stdio
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | \
  python src/adk_cx_support_orchestrator/mcp_server/server.py
```

---

## Testing

### Option A: Unit tests (no API key, offline)

```bash
pip install "google-adk>=2.0.0" pytest

# 16 tests covering MCP server, KB/CRM tools, JSON parsing, routing models
python -m pytest tests/ -v
```

### Option B: Mock evaluation (no API key)

```bash
# Generates a mock eval report with representative metrics for CI/demo
python -m evals.run_eval --mock
```

### Option C: Live end-to-end test (requires GOOGLE_API_KEY)

```bash
# Run the default samples (billing, technical, ambiguous)
python scripts/test_live.py

# Run specific samples
python scripts/test_live.py billing refund edge

# Run everything
python scripts/test_live.py --all
```

Each sample runs the FULL pipeline and prints the final grounded response.

> **Rate limits:** Free-tier Gemini keys are limited (~5-15 req/min). One ticket
> consumes ~6-12 requests. Space runs out or use the paid tier.

### Option D: Force the Parallel Fan-out path

By default, the fan-out only triggers when classification confidence is below
`AMBIGUITY_THRESHOLD` (0.6). To force the fan-out and verify the gather logic:

```bash
AMBIGUITY_THRESHOLD=0.99 python scripts/test_live.py billing
# → log shows: "ambiguous ticket — fanning out to specialists"
# → gather:    "Specialist scores: {...}. Winner: <category> (<score>)"
```

## Evaluation

### Run Mock Evaluation (No API Key Required)

```bash
python -m evals.run_eval --mock
```

### Run Full Evaluation (Requires API Key)

```bash
# Install eval dependencies
pip install 'google-adk[eval]'

# Run evaluation via Python
python -m evals.run_eval

# Or via ADK CLI
adk eval src/adk_cx_support_orchestrator evals/eval_dataset.json \
  --config_file_path=evals/test_config.json \
  --print_detailed_results
```

### Mock Evaluation Report

Running `--mock` produces a report like this:

```
============================================================
  CX Support Triage — Evaluation Report
============================================================
  Total tickets evaluated : 25
  Correct routes         : 23/25
  Routing precision      : 92%
  Routing recall         : 92%
  Tool-call accuracy     : 88%
  Avg loop count         : 1.4

  Rubric Scores:
    tone                      94%
    accuracy                  90%
    policy_compliance         96%
    grounding                 88%

  Loop Convergence:
    passed_iter_1             14
    passed_iter_2             7
    passed_iter_3             2
    hit_limit                 2
============================================================
```

Reports are saved to `evals/eval_report.json`.

---

## Deployment

### Deploy to Cloud Run (Recommended)

```bash
# Option A: Using gcloud directly
gcloud run deploy cx-support-orchestrator \
  --source . \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --allow-unauthenticated

# Option B: Using ADK's built-in deploy
adk deploy cloud_run \
  --project=YOUR_PROJECT_ID \
  --region=us-central1 \
  --service_name=cx-support-orchestrator \
  src/adk_cx_support_orchestrator
```

### Deploy to Vertex AI Agent Engine

```bash
adk deploy agent_engine \
  --project=YOUR_PROJECT_ID \
  --region=us-central1 \
  --display_name "CX Support Orchestrator" \
  --staging_bucket gs://YOUR_BUCKET \
  --requirements_file requirements.txt \
  src/adk_cx_support_orchestrator
```

### CI/CD

The GitHub Actions workflow (`.github/workflows/deploy.yml`) runs on push to `main`:

1. **Lint** — ruff check + format + mypy
2. **Test** — mock evaluation run
3. **Deploy** — build Docker image → push to GCR → deploy to Cloud Run

Required GitHub secrets:
- `GCP_PROJECT_ID` — your Google Cloud project ID
- `GCP_SA_KEY` — service account JSON key with Cloud Run deploy permissions

---

## Trade-offs and Decisions

### Deterministic Routing vs. Pure LLM Reasoning

| Decision | Rationale |
|---|---|
| **Deterministic `BaseAgent` for routing, gathering, and assembly** | Parsing JSON from LLM output, comparing confidence scores, and assembling final text are **logic-heavy, low-creativity tasks**. Using `BaseAgent` (no LLM call) saves latency and cost, eliminates hallucination risk for these steps, and makes behavior fully reproducible. |
| **LLM agents for classification, specialist scoring, and drafting** | These tasks require **natural language understanding** — interpreting nuanced customer intent, generating empathetic responses, and reasoning about policy applicability. LLMs excel here where deterministic rules would be brittle. |
| **LoopAgent with explicit `max_iterations`** | The draft/critic loop gives the model a chance to self-correct, but we cap it at 3 iterations to **bound latency and cost**. The `LoopTerminator` (a `BaseAgent`) provides deterministic control over when the loop exits, avoiding reliance on the LLM to "decide" to stop. |
| **Key-collision avoidance in ParallelAgent** | Each specialist writes to a **unique `output_key`** (`billing_score`, `technical_score`, `refund_score`). ADK's `ParallelAgent` runs sub-agents concurrently; shared keys would cause race conditions. The `Gatherer` agent then deterministically merges these into a single routing decision. |
| **Fan-out is gated by a deterministic check** | The `ConditionalSpecialistFanOut` `BaseAgent` inspects `is_ambiguous` in session state and **only invokes the parallel specialists when the classification confidence is low**. For confident tickets it skips the fan-out entirely — saving 3 LLM calls (~60% request cost) per ticket and avoiding wasted quota. |

### Model Selection

The model is fully configurable via `ADK_MODEL`. All agents default to
`gemini-3.5-flash-lite`, chosen because:
- It is the current entry-tier Flash model exposed by the Google AI Gemini API
  (older `gemini-2.5-flash*` models were retired for new users as of late 2026).
- Flash-Lite models carry a **higher free-tier rate limit**, which matters
  during evaluation and CI — one full triage consumes ~6-12 model requests.
- For higher-fidelity drafting, set `ADK_MODEL=gemini-3.5-flash` or a Pro model
  in your `.env` / Cloud Run env vars.

### MCP Integration

The mock MCP server runs as a **stdio subprocess** (the standard MCP transport). ADK's `McpToolset` handles protocol negotiation, tool discovery, and tool invocation automatically. The same knowledge-base and CRM functions are also exposed as plain **FunctionTools** for use by sub-agents that don't need full MCP — this avoids spawning multiple MCP server processes.

### Evaluation Strategy

- **25 test tickets** covering all 4 categories + ambiguous + edge cases
- **Tool trajectory scoring** ensures agents call the right tools with correct arguments
- **Rubric-based quality** (tone, accuracy, policy compliance, grounding) catches soft failures that metric-only evals miss
- **Mock evaluation mode** enables CI runs without requiring a live API key

### Why ADK Over Rolling Our Own

- **Pattern primitives** (`SequentialAgent`, `ParallelAgent`, `LoopAgent`) enforce clean composition without hand-rolling orchestration logic
- **Session state** acts as a shared whiteboard between agents — no custom message-passing or state-management code
- **Built-in evaluation** with tool-trajectory and rubric-based metrics is far more rigorous than ad-hoc testing
- **MCP integration** is first-class, not a bolt-on
- **Deployment** to Cloud Run / Agent Engine is one command

### What We'd Change in Production

1. **Persistent session store** — swap `InMemorySessionService` for `DatabaseSessionService` (PostgreSQL) or Vertex AI sessions
2. **Real MCP server** — replace the mock with a live KB (e.g., Algolia, Pinecone) and CRM (e.g., Salesforce, HubSpot) MCP server
3. **Streaming responses** — use ADK's event streaming to push partial responses to the client
4. **A2A protocol** — expose the orchestrator as an A2A server for cross-system agent collaboration
5. **Caching** — cache KB lookups and CRM responses to reduce MCP round-trips for repeat queries

---

## License

Apache 2.0
