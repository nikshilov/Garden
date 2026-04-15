# Test Plan – MVP

> Ensure core quality for multi-agent world chat before TestFlight release.

## 1. Unit Tests (XCTest)
| Module | Key Tests |
|--------|-----------|
| **RouterNode** | Predicts correct character IDs for simple queries; respects "@name" override; returns ≤2 IDs. |
| **MemoryManager** | Stores memory record; decay halves weight after 14 days; forgiveness reduces weight; archive threshold works. |
| **ReflectionEngine** | Generates JSON re-weight directives; applies updates; ignores malformed JSON. |
| **CostTracker** | Computes USD with mock pricing; triggers budget alert when exceeding limit. |
| **SentimentClassifier** | Accuracy ≥80% on labeled test set. |
| **Import/Export** | Character JSON round-trips without loss; signature validation fails on tamper. |

## 2. Integration Tests
Scenario | Expected
---------|----------
User sends text → Eve replies only (router) | UI shows 1 reply, token cost logged.
User insults Eve → Eve’s tone negative next message | Memory weight rises >0.5.
Image added → characters reference Vision tag | Message contains tag keyword.
Background task fires after 1h offline | Push notification delivered.

## 3. UI Tests (XCUITest)
* Launch → onboarding sets API key → chat screen appears.
* Long-press message → CharacterSheet opens.
* Slider changes budget limit → CostDashboard reflects new value.
* Dark Mode & Dynamic Type snapshots match baseline.

## 4. Performance / Load
Metric | Target | Tool
------ | ------ | ----
Cold start time | <2.5 s | Xcode Instruments
Memory on idle chat | <250 MB | Xcode Memory Gauge
On-device router latency | <200 ms avg | Custom trace
Concurrent character replies (2) | <3 s total | XCTestMeasure

## 5. Security / Compliance Checks
* Keychain items not synced to iCloud.
* No PII leaves device without user opt-in.
* Encryption at rest verified for Core Data store.
* Static analysis via Xcode & SwiftLint passes.

## 6. Regression Suite
Executed before each TestFlight build:
```
fastlane test             # unit + UI tests
fastlane run_lints        # SwiftLint
fastlane run_snapshots    # visual regressions
```

## 7. Acceptance Criteria
* All unit & integration tests pass (≥95% coverage critical path).
* Performance targets met on iPhone 13.
* Zero high-severity bugs open.

---
*(Last updated: 2025-05-21)*
