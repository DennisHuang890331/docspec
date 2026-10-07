## ADDED Requirements

### Requirement: Frozen versions have an immutable snapshot
The system SHALL write a new document version under `docspec/changes/_versions/<article>/<version>/snapshot/document.md` together with its referenced managed assets under `snapshot/assets/`, preserving the whole snapshot as immutable input.

#### Scenario: First owner-authorized freeze
- **WHEN** the owner explicitly requests the first freeze of a current written document
- **THEN** the system creates its snapshot and document baseline without requiring a new document change and preserves the working latest document

#### Scenario: Working image changes after freeze
- **WHEN** a managed working image is changed after a version was frozen
- **THEN** reading or exporting the old version uses that version's captured asset bytes and its snapshot remains unchanged

#### Scenario: Snapshot write or deletion
- **WHEN** an external write, replacement, addition or deletion targets a frozen snapshot or its assets
- **THEN** the write guard rejects the mutation and the system does not silently replace the recorded hash to accept altered content

#### Scenario: Missing asset in a new snapshot
- **WHEN** an image referenced by a version's new snapshot is absent or cannot be verified
- **THEN** export fails with the affected reference and does not substitute a current working image

### Requirement: Version discovery is read-only and rejects ambiguity
The system SHALL provide `artispec versions [article] [--json]` and read legacy snapshots without query-time migration, while refusing duplicate new and legacy copies of the same article and version.

#### Scenario: Legacy version
- **WHEN** a frozen version exists only under legacy `docs/archive/`
- **THEN** version discovery and snapshot reading report its original location without writing project files

#### Scenario: Duplicate version copies
- **WHEN** the same article and version exists in both new and legacy snapshot locations
- **THEN** list or snapshot reading reports the conflict instead of choosing either copy, even if their Markdown bytes match

#### Scenario: Reserved version tree
- **WHEN** normal change discovery, archive or software change migration scans shared changes
- **THEN** `_versions` and `_preview` are excluded from ordinary document/software change containers and keep their own identity rules

### Requirement: Version history has one write location
The system SHALL write document history to `docspec/changes/_versions/<article>/history.md` and require explicit migration before extending an article that still has unmigrated legacy history.

#### Scenario: Existing legacy history at freeze
- **WHEN** freeze would create a new history while the article retains legacy history
- **THEN** freeze rejects the operation and names `artispec versions migrate <article>` rather than splitting history across two locations

#### Scenario: Unsafe history write target
- **WHEN** the article history path uses a symbolic link or junction, escapes the project, or exists as a non-file
- **THEN** freeze rejects it before rendering or creating a new snapshot, preserving the target and existing manifest and baselines

### Requirement: Explicit migration preserves verified history
The system SHALL provide `artispec versions migrate [article] [--dry-run]`, select all articles when omitted, preflight the complete selected batch, preserve original snapshot bytes and hashes, and rekey only verified freeze-manifest entries without modifying sealed baselines.

#### Scenario: Successful move
- **WHEN** selected old snapshots, freeze entries, history and paths are valid and their targets are free
- **THEN** explicit migration moves the records to the new version tree with identical original Markdown bytes and hash, preserves existing sealed baselines in place, and updates only the verified manifest path keys

#### Scenario: Dry-run
- **WHEN** migration runs with `--dry-run`
- **THEN** it reports selected moves and problems without creating, moving, deleting, resealing or rewriting project files

#### Scenario: Later item has an invalid hash or collision
- **WHEN** any selected article has a mismatching old freeze hash, conflicting target/history or unsafe resolved path
- **THEN** preflight rejects the batch before any selected source, manifest or baseline is changed

#### Scenario: Failure during a valid batch
- **WHEN** a filesystem operation fails after migration has begun
- **THEN** completed moves and manifest changes are rolled back and the failure is reported without claiming migration success

#### Scenario: Historical image provenance is unavailable
- **WHEN** a legacy snapshot references an image but has no identifiable contemporaneous asset
- **THEN** valid original Markdown migration succeeds with unknown asset provenance or missing assets reported, without copying current assets or declaring the historical image verified, and export with no version asset explicitly fails

#### Scenario: Repeat after successful migration
- **WHEN** explicit migration is run again with no remaining legacy content
- **THEN** it reports no pending move without duplicating, overwriting or rehashing the existing version

### Requirement: Legacy registrations and unversioned proof retain honest identities
The system SHALL preserve old `register-legacy` content under `_versions/_legacy/<name>/snapshot/` without inventing a document version, and retain unversioned historical proof under `_versions/<article>/_legacy-proof/` with unknown version provenance.

#### Scenario: All-article migration includes legacy registration
- **WHEN** an explicit migration without an article argument encounters old registered files in `docs/archive/legacy/`
- **THEN** it preflights and moves that collection with identical bytes and original verified hash rekeying, while preserving legacy read fallback and excluding those registrations from document version-number sequences

#### Scenario: Unversioned old proof
- **WHEN** a historical proof directory has no trustworthy version identity
- **THEN** migration stores its files under the article's `_legacy-proof/` and reports unknown provenance instead of attaching them to the latest or any selected version

#### Scenario: Reserved identity collision
- **WHEN** an article or version identity collides with `_legacy`, `_legacy-proof` or `_preview` at its reserved location
- **THEN** discovery or migration rejects the conflict without reinterpreting or overwriting the existing content

### Requirement: Reproducible outputs stay outside snapshots
The system SHALL regenerate a selected frozen version's export and proof beneath that version's `exports/` and `proof/`, place unfrozen previews beneath the article's `_preview/`, and retain existing latest-output behavior without pruning unrelated artifacts.

#### Scenario: Export an old version
- **WHEN** the user selects an older frozen version for export and proof
- **THEN** the system uses that version's snapshot/assets and matching exported file, writes its own version exports/proof, and leaves other versions and latest outputs intact

#### Scenario: Unfrozen preview
- **WHEN** the user explicitly exports or proofs the unfrozen latest content
- **THEN** preview artifacts are written under `_preview/` without creating a frozen version, changing snapshot hashes or replacing existing frozen-version artifacts

#### Scenario: Format correction of a frozen version
- **WHEN** a permitted profile or format setting is adjusted and the same frozen version is re-exported
- **THEN** exports/proof can be regenerated while snapshot Markdown/assets and existing sealed baseline bytes remain unchanged

#### Scenario: Handover freshness after output regeneration
- **WHEN** only version proof, legacy proof or unfrozen preview artifacts change
- **THEN** handover freshness remains unchanged, while changes to snapshot or working source assets remain tracked
