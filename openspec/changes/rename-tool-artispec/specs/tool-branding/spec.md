## ADDED Requirements

### Requirement: Compatible external name
The distribution SHALL provide artispec and retain docspec as an alias without renaming the installation package, Python namespace or managed directories.

#### Scenario: Installed command
- **WHEN** either entrypoint is invoked after installing the wheel
- **THEN** both run the same ArtiSpec CLI

### Requirement: Current collaboration instructions
Generated instructions and skills SHALL use the current external command and preserve existing managed markers and skill identifiers.

#### Scenario: Reinitialization
- **WHEN** init --agents-md is rerun
- **THEN** it updates the existing managed block rather than creating an additional block
