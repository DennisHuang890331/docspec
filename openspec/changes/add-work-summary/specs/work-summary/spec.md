## ADDED Requirements

### Requirement: Read-only work summary
The system SHALL provide `docspec roadmap show <id>` and `--json` using a shared versioned result without running commands or changing managed records.

#### Scenario: Incomplete work is inspectable
- **WHEN** a linked work item has unsigned tests or failing evidence
- **THEN** the query succeeds and identifies every relevant test, task, evidence and reason with source entries

#### Scenario: Corrupt or absent work
- **WHEN** the requested work is absent or managed data cannot be read reliably
- **THEN** the query reports an error rather than claiming completion

### Requirement: Explicit relationship scope
The summary SHALL follow recorded refs, children, prerequisites and necessary sources, deduplicate sources, preserve original references and show explicit successors with their effective decision content.

#### Scenario: Superseded decision
- **WHEN** a linked decision is explicitly superseded
- **THEN** the original reference, current successor and related review flags are shown without changing any reference or granting authority

#### Scenario: Incomplete relationship data
- **WHEN** links are missing or dependencies form a cycle
- **THEN** the summary diagnoses the missing coverage or cycle and missing sources or cycles cannot be reported as completed

### Requirement: Shared completion and fixed advice
The system SHALL reuse existing completion, signoff, evidence and document judgments and give fixed-rule optional next actions.

#### Scenario: Independent document completion
- **WHEN** a linked document is written but unfrozen or has a software divergence
- **THEN** its writing, sync and current freeze states are displayed separately and software divergence does not become a document freeze blocker

#### Scenario: Role and owner boundaries
- **WHEN** tests need review and a document is unfrozen
- **THEN** advice names the test role's review obligation and the owner's explicit freeze authority without taking those actions
