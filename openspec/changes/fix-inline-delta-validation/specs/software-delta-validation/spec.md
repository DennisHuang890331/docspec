## ADDED Requirements

### Requirement: Inline edits obey operation field restrictions
The engine SHALL apply existing delta operation field restrictions before editing an addition owned by the same change.

#### Scenario: Invalid scenario edit leaves sealed records unchanged
- **WHEN** an inline scenario edit supplies a removal reason or an unrelated requirement field
- **THEN** the command reports an invalid field before writing and the original managed bytes and integrity seal remain unchanged

#### Scenario: Invalid requirement edit leaves sealed records unchanged
- **WHEN** an inline requirement modification or rename supplies a field the operation does not accept
- **THEN** it is rejected before writing, consistently with modification of an existing baseline requirement

### Requirement: Valid inline edits preserve identity and existing verification semantics
The engine SHALL update only the operation's editable fields while preserving requirement and scenario identifiers and existing verification semantics.

#### Scenario: Metadata cannot overwrite assigned identifiers
- **WHEN** a valid inline edit also supplies an identifier or base metadata
- **THEN** the assigned identifier is preserved and the intended editable field is updated

#### Scenario: Semantic edit uses existing signoff and evidence rules
- **WHEN** a scenario WHEN or THEN changes
- **THEN** existing scope comparison makes affected signoff or evidence stale without changing the completion algorithm

#### Scenario: Title edit remains nonsemantic
- **WHEN** only a scenario title changes
- **THEN** its verification semantics remain unchanged and engine verification and archive continue using the existing rules

### Requirement: Removal reason help describes the supported operations
The CLI SHALL explain that the delta reason option is accepted for removal operations and is not accepted by modification operations.

#### Scenario: Help prevents inappropriate reason use
- **WHEN** an agent reads delta command help
- **THEN** it can distinguish the removal reason option from scenario modification fields
