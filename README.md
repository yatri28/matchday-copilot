# MatchDay Copilot ⚽

A GenAI-powered matchday assistant for **fans at FIFA World Cup 2026 venues** — in-stadium navigation, live crowd intelligence, multilingual help, and accessibility-first routing, all in one lightweight web app.

Built for **PromptWars — [Challenge 4] Smart Stadiums & Tournament Operations**.

---

## 1. Chosen Vertical

**Fans** (with accessibility treated as a first-class requirement, not an afterthought).

Of the challenge's focus areas, this solution directly addresses four:

| Focus area | How MatchDay Copilot delivers it |
|---|---|
| **Navigation** | Graph-based in-stadium wayfinding (gates → concourses → sections → facilities) with shortest-path routing |
| **Multilingual assistance** | Fans ask questions in 7 languages (EN/ES/FR/AR/PT/DE/HI); answers come back in their language |
| **Accessibility** | A "step-free routes" mode that guarantees wheelchair users are never routed through stairs-only areas; sensory room and accessible restrooms are mapped; the UI itself is WCAG-minded (ARIA live regions, skip link, keyboard focus, reduced-motion support) |
| **Real-time decision support** | A live crowd board per zone with congestion levels and a "fastest gate right now" advisory the assistant folds into its answers |

## 2. Approach & Logic

### Architecture

```
Browser (single-page UI)
      │  JSON over HTTPS
      ▼
FastAPI backend
 ├── /api/venues      venue maps (nodes + edges + accessibility flags)
 ├── /api/matches     fixture context
 ├── /api/crowd/{id}  live-style crowd densities + advisory
 ├── /api/navigate    Dijkstra shortest path, optional step-free constraint
 └── /api/ask         the assistant (GenAI tier → offline tier)
            │
            ├── GenAI tier: Anthropic Claude, grounded in a context pack
            │   built from live services (venue map, crowd snapshot, fixtures)
            └── Offline tier: rule-based intent router over the SAME services
```

### The two-tier GenAI design (the core idea)

1. **GenAI tier** — when `ANTHROPIC_API_KEY` is set, every fan question is answered by Claude. Crucially, the model is **grounded**: the prompt injects a context pack assembled at request time (venue facilities, live crowd levels, today's fixtures) and instructs the model to answer *only* from that context, in the fan's language, and to defer to stewards when the context can't answer — so it never invents gate numbers or kickoff times.
2. **Offline tier** — with no API key, a deterministic intent router (route parsing, crowd, food, restrooms, first aid, transport, accessibility, fixtures) answers from the exact same services with localized templates. Every response discloses its `source` (`genai` or `offline_assistant`), so the system is honest about which tier answered.

This means the app **degrades gracefully**: it is fully demoable, testable, and useful with zero external connectivity, and gets smarter when GenAI is enabled.

### How Gen AI was used to build this

The project was built end-to-end through AI-assisted development (prompting → code → tests → iteration), and Generative AI is embedded in the product itself as the conversational tier described above — satisfying the challenge's mandatory Gen AI requirement on both fronts.

## 3. How the Solution Works (Running It)

```bash
# 1. Install
pip install -r requirements.txt

# 2. (Optional) enable the GenAI tier
cp .env.example .env   # add your ANTHROPIC_API_KEY, then export it
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Run
uvicorn app.main:app --reload

# 4. Open
#    http://127.0.0.1:8000        ← fan UI
#    http://127.0.0.1:8000/docs   ← interactive API docs (OpenAPI)
```

Try in the UI:
- *"How do I get from Gate A to Section 115?"*
- *"Which gate has the shortest queue?"* (uses the live crowd feed)
- Toggle **Step-free routes**, then ask for the nearest restroom
- Switch language to **Español** and ask *"¿dónde puedo comer?"*

### Tests

```bash
python -m pytest -q     # 21 tests: unit (navigation, crowd) + API integration
```

Tests cover shortest-path correctness, step-free constraint enforcement, crowd determinism and bounds, input validation (length caps, ID pattern injection attempts, unknown-field rejection), multilingual answers, accessibility routing, and rate limiting.

## 4. Evaluation-Criteria Mapping

- **Code Quality** — small typed modules with single responsibilities, docstrings explaining *why*, Pydantic schemas, no dead code.
- **Security** — no secrets in the repo (env-only config), strict input validation (`extra="forbid"`, regex-constrained IDs, length caps), per-IP rate limiting, security headers (CSP, `X-Frame-Options`, `nosniff`), generic 500s that never leak internals, and a grounded LLM prompt that refuses to fabricate.
- **Efficiency** — venue data cached with `lru_cache`, Dijkstra on tiny graphs (µs-scale), deterministic crowd simulation (no polling of external services), 4-dependency footprint, repo well under 10 MB.
- **Testing** — 21 automated tests across three suites, runnable offline with zero configuration.
- **Accessibility** — step-free routing engine, accessible-facility data model, and an interface with skip links, ARIA live regions, visible focus states, semantic HTML, and `prefers-reduced-motion` support.
- **Problem Statement Alignment** — see the vertical table above; every feature maps to a named focus area for FIFA World Cup 2026 stadium operations.

## 5. Assumptions Made

- **Venue maps** for MetLife Stadium and Estadio Azteca are simplified representative graphs (real deployments would ingest official venue CAD/BIM data). Edge weights approximate walking minutes.
- **Crowd data is a deterministic simulation** (hash of venue/zone/5-minute window). It stands in for real telemetry (turnstiles, CCTV analytics, Wi-Fi probes) behind the same interface, so swapping in a real feed changes one module.
- **Fixtures** are sample data for demo purposes.
- The offline tier's language coverage uses curated templates; free-form multilingual conversation is delegated to the GenAI tier.
- Single-process deployment is assumed (in-memory rate limiting); a production rollout would move that to a shared store.

## Project Structure

```
app/
  main.py            FastAPI app, middleware, routes
  config.py          env-driven settings (no secrets in code)
  models.py          request/response schemas + validation
  services/
    navigation.py    venue graphs + Dijkstra + step-free routing
    crowd.py         crowd densities, levels, gate advisory
    assistant.py     GenAI orchestration + offline intent router
    i18n.py          language registry + localized templates
  data/              venue maps + fixtures (JSON)
  static/index.html  accessible single-page fan UI
tests/               21 automated tests
```

---

*MatchDay Copilot — built with Generative AI, for 104 matches, 16 stadiums, and millions of fans.*
