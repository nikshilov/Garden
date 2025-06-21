# 🌤️ Daily Mood System

Garden characters wake up each (simulated) day with a lightweight random **mood vector**.  
It biases their replies, the chance to remember an event, and how strongly relationships change.

---
## 1. Model

| Axis (subset of Plutchik + VAD) |
| --- |
| joy, trust, fear, surprise, sadness, disgust, anger, anticipation |
| valence, arousal, dominance |
| flirt, playfulness, shadow |

Range: **−0.4 … +0.4** (moderate).  The vector decays with a 12-hour half-life.

---
## 2. Lifecycle

1. On the first run of a calendar day the engine:
   * loads previous `data/mood_states.json` if same date ⇒ re-use;
   * else calls `mood.generate_mood()` which adds Gaussian noise ±0.25 with a small bias to yesterday’s valence.
2. Result is persisted and **logged** in `data/mood_log.csv`.
3. Each saved memory nudges the vector by `+0.05·emotions`.

---
## 3. Influence

| Place | Formula |
| ----- | -------- |
| Memory importance weight | `× (1 + 0.25·valence + 0.15·flirt − 0.20·shadow)` |
| Relationship delta | `× (1 + 0.2·arousal)`<br/>negative deltas further × `(1 + 0.3·shadow)`
| Prompt prefix | `Today you feel _slightly_ angry.` |

---
## 4. CLI helpers

```
# Reset cached moods – force fresh generation on next run
garden chat --reset-mood

# Show last 15 mood entries and exit
garden chat --show-mood-log
```

---
_Last updated: 2025-06-18_
