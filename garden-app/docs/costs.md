# 💰 Cost Tracking

Garden records token usage and estimated USD cost for every LLM invocation so that you always know how much your conversations cost.

## 1. How It Works

The `CostTracker` class hooks into every model call and stores a `CostRecord` containing:

* model id (e.g. `gpt-4o`, `llama3-70b`)
* prompt / completion tokens
* calculated USD price (see `DEFAULT_PRICING` table)
* optional `category` label (e.g. `intimacy`)

The CLI prints a live session summary and a detailed breakdown when you exit.

```
Cost: $0.0123
  gpt-4o: $0.0067
  llama3-70b: $0.0056
  by category → general:0.0067$, intimacy:0.0056$
```

## 2. Categories

Garden currently uses two categories:

| Category  | Description                                  |
|-----------|----------------------------------------------|
| `general` | Normal chat, summarisation, supervisor, etc. |
| `intimacy`| Messages routed through `IntimateAgent`.      |

More categories can be added by passing `category="..."` to `CostTracker.record()`.

## 3. Configuration

| Env / Config                | Default | Description                                                  |
|-----------------------------|---------|--------------------------------------------------------------|
| `DISABLE_COST_TRACKING`     | `false` | Set to `true` to skip all cost recording.                    |
| `BUDGET_LIMIT`              | `1.0`   | USD budget per session – a warning prints if exceeded.       |
| `INTIMACY_MODEL`            | `llama3-70b` | Default model for Intimacy Mode (also in `config.yaml`). |

Example `.env` snippet:

```
BUDGET_LIMIT=5.0
DISABLE_COST_TRACKING=false
```

## 4. Exporting CSV

```python
tracker.export_csv("session_costs.csv")
```

Fields: `id, model, prompt_tokens, completion_tokens, usd, created_at, message_id, category`.

## 5. Updating Prices

Edit the `DEFAULT_PRICING` dict in `garden_graph/cost_tracker.py` whenever OpenAI / Groq adjusts their pricing.
