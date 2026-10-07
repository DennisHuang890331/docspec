# work-summary-source-commands Specification

## Purpose
讓工作摘要提供可實際執行的既有唯讀來源查詢，完整呈現原始紀錄及其有效狀態，並保留既有完成判定、角色界線、引用與歷史證據。
## Requirements
### Requirement: Executable source commands
The summary SHALL provide executable existing read-only queries for its governance source rows, with the same commands in text and JSON.

#### Scenario: Questions with different effective states
- **WHEN** an explicitly linked question is open, answered, withdrawn or awaiting explanation
- **THEN** the suggested query returns its original identifier, title, body and effective state without changing project files

#### Scenario: Work and milestone references
- **WHEN** the summary includes an explicitly linked work item or milestone
- **THEN** its suggested query returns the identified work or milestone and the existing derived progress through the supported roadmap interface

#### Scenario: Existing governance queries
- **WHEN** a ruling, information record or active decision is included
- **THEN** its existing suggested query remains executable and preserves the original record content

### Requirement: Preserve completion and history
The correction SHALL only change source query advice, preserving existing completion judgments, original references, sealed records and historical evidence.

#### Scenario: Query incomplete work
- **WHEN** a suggested source query opens unfinished work
- **THEN** the query succeeds with its actual unfinished state and neither completes it nor executes tests

#### Scenario: Retained failed command
- **WHEN** a validation case recorded the previous invalid source suggestion
- **THEN** its original command, exit code and artifacts remain available and are not rewritten as successful validation
