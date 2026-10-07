## ADDED Requirements

### Requirement: Executable complete workflow documentation
The English README SHALL provide a concise project overview, getting-started and shared navigation commands, both domain workflow outlines, and links to detailed documentation, and SHALL contain no docspec spelling, including in URLs. The linked user guide SHALL distinguish the docspec installation name from artispec commands and SHALL describe document development through authorized freeze/PDF/proof, software proposal through independently signed tests/evidence/archive, and upgrade without implicit data migration.

#### Scenario: Concise entry page with complete linked guidance
- **WHEN** a participant reads the README and follows its installation or domain-workflow links
- **THEN** the README uses only ArtiSpec branding and the linked guide preserves truthful installation names, complete commands, owner authority, and domain completion conditions

#### Scenario: Unpublished local installation
- **WHEN** a participant follows this branch's installation instructions
- **THEN** the participant installs the local source or wheel rather than treating a remote old release as the new functionality

### Requirement: Recorded independent fresh-agent acceptance
Validation SHALL use six isolated synthetic cases, three per supported runtime, and SHALL record actual installed commands, exit codes and output with expected facts outside cases.

#### Scenario: New complete workflow
- **WHEN** a fresh participant creates the synthetic document and software
- **THEN** the document obtains an explicitly authorized frozen version and PDF/proof, and the software obtains engine-generated evidence and archive with independently authored/signed tests

#### Scenario: Code layout found during proof
- **WHEN** the synthetic document includes highlighted or plain fenced code with separate lines, a blank line and indentation
- **THEN** the exported PDF preserves those line and indentation relationships without changing frozen source bytes or relaxing fidelity verification

#### Scenario: Legacy upgrade
- **WHEN** a participant upgrades the old project and refreshes generated rules
- **THEN** existing work, user configuration and data survive, protection remains effective, and unfinished work is not reported as complete

#### Scenario: Stale handover
- **WHEN** a participant resumes the stale case
- **THEN** it identifies effective and original superseded references, latest failed evidence, signoff and unfrozen document state before rewriting the handover
- **AND** other managed records are unchanged

### Requirement: Honest validation boundaries
Reports SHALL separate tool/documentation defects, environment failures and agent performance, and SHALL identify WSL controller boundaries, offline asset sources and unavailable shell history.

#### Scenario: Environment failure
- **WHEN** a required download or runtime verification fails
- **THEN** it is recorded as a failure or limitation rather than a pass or a reason to weaken tests
