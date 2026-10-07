## ADDED Requirements

### Requirement: Guide projects the current governance source contract
The bundled guide SHALL project owner rulings and supplied facts as governance sources and change notes as change rationale with references to those sources. Full text, develop text and JSON views SHALL use the same workflow source without changing managed project files.

#### Scenario: Clear owner choice or supplied fact
- **WHEN** an agent queries the develop workflow for an existing clear owner choice or supplied fact
- **THEN** the guide directs reuse and recording through ruling or info as appropriate, without requiring the words to be copied into notes or confirmed again

#### Scenario: Unclear or missing choice
- **WHEN** a choice affecting design is missing or unclear
- **THEN** the guide retains clarification before recording, without treating the agent's own choice as an owner ruling

#### Scenario: Shared read-only projection
- **WHEN** full text, develop text and JSON guide queries run against a project containing governance records
- **THEN** all project the same current source contract and preserve the original records and managed content

### Requirement: Advisory notes do not alter completion conditions
The guide SHALL NOT introduce additional notes or duplicated owner records as a completion condition. Existing target completion, fork drift, test-role separation and valid-evidence requirements SHALL remain unchanged.

#### Scenario: Seed-only or missing notes
- **WHEN** a document change has seed-only or missing notes
- **THEN** archive continues to use its existing completion and drift rules, rather than requiring a second copy of the owner's words
