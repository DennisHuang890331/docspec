## ADDED Requirements

### Requirement: Isolated deterministic preparation
The validation harness SHALL prepare the same synthetic contract on Windows and Linux, preserve all existing runs, and keep evaluator answers outside participant projects.

#### Scenario: Prepare a new case
- **WHEN** the controller supplies an installed CLI path, interpreter, wheel and platform
- **THEN** the harness creates a fresh project containing only the bilingual README, opening task and synthetic CSV, records artifact and contract fingerprints, and does not launch product or test processes

#### Scenario: Prepare another run
- **WHEN** preparation is repeated in the same output directory
- **THEN** a distinct run is created and every byte of prior runs remains unchanged

### Requirement: Truthful full workflow acceptance
The evaluator SHALL distinguish preparation, mechanical regression, actual participant execution, environment failure, product defects and agent performance.

#### Scenario: A role cannot sign tests
- **WHEN** real independent participant sessions are blocked by provider-based identity checks
- **THEN** the controller records the restriction, does not impersonate another provider or the owner, and does not report software acceptance

#### Scenario: Two deliveries and one fresh handover
- **WHEN** first delivery has been independently verified
- **THEN** exactly one capacity/remaining-seats event is introduced, a fresh session takes over while work is unfinished, and second delivery is assessed against recorded facts and actual outputs

#### Scenario: Platform-specific evidence
- **WHEN** a controller runs Linux validation through WSL
- **THEN** the report states the actual runtime and does not treat Linux results as Windows double-click delivery evidence
