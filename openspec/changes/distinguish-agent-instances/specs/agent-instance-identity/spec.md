## ADDED Requirements

### Requirement: Separate provider from instance
The engine SHALL retain provider labels and record optional stable participant instance identifiers in new software test, task, signoff and objection records.

#### Scenario: Two GPT instances
- **WHEN** a gpt test author and a gpt implementer have different known instance identifiers
- **THEN** the test author may sign its own tests without a provider-based rejection

#### Scenario: Same instance or unknown independence
- **WHEN** a signer has created implementation tasks in the same instance, or same-provider legacy task records lack an instance identifier
- **THEN** signing is rejected and the reason distinguishes same-instance work from unavailable identity information

#### Scenario: Conflicting instance override
- **WHEN** DOCSPEC_ACTOR_ID conflicts with the detected Codex thread identifier
- **THEN** the command reports an error before changing managed records

### Requirement: Consistent ownership
Test changes, removal, signing and objection responses SHALL use the same author comparison, while retaining the existing owner exception and conservative legacy compatibility.

#### Scenario: Non-author modification
- **WHEN** another instance attempts to change, remove or sign a test with a known author instance
- **THEN** the operation is rejected and managed bytes remain unchanged

#### Scenario: Signoff remains content-sensitive
- **WHEN** signed test content or covered scenario changes
- **THEN** evidence reports a stale signoff regardless of distinct provider or instance identifiers

#### Scenario: Historical records
- **WHEN** a record lacks instance metadata
- **THEN** it is read without migration, its original provider behavior is preserved, and same-provider independence is not invented
