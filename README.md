<div align="center">

<img src="docs/assets/logo.png" alt="ArtiSpec logo" width="160">

# ArtiSpec

**Specification-driven engineering for documents and software.**

English · [繁體中文](README.zh-TW.md)

![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)

</div>

ArtiSpec gives AI agents a workflow for turning decisions and requirements into documents, software, and verification evidence. It connects the owner's decisions, planned work, changes, and delivery records so another agent can see what was done and what still needs attention.

## One project, two workflows

Suppose you need to **add report export and update its operating guide**:

- Record the owner's choices and constraints, then link the software requirements and document sections to their sources.
- Track the work in one roadmap. Document and software changes share a directory and discovery commands, while keeping their own workflow.
- Have a separate test role write and sign off tests. The engine runs verification and records evidence for software completion.
- Review the guide and freeze it only when the owner requests it. Each version preserves its text and referenced images; PDF and page proofs can be regenerated.

Documents and software have their own completion conditions. Missing traceability links are reminders; missing required software tests or valid evidence prevents completion. Software problems are recorded without blocking document freeze.

## Get started

Requires Python 3.11+ on Windows or Linux. The installation package is `artispec`; [install from the local `dev` checkout or a locally built wheel](docs/user-guide.md#install-and-initialize). This does not imply a public PyPI release. Existing users should follow the [upgrade procedure](docs/user-guide.md#upgrade-an-existing-project) to replace the old tool installation and explicitly migrate their managed tools and fonts.

In your project directory, initialize for your agent:

```text
artispec init --agents-md --tool codex --lang en
```

Use `--tool claude` for Claude Code or `--lang zh-TW` for Traditional Chinese. Initialization installs project instructions, skills, and supported hooks. For PDF tools and fonts, see [setup](docs/user-guide.md#install-and-initialize).

**Starting a project:** ask your agent to define the scope, record known decisions and requirements, and register the work. For example:

> Add report export and update the operating guide. Use an independent test role and show me the verification results.

Follow the [document workflow](docs/user-guide.md#document-workflow) or [software workflow](docs/user-guide.md#software-workflow). Skills guide the agent through planning, writing, implementation, and review; CLI commands read and update the managed records. Document `develop` and `apply` are skill stages, not top-level CLI commands.

**Resuming a project:** read the handover, find the existing work, and inspect its current state:

```text
artispec handover
artispec roadmap
artispec roadmap show <work-id>
```

Use `artispec change` to find related changes and `artispec change show <change-id>` for their details. These queries are read-only. Reuse existing work, verify the result, and rewrite the whole handover when handing off. Agents work through handoffs; simultaneous writes to managed records are unsupported.

## Learn more

- [User guide: installation, both workflows, and upgrades](docs/user-guide.md)
- [Document examples and PDFs](docs/showcase/)
- [Document version and platform validation](docs/dev/validation/document-version-storage-run.md)
- [Agent workflow trials and current limitations](docs/dev/validation/readme-workflows-run.md)

Run `artispec --help` for commands or `artispec guide` for record contracts. The user guide is currently in English.

## License and credits

Source-available under [PolyForm Noncommercial 1.0.0](LICENSE). Commercial use requires a separate license; bundled components are listed in [NOTICE.md](NOTICE.md).

Maintained by Yao-Jiun Huang. The design draws on [OpenSpec](https://github.com/Fission-AI/OpenSpec); ArtiSpec runs independently. Development and validation have used Claude Code, Codex, and Gemini agents.
