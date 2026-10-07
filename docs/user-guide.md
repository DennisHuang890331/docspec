# User guide

This guide covers installation, document and software workflows, and upgrades. Start with the [project overview](../README.md) for the common workflow.

The executable and Python distribution are `artispec`. The import package remains `dspx`, and existing project data stays under `docspec/` with `corpus/`. `DOCSPEC_*` environment variables and ownership markers keep their names. New installations provide no `docspec` executable. The repository is still named `docspec`; it is separate from the installation package and project data names.

## Install and initialize

Requires Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). Development now uses the `dev` branch. Install this checkout or a wheel built from it; this does not imply a public PyPI release. A remote installation can use `git+https://github.com/DennisHuang890331/docspec@dev` only after these changes are pushed, with repository access if required.

From the checkout containing `pyproject.toml`:

```text
uv tool install ".[export]" --reinstall
uv tool update-shell
```

Or build and install a local wheel:

```text
uv build --wheel --out-dir dist
uv tool install "/absolute/path/to/artispec-0.1.0-py3-none-any.whl[export]" --python "/absolute/path/to/python" --reinstall
uv tool update-shell
```

Use the wheel actually produced by the build and a Python 3.11+ interpreter path. Quote paths with spaces. A Windows wheel argument can look like `"C:\Tools\ArtiSpec build\artispec-0.1.0-py3-none-any.whl[export]"`. Attach `[export]` directly to the wheel path: the older `--from <wheel> <package>[export]` form can produce conflicting requirements with uv 0.11.19.

Open a new terminal after updating PATH and check the installed entry point:

```text
artispec version
artispec --help
```

If PATH has not refreshed, `uv tool dir --bin` prints the executable directory. On PowerShell, invoke a quoted path with `& "C:\path\to\artispec.exe"`; on Linux use `"/path/to/artispec"`. Do not fall back to the retired command. A stale executable in another Python environment is outside the upgraded installation; inspect its location rather than deleting unrelated installations.

Alternatively use an isolated virtual environment. This also provides pytest for a small Python program's tests:

```text
uv venv .venv
```

On Windows:

```text
uv pip install --python .venv\Scripts\python.exe --reinstall "/absolute/path/to/artispec-0.1.0-py3-none-any.whl[export]" pytest
.venv\Scripts\artispec.exe version
```

On Linux:

```text
uv pip install --python .venv/bin/python --reinstall "/absolute/path/to/artispec-0.1.0-py3-none-any.whl[export]" pytest
.venv/bin/artispec version
```

Put that environment's `Scripts` (Windows) or `bin` (Linux) on PATH before initialization, so generated hooks resolve the installed `artispec`. Use that environment's Python as the registered test runner when necessary.

Create an empty project directory, enter it, and initialize for your actual agent tool:

```text
artispec init --agents-md --tool codex --lang en
```

Supported `--tool` values are `claude`, `codex` (or `chatgpt`), `gemini`, `antigravity`, comma-separated combinations, and `all`. Use `--lang zh-TW` for Traditional Chinese. Select the integration explicitly for unattended runs. Initialization installs skills/instructions, writes the managed AGENTS.md block and configures hooks where supported. Resolve any missing `artispec` PATH warning before relying on a hook.

The `export` extra installs Python dependencies. Install the managed, pinned PDF tools and fonts with:

```text
artispec setup
artispec doctor
```

Setup installs controlled PDF tools and fonts under `platformdirs.user_data_dir('artispec', appauthor=False)`: `%LOCALAPPDATA%\artispec` on Windows and normally `~/.local/share/artispec` on Linux (or the configured `XDG_DATA_HOME`). It aligns the PDF environment, not ArtiSpec's code. A download or checksum failure is not successful setup. Optional diagram rendering uses `artispec setup --with-drawio`. Optional journal compilation tools use `artispec setup --with-latex`; journal export itself emits `.tex` for an external toolchain. Existing users can explicitly copy their old tool data with the [upgrade procedure](#upgrade-an-existing-project).

## Start or resume any work

The common entry sequence is:

```text
artispec handover
artispec roadmap
artispec roadmap show <work-id>
artispec change
artispec change show <change-id>
```

- Read the handover's promises and cautions. A freshness warning means compare it with current records before relying on it; available differences name changed managed files. An old note without a manifest cannot list those differences.
- Find existing roadmap work, then inspect its summary. It shows recorded dependencies, governance authority, tests/evidence, document state, problems and possible actions. Follow original records for additional detail.
- Reuse work covering the same scope. Only add an item when none exists and retain the returned identifier:

  ```text
  artispec roadmap add --title "Write the operating guide" --ref doc:operating-guide
  artispec roadmap add --title "Implement greeting behaviour" --ref swc:add-greeting
  artispec roadmap link <work-id> --ref change:<document-change-id>
  ```

  Referenced sources must exist. For a document not yet created, register without `--ref` and link it after creation.
- `artispec change --all` includes history. Shared list/show queries identify the domain; they do not refresh tasks, run tests, write handover or migrate files. `roadmap show` is also read-only. Append `--json` to shared list/show or work summary queries for versioned structures.
- Missing links mean the summary cannot establish all constraints. A superseded decision remains an original reference; seeing its successor does not authorize changing the reference or clearing an impact flag.

Work summaries default to schema v2. They retain signer metadata, saved verification-scope fingerprints and original-record entry points without repeating full signed contracts. Identical fingerprints share a source index; different historical scopes remain distinct. `artispec roadmap show <work-id> --json --schema-version 1` retains the original v1 structure. Decisions and supplied information are background basis, not delivery tasks. A work item containing only background references needs a reasoned manual close; it never completes automatically.

Record owner choices with `artispec ruling add`, supplied facts with `artispec info add`, and project decisions with `artispec decision add --based-on <ruling-id>`. A new decision starts as a draft: use `artispec decision activate <returned-id>` to make it effective. Activation checks the ruling already recorded on that decision; it is not new owner permission and must not invent a choice. Use `artispec question` when a choice is unresolved. Clear statements can be recorded directly; read back only when unclear. Query each command's `--help` for its fields. A replacement decision uses `decision add --supersedes <old-id> --based-on <new-ruling-id>`; preserve the original record.

After domain work and verification, rewrite the **whole** handover:

```text
artispec handover write --done "What this session actually completed" --in-progress "Existing work and what remains" --promise "Outstanding owner promise" --caution "Relevant limitation or trap" --next "A concrete next action"
```

Flags are repeatable. Alternatively `--from handover-input.yaml` accepts lists named `done`, `in-progress`, `promises`, `cautions`, and `next`. Omitted old entries are removed; this is not an append-only log. Current progress comes from the roadmap and original records.

## Document workflow

Document skills operate a loop: **develop → apply → check/review → revise as needed**. `develop` establishes audience, scope, structure and decisions; `apply` writes or aligns prose from those sources. `factcheck` records advisory findings. Consult the live contracts instead of guessing fields:

```text
artispec guide
artispec instructions develop operating-guide/Overview
```

1. Reuse known owner requirements and facts. Ask only about missing information that affects the design. A new document does not automatically require software-style proposal/design/task files.
2. Create the outline through the validated write API. A section exists after its first `put`; the engine stamps IDs and ordering. Input files are editable scratch files, not sealed records:

   ```text
   artispec put operating-guide/Overview concept concept-input.yaml
   artispec put operating-guide/Overview material material-input.md
   artispec get operating-guide/Overview concept
   ```

   `artispec guide concept` shows the field contract. Write section decisions only when the owner actually made a normative choice. Sections restating project decisions, information or requirements use `realizes` links such as `gov:D-…`, `gov:I-…`, and `req:<capability>/R<n>`. For a changed requirement still in an active software change, use `draft-req:<change>/<capability>/R<n>`; after archive its original reference follows the sealed landing baseline to the formal source. Missing or invalid sources are reported, never guessed from matching numbers; do not archive unfinished software just to get a document link.
3. Use a **document change** when the existing document change rules require staging, especially normative ruling edits and revisions to a frozen official face. Open it when that need appears; retain targets/staging rather than replacing them with software tasks:

   ```text
   artispec change new revise-operating-guide --seed <decision-or-section-id> --publish advisory
   artispec change show revise-operating-guide
   artispec put operating-guide/Overview concept concept-input.yaml --change revise-operating-guide
   artispec render operating-guide --change revise-operating-guide
   artispec change status revise-operating-guide
   ```

   `--publish release-bound` is also available. Keep change reasoning and references in `notes.md`; preserve the owner's words in governance records. Inspect `artispec change add-target --help` when adding targets. The engine prints staging/preview paths; edit the preview's relevant body, preserving headings and engine markers. Re-render to record alignment. When target conditions are met and the owner accepts, `artispec archive revise-operating-guide` lands the change. This does not grant permission to freeze the document.

   If notes contain only the title/initial why text or are absent, archive prints a non-blocking reminder about optional rationale and original governance queries. It does not establish that rulings are missing, require a second copy of the owner's words, or announce success. Target completion and fork-drift checks still apply; the reminder does not write notes or governance records.

   Queries `get`, `instructions`, `find`, `check` and `diff` default to official content. To inspect a draft, pass the same explicit change id to every query and write:

   ```text
   artispec get operating-guide/Overview concept --change revise-operating-guide
   artispec instructions apply operating-guide/Overview --change revise-operating-guide
   artispec find "operator" --in prose --change revise-operating-guide --json
   artispec check --change revise-operating-guide --json
   artispec diff operating-guide --change revise-operating-guide --json
   ```

   The selected view combines official sources with that change's staged sources, including affected parents and dependencies. Output reports the context and source paths. Draft prose comes from its preview; missing or stale prose is diagnosed instead of silently reviewing old official text. Follow the indicated apply/render step. These queries never render, run tests, write ledgers or refresh records. `check` validates the whole selected project; an article argument only narrows its successful index.
4. Apply the prose projection, preserving headings/markers and editing only the relevant body slots:

   ```text
   artispec instructions apply operating-guide/Overview
   artispec render operating-guide
   artispec status operating-guide
   artispec check
   artispec lint
   ```

   `render` prints the working deliverable path. Write the prose there, then render again to stamp alignment. Write from committed concept/material/decisions, without invented facts. A semantic acknowledgement (`render --ack` or `--ack-own`) needs explicit owner consent; it does not replace missing writing.
5. Only on the owner's **explicit request**, freeze a version and its baseline:

   ```text
   artispec freeze operating-guide --note "Initial approved operating guide"
   ```

   Normal freeze requires current, written sections and clean deliverable text. Missing traceability links and software divergence remain recorded reminders; software errors do not block document freeze. Mechanical success does not prove the prose factually correct.

   Freeze stores the document and its referenced managed images under `docspec/changes/_versions/<article>/<version>/snapshot/`. Initial freeze does not require a new change. Existing document-change rules still apply to subsequent content revisions. Follow the installed command's printed paths; [validation results](dev/validation/document-version-storage-run.md) are recorded separately.

   `docs/` contains the latest public projection. Historical snapshots, PDF exports and proof remain in their version container; do not restore an old public PDF or proof into `docs/`.
6. Render the frozen snapshot to PDF and inspect page images:

   ```text
   artispec export operating-guide
   artispec proof operating-guide
   ```

   Export checks extracted PDF content tokens against the source; it does not prove every glyph or layout choice visually correct. Proof produces PNG pages for review. Adjust formatting and re-export through the release skill. Content fixes return to develop/apply and need another owner-authorized freeze. `--version X.Y.Z` selects a frozen version; use the same version for export and proof. `--latest` explicitly selects an unfrozen preview. Under the approved layout, version exports/proof are regenerated beside the immutable snapshot, and previews use `_preview/`; an older-version or preview export must preserve unrelated versions and latest outputs. A missing captured image must be reported rather than replaced with a current image.

## Software workflow

Software follows **proposal/deltas → independent tests/sign-off → implementation → engine evidence → review/archive**. Registered program repositories contain source and executable tests; `artispec code` writes managed records.

1. Register the program repository and test runner. Here `app/` exists under the project root, containing a Python project with pytest available:

   ```text
   artispec code repo add app app --test-command "python -m pytest -q"
   artispec code repo list
   artispec code change new add-greeting --why "Provide a greeting for callers" --what "Add greeting behaviour" --new greeting --code-areas app:greeting.py
   artispec code change design add-greeting --context "Small Python API" --goal "Return the agreed greeting"
   artispec code change delta add-greeting --capability greeting --op add-requirement --purpose "Provide a greeting API for callers" --title "Greeting" --statement "The function SHALL return Hello followed by the supplied name." --verification test --scenario "Named caller | greet is called with Ada | the result is Hello Ada"
   artispec code task add add-greeting --title "Implement greeting" --implements greeting/R1 --files app:greeting.py --verify test
   ```

   The illustration assumes owner-approved behaviour. Cite actual decisions with design `--decision` and requirement `--based-on` where applicable. Check returned identifiers; substitute them if they differ. A test task can initially lack test IDs, but that is pending planning and cannot complete or archive. When needed, put a quoted absolute environment Python path in `--test-command`; `repo list` shows what the engine will run. Declare implementation files only.
2. Delegate to a **different test-role agent session**. Both sessions may use the same AI provider. Codex automatically records `CODEX_THREAD_ID`; for tools without a detected session id, the controller may set `DOCSPEC_ACTOR_ID` to the stable id saved with the actual launch. A conflicting override is rejected; never change ids to impersonate an author or the owner. A child that inherits the implementer's thread id is not distinguishable and needs a separate session. Legacy same-provider records without ids remain conservative, without automatic reassignment. The test role reads scenarios, plans tests, writes them, checks their behaviour and signs each test:

   ```text
   artispec code testplan add add-greeting --location app:tests/test_greeting.py::test_named_greeting --covers greeting/R1/S1
   artispec code testplan sign add-greeting T1
   artispec code testplan list add-greeting --json
   artispec code task set add-greeting 1 --tests T1
   ```

   The file must exist before signing. Use actual test/task identifiers returned by the engine. The test role runs what it wrote or says it did not. Signing binds the test and shared helpers to its covered scenario, not every unrelated test in the file.
3. The implementer changes declared implementation files and **cannot edit tests**. A dispute uses `artispec code testplan object <change> <test-id> --reason "…"`; the test role resolves it. Obtain completion evidence through the engine:

   ```text
   artispec code evidence run add-greeting 1
   artispec code evidence list add-greeting
   artispec code task list add-greeting
   artispec code change status add-greeting
   ```

   The engine builds the registered runner command and records JUnit collection/results, sign-off and fingerprints. A manually run passing test is feedback, not a replacement for engine evidence. The latest failed attempt cannot be hidden by older success. A changed verification scope, declared file or signed test may require renewed review/evidence.
4. Independent review checks that tests actually prove the scenarios and all necessary evidence is current. Inspection/demonstration requirements need owner acceptance of the current result. Waivers cite effective rulings and reopening conditions; agents cannot fabricate acceptance or authority.

   Match verification to recorded platforms, startup methods, permissions, installation and network restrictions. An operator who needs no installation may still use a host with existing dependencies; restricting one program's connections does not prove the whole host is offline. Cite the actual requirement rather than strengthening it. Headless tests or tests on another OS do not prove an unexercised delivered GUI. Use the author's finished delivery artifact, check the validation copy matches it, and report untested scope and environment failures.

   If delivery includes documents, compare latest claims about readiness or pending verification with current evidence. Correct discrepancies explicitly and freeze a new version only when the owner requests it; preserve historical snapshots. This delivery review adds no engine gate between the document and software domains.

   ```text
   artispec code archive add-greeting --dry-run
   artispec archive add-greeting
   artispec code test
   artispec code spec show greeting
   artispec roadmap
   ```

   Archive merges validated deltas into specifications and records a baseline. Missing necessary tasks, valid evidence, authority or owner acceptance blocks software archive. Semantic review remains a role responsibility: the engine cannot judge whether a test meaningfully proves a requirement.

## Upgrade an existing project

1. Keep a project backup. Build a new wheel and install it in an isolated environment using the procedure above. Verify its `artispec version` and CLI before replacing the current tool installation. The distribution name is now `artispec`; use `--reinstall` because its version may be unchanged. `artispec update` describes the detected installation; a remote old build cannot validate local changes.
2. If the old installation is the uv tool named `docspec`, replace that tool environment with the verified wheel:

   ```text
   uv tool uninstall docspec
   uv tool install "/absolute/path/to/artispec-0.1.0-py3-none-any.whl[export]" --python "/absolute/path/to/python" --reinstall
   uv tool update-shell
   artispec version
   ```

   Uninstall only that old uv tool environment. Other Python environments and their installations are separate. Refresh PATH or open a new terminal as needed.
3. Copy old managed tools and fonts explicitly before refreshing the project:

   ```text
   artispec setup --migrate-data
   artispec doctor
   artispec doctor --deep
   ```

   This is an offline, migration-only operation: it does not download or run ordinary setup. Its source is the former `platformdirs.user_data_dir('docspec')`; its destination is the new ArtiSpec user data directory described above. It copies the managed `tinytex/`, `fonts/`, `pandoc/`, `typst/`, `drawio/`, `cache/`, `tex.lock` and `update-cache.json` when present. The source remains as a backup; unrelated old-root contents stay there. Tool/font bytes are preserved, with only known `tex.lock` paths inside the old root rewritten to the new root. A conflicting destination file refuses the whole batch before copying; an existing destination root, including its `installers/`, is retained. Results distinguish migrated, unchanged and missing items; repeating a successful copy leaves matching content unchanged. For new tool downloads or font alignment, run ordinary `artispec setup` separately. Actual platform checks and limits are recorded in the [installation upgrade report](dev/validation/installation-upgrade-run.md).
4. Enter the existing project and refresh generated content:

   ```text
   artispec init --agents-md --tool codex
   artispec handover
   artispec roadmap
   artispec roadmap show <existing-work-id>
   ```

   Select your actual integration(s). Reinitialization updates this tool's managed block, installed skills and supported hooks without duplication. Content outside the managed block and other tools' hooks/settings is preserved. Corrupt settings produce an error; repair them rather than treating a failed refresh as complete. Restart the agent tool if it caches skills/hooks.
5. Project data, IDs, seals, history and evidence are retained. Tool-data migration does not move or rename a project's `docspec/` or `corpus/`. Old sealed history stays as written; execute current commands with `artispec`.
6. Project data migration is **separate and explicit**. Existing software changes under `docspec/software/changes/` remain usable. To move only these containers and their history into the shared root:

   ```text
   artispec change migrate --dry-run
   artispec change migrate
   ```

   Preflight checks conflicts and preserves record contents. This does not rename `docspec/`, move a program repository or convert document formats. Queries never migrate data.
7. Inspect unfinished work and evidence after upgrading. Refreshing instructions or moving a folder does not complete work. Legacy sign-offs/evidence without necessary scope data can need renewed review or verification; archived history is not reopened or rewritten.

### Document version relocation

The directory change is implemented in `relocate-document-versions`; [its validation report](dev/validation/document-version-storage-run.md) records actual platform results and limits. It replaces new frozen writes to `docs/archive/` and history writes to `docs/revision_history/`. Existing snapshots remain readable through legacy fallback and retain their write protection. A new and an old copy of the same version is a conflict, even when their Markdown matches.

The approved commands are:

```text
artispec versions
artispec versions operating-guide --json
artispec versions migrate --dry-run
artispec versions migrate
```

An article argument restricts migration; omitting it selects all articles. Review the dry-run before moving existing data. Migration preflights every selected source, old freeze-manifest hash, target/history collision and resolved path before writing. It preserves frozen Markdown bytes and existing sealed baseline records in place, and changes only verified freeze-manifest path keys. Queries never migrate. Freeze refuses an article with unmigrated old history and points to this explicit migration instead of creating a second history file.

A legacy Markdown snapshot may lack its original images. That remains unknown provenance or a missing-asset report after relocation; current images must not be copied to manufacture a historical version. New snapshots use their own captured assets. Export/proof regeneration changes outputs, not snapshot content or baseline seals.

Valid old Markdown can be relocated even when its historical images are unavailable, with that limitation reported; exporting it without its version assets fails explicitly. Unversioned old proof is kept under the article's `_legacy-proof/` with unknown version provenance. Files previously registered through `register-legacy` are preserved under `_versions/_legacy/<name>/snapshot/`, retain their original format and verified hashes, and do not become numbered document versions. Default all-article migration includes this collection; old `docs/archive/legacy/` remains readable.

## Where records live

```text
project/
  docspec/
    config.yaml                 Project/document settings
    governance/                 Questions, rulings, information, decisions,
                                impact flags, milestones and roadmap work
    corpus/                     Sealed document source stores and bookkeeping
    changes/
      <document-change>/        change.yaml, notes.md, staging/, preview/
      <software-change>/        proposal.yaml, design.yaml, specs/,
                                tests.yaml, tasks.yaml
      _archive/                 Both domains retain their own archived format
      _abandoned/               Existing document abandonment records
      _versions/<article>/      Approved document version area; not a change
        history.md              Article history
        <version>/
          snapshot/document.md  Immutable frozen Markdown
          snapshot/assets/      Immutable referenced managed images
          exports/              Regenerated <article>_v<version>.<format>
          proof/                Regenerated page_<N>.png
        _preview/               Unfrozen exports/ and proof/
        _legacy-proof/          Old proof with unknown version provenance
      _versions/_legacy/<name>/snapshot/
                                Registered legacy files; no invented version
    software/
      config.yaml               Registered code repositories and test runners
      specs/                    Current software specifications
      evidence/                 Engine-created execution/review evidence
      baselines/                Archived software state
      changes/                  Supported legacy change location
  docs/                         Working latest documents, working assets,
                                and existing latest-output behavior
  app/                          Example program repository
```

Actual document paths follow the configured layout. `artispec guide` projects contracts; `instructions` projects the permitted context. Do not hand-edit sealed records or frozen snapshots. The product does not support simultaneous writers or collaborative editing. Base fingerprints remain to detect overwritten change assumptions.

## Checks, limits and validation

- Mechanical gates check structure, references, cleanliness and domain completion. Traceability reminders and advisory audits are not universal completion gates.
- Software divergence remains visible without blocking document freeze. Document freeze does not complete software tasks; software archive does not freeze documents.
- Fingerprints follow managed content and declared scope, not modification times. Unlinked or undeclared external facts are not automatically watched.
- No automatic semantic completeness judgment, automatic test sign-off or automatic owner approval is provided.
- Independent sessions can share a provider label: new test/task/signoff records carry a stable session id when available. An implementer still cannot sign its own tests or change/remove another author's tests. Legacy same-provider records without ids cannot establish independence. This repair does not turn the earlier unfinished trials into passes; [the historical validation report](dev/validation/readme-workflows-run.md) retains their original results.
- `artispec --help` shows maintenance commands; `--help-all` includes agent commands. `doctor`, `version`, `setup` and `update` explain environment and installation.
- CI runs mechanical regressions. Fresh-agent trials are started manually. Actual results, skips and platform limits appear in [validation reports](dev/validation/), not inferred from the badge.

Document examples and PDFs remain in [docs/showcase/](showcase/), including methods and limitations.

## License

ArtiSpec uses **PolyForm Noncommercial 1.0.0**; commercial use needs a separate license from the author. It is source-available, not OSI-approved open source. Read [LICENSE](../LICENSE) and [NOTICE.md](../NOTICE.md) for terms and bundled third-party components.

## Acknowledgements

The design draws on [OpenSpec](https://github.com/Fission-AI/OpenSpec). ArtiSpec runs independently; OpenSpec manages this repository's development changes. The author directs design and rulings; development and validation have used Claude Code and Codex agents.
