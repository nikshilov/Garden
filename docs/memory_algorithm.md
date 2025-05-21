# Emotional Memory Algorithm – MVP

> **Goal:** give each character a lightweight, interpretable memory system that influences future replies, supports forgiveness, and remains bounded in size/cost.

## Memory Record Structure
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `characterId` | UUID | Owner character |
| `eventText` | String | Short natural-language summary (≤120 tokens) |
| `weight` | Float (0–1) | Importance / emotional intensity |
| `sentiment` | Int (–2..+2) | –2 = very negative, 0 neutral, +2 very positive |
| `createdAt` | Date | Timestamp |
| `lastTouched` | Date | For decay algorithm |

## Weight Rules
```
Initial weight  w0  =  clamp(  |sentiment|  * 0.3 + userFlag , 0.1 .. 1.0 )
userFlag = 0.4  if user manually “pin memory”, else 0
```

### Decay
```
Effective weight  w(t) = w0 * exp( -λ * Δdays )
λ = 0.05  (≈ half-life 13.9 days)
```
Memory with `w(t) < 0.05` is archived (not used in prompt) but kept for export.

### Forgiveness / Amplification
When a new event E′ arrives with opposite sentiment to existing memory M:
```
if  sign(sentiment_E′) != sign(sentiment_M):
    Δ = |sentiment_E′| * 0.2
    weight_M = max( weight_M - Δ , 0 )   # forgiveness
else:
    weight_M = min( weight_M + Δ , 1 )   # reinforcement
```

## Prompt Assembly (CharacterNode)
1. Select top-`K` memories by `w(t)` where `sentiment ≠ 0`. (`K=3` for MVP.)
2. Format template:
```
Relevant memories:
• [user insulted me once, I felt hurt] (w=0.6)
• [user brought me a joke, I felt happy] (w=0.4)
```
3. Append to character prompt before sending to LLM.

## Reflection Trigger
After each reply batch:
1. Pass last user + character messages to SentimentClassifier (tiny on-device).  
2. If |sentiment| ≥1  **and** message length ≥20 chars → create **or update** a Memory Record.
3. Also create memory for explicit `#remember` user command.
4. **Re-weighting:** `ReflectionEngine` sends the new event **plus the character’s top-K memories** to the character’s own LLM. The model may return JSON directives like `[ {"id":"…","newWeight":0.85} ]`. `MemoryManager` applies these updates and sets `lastTouched = now`.

## Storage Limits
* Max 200 active memories per character.
* Archive table can grow unlimited; purged on export if user selects.

## Pseudocode
```swift
func storeMemory(event: String, sentiment: Int, charID: UUID) {
    let w0 = max(0.1, min(1.0, abs(Double(sentiment)) * 0.3 ))
    let record = Memory(id: UUID(), characterId: charID,
                        eventText: event, weight: w0,
                        sentiment: sentiment, createdAt: .now, lastTouched: .now)
    context.insert(record)
    enforceCap(for: charID)
}

func decayWeights() {
    for m in fetchActiveMemories() {
        let days = Date().timeIntervalSince(m.lastTouched) / 86_400
        m.weight = m.weight * exp(-0.05 * days)
        if m.weight < 0.05 { m.isArchived = true }
    }
    save()
}

func reflectAndReweight(charID: UUID, context: String) async throws {
    let memories = topKMemories(for: charID, k: 3)
    let prompt = ReflectionPrompt(context: context, memories: memories)
    let (json, usage) = try await characterLLM.send(prompt)
    try await CostTracker.shared.record(model: characterLLM.id, usage: usage)
    let updates = try JSONDecoder().decode([MemoryUpdate].self, from: Data(json.utf8))
    for u in updates {
        if let m = fetchMemory(id: u.id) {
            m.weight = clamp(u.newWeight, 0, 1)
            m.lastTouched = .now
        }
    }
    try context.save()
}
```

---
*(Last updated: 2025-05-21)*
