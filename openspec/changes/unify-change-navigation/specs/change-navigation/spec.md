## ADDED Requirements

### Requirement: Shared discovery preserves domain workflows
The system SHALL store new changes under docspec/changes while preserving document and software formats and completion rules.

#### Scenario: Existing software container
- **WHEN** an existing change lives under software/changes
- **THEN** reading, editing and archiving remain available without query-time migration

### Requirement: Queries are read-only and reliable
The system SHALL provide change and change show with shared versioned JSON and text results without tests, task refresh or managed writes.

#### Scenario: Incomplete change
- **WHEN** tasks fail or document targets are unfinished
- **THEN** the query succeeds and displays the existing judgment, identifiers and sources

#### Scenario: Historical query
- **WHEN** archived or abandoned changes are requested with --all or show
- **THEN** their stored records are shown without live acceptance reevaluation

#### Scenario: Ambiguous or corrupt records
- **WHEN** an id is duplicated or a record cannot be read reliably
- **THEN** the query fails explicitly instead of choosing a copy or claiming completion

### Requirement: Explicit safe migration
The system SHALL preflight all migration paths, identities and seals and preserve bytes, reverting completed moves when a later move fails.

#### Scenario: Collision
- **WHEN** a migration or import batch contains a reserved identity
- **THEN** it fails before moving or writing any managed file

#### Scenario: Shared sealed record
- **WHEN** a software record is hand-edited in the common location
- **THEN** the hook rejects the write and broken seals produce unknown handover freshness
