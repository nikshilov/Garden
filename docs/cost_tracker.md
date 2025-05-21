# Cost Tracker Specification – MVP

## Purpose
Provide transparent, real-time visibility into token usage and USD cost for every LLM request made by the app, enabling users to stay within budget and evaluate model trade-offs.

## Data Flow
```
CharacterNode / RouterNode ──► LLMWrapper.request(prompt)
                                      │
                                      ▼
                              CostTracker.intercept()
                                      │  (records)
                                      └──► Core Data → UI Dashboard
```

## Pricing Table (default values)
| Model | Context Price /1K tokens | Generation Price /1K tokens |
|-------|-------------------------|-----------------------------|
| phi-3-mini (local) | $0.00 | $0.00 |
| GPT-4.1-turbo | $0.01 | $0.03 |
| Sonet-3.7 | $0.008 | $0.024 |

*Values loaded from remote JSON so they can update without app release.*

## Core Data Entity `CostRecord`
Field | Type | Notes
------|------|------
`id` | UUID |
`modelId` | String | e.g., `gpt-4.1-turbo` |
`promptTokens` | Int |
`completionTokens` | Int |
`usd` | Float | Rounded to 1e-6 |
`createdAt` | Date |
`messageId` | UUID? | Optional link back to chat message |

## CostTracker API (Swift)
```swift
struct Usage {
    let prompt: Int
    let completion: Int
}

protocol LLMRequesting {
    func send(_ prompt: String) async throws -> (String, Usage)
}

class CostTracker {
    static let shared = CostTracker()
    private(set) var sessionUSD: Double = 0
    private let context = Persistence.shared.viewContext

    func record(model: String, usage: Usage) async {
        let price = Pricing.shared.price(for: model)
        let usd = (Double(usage.prompt)  / 1000.0) * price.prompt +
                  (Double(usage.completion) / 1000.0) * price.completion
        sessionUSD += usd
        await context.perform {
            let record = CostRecord(context: context)
            record.modelId = model
            record.promptTokens = Int32(usage.prompt)
            record.completionTokens = Int32(usage.completion)
            record.usd = usd
            record.createdAt = Date()
            try? context.save()
        }
        checkBudgetLimit()
    }

    private func checkBudgetLimit() {
        let limit = UserDefaults.standard.double(forKey: "monthlyBudgetUSD")
        guard limit > 0 else { return }
        if monthlySpend() > limit {
            pushAlert("Budget exceeded: $\(limit)")
        }
    }
}
```

## UI Integration
* CostChip under chat composer displays session token + USD.
* CostDashboard shows daily / monthly charts (Swift Charts).
* Settings → Budget Limit slider & reset stats button.

## Sync / Export
* CostRecords sync via CloudKit (private DB) alongside messages.
* Export chat bundles include per-message cost metadata.

## Privacy
* No usage data sent off-device unless CloudKit enabled.

---
*(Last updated: 2025-05-21)*
