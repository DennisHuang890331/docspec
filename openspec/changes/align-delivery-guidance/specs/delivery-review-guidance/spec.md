## ADDED Requirements

### Requirement: Advisory document archive source reminder
The document archive command SHALL distinguish the optional notes text reminder from governance authority and archive completion. It SHALL retain existing target-completion and fork-drift checks and SHALL NOT duplicate, fabricate or rewrite notes or governance records in response to the reminder.

#### Scenario: Seed-only notes with existing governance
- **WHEN** a document change's notes contain only the title and initial why text and valid owner records already exist
- **THEN** the reminder identifies optional rationale and original governance query entry points, states that it is non-blocking, and does not claim that owner rulings are missing

#### Scenario: Incomplete or drifted target
- **WHEN** notes trigger the reminder but a target is unfinished or its forked official source has drifted
- **THEN** archive retains its existing refusal, leaves the change active and does not announce inevitable or completed archive

#### Scenario: Successful archive with no additional notes
- **WHEN** existing target and drift conditions permit archive despite seed-only or absent notes
- **THEN** archive lands the staged change while preserving original notes presence/content and governance bytes

### Requirement: Guidance preserves recorded delivery scope
Bundled proposal and verification skills and generated collaboration rules SHALL distinguish recorded platform, launch, installation and network constraints from additional assumptions. They SHALL direct review of the finished delivery artifact and relevant current document claims without introducing new engine gates or altering historical records.

#### Scenario: Actual platform and artifact coverage
- **WHEN** a change has explicit delivery and environment constraints
- **THEN** the guidance requires reporting coverage of those recorded constraints and unmet conditions, without presenting headless or other-platform tests as proof of an unexercised delivered GUI

#### Scenario: Earlier frozen document has a pending-verification claim
- **WHEN** current evidence differs from the latest delivery document's readiness claim
- **THEN** the guidance directs an explicit correction and owner-requested new frozen version, preserving previous snapshots and independent domain completion conditions
