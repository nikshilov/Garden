# Emotional Memory & Relationships (P2 Memory Core)

This document records the semantic emotional memory system and multidimensional relationship model introduced in **P2 Memory Core**.

---

## 1. MemoryRecord schema
```jsonc
{
  "id": "uuid",
  "character_id": "eve",
  "event_text": "summary (<=500 chars)",
  "weight": 0.742,
  "sentiment": 2,               // legacy int
  "sentiment_label": "affection",
  "created_at": "ISO 8601",
  "last_touched": "ISO 8601",
  "archived": false,
  "emotions": {
    "joy": 0.6, "trust": 0.5, "fear": 0.0, "surprise": 0.1,
    "sadness": 0.0, "disgust": 0.0, "anger": 0.0, "anticipation": 0.3,
    "valence": 0.5, "arousal": 0.4, "dominance": 0.2
  }
}
```
* `emotions` is an **11-D vector**: Plutchik’s 8 emotions + Valence/Arousal/Dominance.

---

## 2. Relationship profile
Stored in `garden_graph/data/relationships.json`:

| Axis | Meaning |
|------|---------|
| affection | warmth / liking |
| trust | reliability |
| respect | esteem |
| familiarity | knowledge & comfort |
| tension | stress / conflict |
| empathy | share feelings |
| engagement | interest |
| security | sense of safety |
| autonomy | respect independence |
| admiration | elevated respect & awe |

`__meta__.last_decay` records when passive decay last ran.

---

## 3. Update algorithm
1. Map emotion → axis deltas via `EMOTION_AXIS_WEIGHTS`.
2. Scale by message significance and personal factor.
3. Clamp to −1…+1.

---

## 4. Passive daily decay
```
new = old * (1 − RELATIONSHIP_DECAY × hours / 24)
# RELATIONSHIP_DECAY = 0.0005  (~0.05 % per day)
```

---

## 5. CLI debug
With `DEBUG_MEMORY=true` the CLI prints:
* last 3 memories with valence & top-3 emotions
* top-3 relationship axes by magnitude

---

## 6. Migration notes
* Scalar relationship values auto-wrapped into `{ "affection": value }`.
* `sentiment` int kept for backward compatibility.
