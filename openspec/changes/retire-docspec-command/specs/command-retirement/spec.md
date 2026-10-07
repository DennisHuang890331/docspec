## ADDED Requirements

### Requirement: Single executable with stable data identifiers
The distribution SHALL provide only the artispec console script and SHALL preserve the docspec distribution name, dspx namespace, managed directories, DOCSPEC environment variables and ownership markers.

#### Scenario: Upgrade in an isolated environment
- **WHEN** a pre-retirement wheel is upgraded to the new wheel
- **THEN** artispec is executable and the previous distribution-owned docspec script is absent from that environment
- **AND** unrelated installations and managed record bytes are unchanged

### Requirement: Safe hook refresh
Initialization SHALL resolve artispec without falling back to docspec, SHALL replace only its own legacy/current hooks, and SHALL preserve foreign hooks and user settings.

#### Scenario: Mixed hook entry
- **WHEN** initialization refreshes a settings entry containing both owned and foreign hook children
- **THEN** only owned children are replaced and foreign children and custom entry fields survive

#### Scenario: Corrupt settings
- **WHEN** existing hook settings contain invalid JSON or an invalid hook structure
- **THEN** initialization reports the affected settings path and fails without overwriting those settings

#### Scenario: Executable absent from PATH
- **WHEN** artispec cannot be resolved
- **THEN** the tool explains how to fix PATH and does not invoke or generate a docspec command

### Requirement: Current instructions use the installed executable
Current help, guides, recommendations and generated rules SHALL use artispec commands while historical records SHALL retain their original wording.

#### Scenario: Reinitialization
- **WHEN** generated instructions and skills are refreshed twice
- **THEN** managed blocks and hooks are not duplicated, and user content and historical records are preserved
