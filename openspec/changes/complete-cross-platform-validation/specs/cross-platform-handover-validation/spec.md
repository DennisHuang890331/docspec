## ADDED Requirements

### Requirement: Genuine platform evidence
Validation SHALL report Windows and Linux regression and PDF/proof outcomes separately using pinned user-level tooling without weakening tests.

#### Scenario: Missing or failed environment
- **WHEN** a tool download or runtime setup fails
- **THEN** it is recorded as an environment failure and never counted as a passing execution

### Requirement: Fresh handover validation
Each platform SHALL run independent fresh normal and stale handovers with the same task, external facts and pre-run managed-content fingerprints.

#### Scenario: Key facts and boundaries
- **WHEN** the successor inspects its existing work via roadmap summary
- **THEN** effective decisions, signoffs, evidence and document freeze facts are available and the successor reuses work before rewriting handover

#### Scenario: Independent review
- **WHEN** a handover finishes
- **THEN** an independent review checks each predefined fact and changed file, distinguishes tool, environment and agent errors, and records query/source navigation observations without claiming a controlled comparison

### Requirement: Manual agent evaluation
Fresh-agent validation SHALL be manually initiated for workflow changes or before release; CI runs mechanical regressions only.

#### Scenario: CI validation
- **WHEN** CI executes the test matrix
- **THEN** it does not silently initiate agent conversations
