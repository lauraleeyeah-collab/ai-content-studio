# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run app.py

# Run offline tests (no API key required)
python -m tests.test_pipeline_mock

# Run demo-mode end-to-end tests (covers all 8 agents)
XHS_DEMO_MODE=1 python -m tests.test_demo_mode

# Run from the repository root
cd /path/to/ai-content-studio
streamlit run app.py

# Run the app in demo mode (no API key needed, for interviews/offline demo)
XHS_DEMO_MODE=1 streamlit run app.py
```

## Demo Mode

`utils/demo_data.py` provides built-in sample data for every agent call. When demo mode is
active (`XHS_DEMO_MODE=1` env var, or the "演示模式" toggle in any page sidebar),
`utils/llm_client.py` short-circuits all LLM calls and returns realistic sample outputs.
Deterministic post-processing (scoring, sorting, ratio checks, grading) still runs for real,
so the full pipeline can be demonstrated without an API key.

To add a new demo response: add the payload to `utils/demo_data.py` and register a
`(system_prompt_keyword, payload)` pair in `_ROUTES`.

## Architecture Overview

This is a 5-agent pipeline for Xiaohongshu (Little Red Book) viral content analysis and generation. The key design principle: **LLM handles judgment, Python handles computation**.

### The 5-Agent Pipeline

```
User pastes raw note content
   ↓
Agent0 (trend_collector) — Parse unstructured text into standardized fields
   ↓
Agent1 (trend_filter) — 5-dimension scoring, Python computes total_score, sorts, detects batch warnings
   ↓
Agent2 (viral_analyzer) — Deconstruct title formulas, content structure, emotion hooks, interaction patterns
   ↓
Agent3 (topic_generator) — Derive inspiration + persona adaptation + deduplication, Python validates content format ratio
   ↓
Agent4 (copywriter) — Generate text/video copy based on style_guide
```

**Critical design decision in Agent1**: Model only provides subjective 5-dimension scores (0-10 each). Python code deterministically:
- Computes `total_score` (normalized to 50-point scale)
- Sorts results by `total_score` descending, with tiebreakers (relevance, engagement)
- Triggers `batch_warning` when all scores fall below `LOW_SCORE_THRESHOLD` (25)
- Downgrades `scoring_confidence` based on missing dimensions

This avoids LLM doing arithmetic/sorting, which is unreliable.

### Model Configuration

- **Text model**: `qwen-plus` (via DashScope OpenAI-compatible API)
- **Vision model**: `qwen-vl-plus` (for image extraction)
- Temperature strategy in `config.py`:
  - Scoring/filtering/analysis agents: 0.15-0.35 (stability)
  - Topic/copywriting agents: 0.7-0.8 (creativity)

### Key Modules

**`utils/llm_client.py`** — Central LLM abstraction with:
- Lazy loading (only imports `openai` when first called)
- `call_llm()` — returns raw text
- `call_llm_json()` — returns parsed JSON with retry logic
- `call_llm_with_images()` / `call_llm_with_images_json()` — vision model calls
- `extract_json()` — robust JSON extraction (handles ```json```, partial matches)

**`utils/prompt_utils.py`** — Template rendering:
- Uses `{{variable}}` double-brace syntax
- Avoids conflict with JSON examples in prompts (which use `{}`)
- Raises `KeyError` if required variable is missing

**`agents/trend_filter.py`** — Reference implementation of "LLM judges, Python computes" pattern.

**`database/`** — SQLite with tables: `trends`, `selected_topics`, `generated_copy`, `note_analyses`, `competitor_accounts`, `account_notes`, `account_analyses`, `trend_snapshots`, `title_optimizations`, `hashtag_recommendations`.

**`style_samples/style_guide_v2.md`** — Style reference for copywriter agent (iterative, not hardcoded in code).

**`pages/`** — Streamlit multi-page structure:
- `1_热点选题流水线.py` — Main 5-agent pipeline
- `2_笔记爆款分析.py` — 7-dimension scoring with radar chart
- `3_竞品账号分析.py` — Competitor account deep-dive
- `4_热门内容趋势.py` — Trend analysis with co-occurrence graphs
- `5_内容创作辅助.py` — Title optimization, A/B testing, hashtag recommendation
- `6_历史记录管理.py` — History viewer/deleter for all modules

## Testing

**Offline tests** (mock-based, no API key needed):
- Test deterministic logic: Agent1 scoring/sorting, Agent3 format ratio validation
- Run with: `python -m tests.test_pipeline_mock`
- Pattern: `mock.patch("agents.trend_filter.call_llm_json", return_value=fake_data)`

**Test what matters**: Code paths that are deterministic (scoring, sorting, ratio checks). LLM behavior can't be tested offline.

## Important Patterns

### Agent Function Signature
Most agents follow this pattern:
```python
def agent_name(track: str, [other inputs...]) -> dict:
    user_prompt = render(PROMPT_TEMPLATE, track=track, ...)
    result = call_llm_json(SYSTEM_PROMPT, user_prompt, temperature=TEMPERATURE_CONFIG["agent_name"])
    # Post-process (Python code adds derived fields)
    return result
```

### JSON Output from LLM
Prompts should explicitly require JSON output. `call_llm_json()` handles:
- Parsing bare JSON
- Extracting from ```json``` code blocks
- Regex-based extraction for malformed output
- Auto-retry with correction instruction

### Vision Model Usage
`call_llm_with_images_json()` accepts:
- `{"type": "base64", "data": "...", "mime": "image/png"}`
- `{"type": "url", "url": "https://..."}`
- Plain base64 strings (assumes PNG)

Base64 should NOT include `data:image/...;base64,` prefix — the client adds it.

### Session State Pattern
Streamlit pages use `st.session_state` to persist pipeline state between interactions:
```python
if "pipeline" not in st.session_state:
    st.session_state.pipeline = {}
# Store intermediate results
st.session_state.pipeline["trends"] = filtered_results
```

## Known Limitations

- Agent0 requires manual copy-paste from Xiaohongshu app (no public API for trending data)
- `style_guide_v2.md` is iterative — needs calibration with real feedback
- Database persistence exists, but UI for history management is incomplete
- Screenshot paste (Cmd+V) has iframe focus/data-passing issues (see `memory/streamlit-paste-debug-session.md`)

## Environment Variables

- `DASHSCOPE_API_KEY` — DashScope API key (can also be entered in sidebar)
- `QWEN_MODEL_NAME` — Override default `qwen-plus`
- `QWEN_VISION_MODEL_NAME` — Override default `qwen-vl-plus`
- `XHS_AGENT_DB_PATH` — Override default `database/xhs_agent.db`
- `XHS_DEMO_MODE` — Set to `1` to enable demo mode (no API key needed)
