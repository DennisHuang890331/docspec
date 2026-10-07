## ADDED Requirements

### Requirement: Background basis does not determine completion
The roadmap SHALL treat governance decisions and information as traceable background, while deriving completion from existing deliverables, child work or explicit closure and reporting structural failures.

#### Scenario: Archived work retains information references
- **WHEN** all linked deliverables are complete and valid information remains referenced
- **THEN** the work is complete without removing the information, while its authority and review warnings remain visible

#### Scenario: Background-only work or invalid source
- **WHEN** work has only background references without explicit closure, or required sources are missing or damaged
- **THEN** the query does not present unsupported completion and identifies the reason

### Requirement: Explicit consistent document query context
Content inspection commands SHALL default to official data and use the specified active document change as a read-only union when --change is supplied.

#### Scenario: Draft source differs from official data
- **WHEN** get, instructions, find, check or diff is called with a document change
- **THEN** the command uses the same staged records and identifies context and sources without modifying managed files or rendering

#### Scenario: Missing or outdated preview
- **WHEN** a query needs preview prose that has not been generated or no longer matches its source
- **THEN** it reports the unavailable or outdated preview rather than silently inspecting official prose or declaring a clean draft

#### Scenario: Structural checking remains global
- **WHEN** check is scoped to an article inside a change
- **THEN** structural failures anywhere in the effective project remain reported and software issues remain separately identified

### Requirement: Compact versioned work summary
The work summary SHALL default to schema version 2, preserve necessary judgments and governance content, and replace repeated signed contracts with fingerprints and original-source lookup information.

#### Scenario: Historical scopes share or differ in fingerprint
- **WHEN** signed historical scopes appear repeatedly
- **THEN** equal fingerprints share their source entry and different fingerprints remain distinct without modifying evidence

#### Scenario: Explicit version 1 output
- **WHEN** a caller requests schema version 1
- **THEN** the original summary structure remains available from the same underlying judgments

### Requirement: Workflow instructions identify draft and delivery boundaries
Generated rules and edited skills SHALL explicitly pass the current change identity and distinguish immutable historical versions, current projections and time-sensitive work state.

#### Scenario: Refresh existing instructions
- **WHEN** built-in instruction versions have increased and an existing project refreshes them
- **THEN** it receives the approved guidance while user content and stored historical records remain intact
