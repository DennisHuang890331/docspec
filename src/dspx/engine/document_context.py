"""Explicit, read-only document query context; no preview is created or refreshed."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dspx.engine import change as chg, store
from dspx.engine.model import ModelError


class DocumentContextError(ModelError):
    """The selected document sources cannot be read safely or consistently."""


def add_context_arguments(parser):
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--official", action="store_true",
                          help="read official sources (the default)")
    selector.add_argument("--change", metavar="ID", default=None,
                          help="read official sources overlaid by this active document change")


def _safe_path(layout, path: Path) -> Path:
    try:
        path.resolve().relative_to(layout.project_root.resolve())
    except ValueError as exc:
        raise DocumentContextError(f"document source leaves the project: {path}") from exc
    return path


def _read_article(layout, path: Path, name: str):
    article = store.load_article(_safe_path(layout, path), verify=True)
    if article.name != name:
        raise DocumentContextError(f"{path}: article {article.name!r} differs from {name!r}")
    seen = set()
    for record in article.records:
        parts = record.path.split("/")
        if (parts[0] != name or any(p in ("", ".", "..") for p in parts)
                or "\\" in record.path):
            raise DocumentContextError(f"{path}: section {record.path!r} is outside article {name!r}")
        if record.path in seen:
            raise DocumentContextError(f"{path}: duplicate section path {record.path!r}")
        seen.add(record.path)
    return article


class QueryLayout:
    """Read adapters use one already verified union, without disk overlays or caches."""

    def __init__(self, context):
        self._context = context
        self._base = context.base

    def __getattr__(self, name):
        return getattr(self._base, name)

    def query_articles(self):
        return sorted(self._context.articles)

    def query_article(self, article):
        return self._context.articles.get(article)

    def query_official_leaves(self):
        return self._context.official_leaves

    def query_config(self):
        return self._context.config

    def staging_article(self, article):
        # Return the complete union so a removed group never falls back to official.
        return self.query_article(article)

    def article_store(self, article):
        official = store.store_path(self._base, article)
        if official.is_file():
            return official
        return self._context.staged_paths.get(article, official)

    def docs_latest(self, article):
        if article in self._context.preview_articles:
            return chg.preview_dir(self._context.change.dir) / f"{article}_latest.md"
        return self._base.docs_latest(article)

    def docs_ledger(self, article):
        if article in self._context.preview_articles:
            return chg.preview_dir(self._context.change.dir) / f"{article}.sections.yaml"
        return self._base.docs_ledger(article)

    def docs_ledger_prev(self, article):
        if article in self._context.preview_articles:
            return chg.preview_dir(self._context.change.dir) / f".{article}.prev.none"
        return self._base.docs_ledger_prev(article)

    def docs_ledger_legacy(self, article):
        if article in self._context.preview_articles:
            return chg.preview_dir(self._context.change.dir) / f".{article}.legacy.none"
        return self._base.docs_ledger_legacy(article)

    def verdicts_journal(self, article):
        if article in self._context.preview_articles:
            return chg.preview_dir(self._context.change.dir) / f"{article}.verdicts.yaml"
        return self._base.verdicts_journal(article)

    @property
    def writing_guide(self):
        return self._context.file_source(self._base.writing_guide)

    def query_glossary_path(self):
        return self._context.file_source(self._base.planning_home / "glossary.yaml")

    def query_config_path(self):
        return self._context.file_source(self._base.planning_home / "config.yaml")


@dataclass
class DocumentContext:
    base: object
    config: dict
    change: object | None = None
    articles: dict = field(default_factory=dict)
    official_leaves: list = field(default_factory=list)
    staged_paths: dict = field(default_factory=dict)
    staged_articles: dict = field(default_factory=dict)
    official_paths: dict = field(default_factory=dict)
    preview_articles: set = field(default_factory=set)
    leaves: list = field(default_factory=list)
    layout: object = None

    def file_source(self, official):
        if self.change is not None:
            staged = chg.staging_target(self.change.dir, self.base, official)
            if (staged.exists() or staged.is_symlink()) and not staged.is_file():
                raise DocumentContextError(f"selected staging source is not a readable file: {staged}")
            if staged.is_file():
                return _safe_path(self.base, staged)
        return _safe_path(self.base, official)

    def relative(self, path):
        return _safe_path(self.base, path).relative_to(self.base.project_root).as_posix()

    def record(self, section):
        article = self.articles.get(section.split("/", 1)[0])
        return article.record_by_path(section) if article is not None else None

    def require_section(self, section, *, allow_pending=False):
        record = self.record(section)
        if record is not None and record.kind == "leaf":
            if record.concept is not None or allow_pending:
                return
        if (allow_pending and self.change is not None
                and any(t.kind == "create" and t.ref == section for t in self.change.targets)):
            return
        label = f'change "{self.change.id}" union' if self.change else "official sources"
        raise DocumentContextError(f'leaf section "{section}" not found in {label} (removed or absent)')

    def record_source(self, section):
        article = section.split("/", 1)[0]
        staged = self.staged_paths.get(article)
        if staged is not None:
            staged_article = self.staged_articles[article]
            if staged_article.record_by_path(section) is not None:
                return {"kind": "staging", "path": self.relative(staged)}
        official = self.official_paths.get(article)
        return {"kind": "official", "path": self.relative(official) if official else None}

    def ledger_source(self, article):
        for path in (self.layout.docs_ledger(article), self.layout.docs_ledger_prev(article),
                     self.layout.docs_ledger_legacy(article)):
            if path.is_file():
                return path
        return None

    def metadata(self, diagnostics=()):
        names = sorted(self.articles)
        return {
            "context": {"kind": "change" if self.change else "official",
                        "change": self.change.id if self.change else None},
            "source": {
                "stores": [{"article": name,
                            "official": self.relative(self.official_paths[name]) if name in self.official_paths else None,
                            "staging": self.relative(self.staged_paths[name]) if name in self.staged_paths else None}
                           for name in names],
                "prose": [{"article": name,
                           "kind": "preview" if name in self.preview_articles else "official",
                           "path": self.relative(self.layout.docs_latest(name)),
                           "ledger": self.relative(self.ledger_source(name)) if self.ledger_source(name) else None,
                           "ledger-expected": self.relative(self.layout.docs_ledger(name))} for name in names],
                "writing-guide": self.relative(self.layout.writing_guide),
                "glossary": self.relative(self.layout.query_glossary_path()),
                "config": self.relative(self.layout.query_config_path()),
            },
            "diagnostics": list(diagnostics),
        }

    def print_context(self, diagnostics=(), *, stream=None):
        import sys
        stream = stream or sys.stdout
        label = f'change "{self.change.id}" (official + staging)' if self.change else "official"
        print(f"context: {label}", file=stream)
        if self.change:
            for article, path in sorted(self.staged_paths.items()):
                print(f"  source: {self.relative(path)} (staging over official)", file=stream)
            for article in sorted(self.preview_articles):
                print(f"  prose: {self.relative(self.layout.docs_latest(article))} "
                      f"(ledger: {self.relative(self.layout.docs_ledger(article))})", file=stream)
            print("  Unaffected records and articles use official sources.", file=stream)
        else:
            print(f"  source: {self.relative(self.base.corpus_dir)} (official stores)", file=stream)
        for diagnostic in diagnostics:
            print(f"  {diagnostic['message']}", file=stream)

    def preview_diagnostics(self, articles, *, section=None):
        """Reuse existing sync axes; incomplete previews never count as current prose."""
        if self.change is None:
            return []
        from dspx.commands.query.status import compute_sync
        from dspx.engine.model import project_decision_index
        from dspx.engine.render import (groups_fingerprint, ledger_needs_migration,
                                      parse_section_bodies, read_ledger, read_ledger_groups)
        import yaml

        result = []
        by_section = {leaf.section: leaf for leaf in self.leaves}
        dindex = None
        for article in sorted(set(articles) & self.preview_articles):
            command = f"artispec render {article} --change {self.change.id}"
            path = self.layout.docs_latest(article)
            ledger = self.layout.docs_ledger(article)
            if not path.is_file():
                result.append({"code": "preview-missing", "article": article,
                               "state": "missing", "command": command,
                               "message": f'preview missing for "{article}"; prepare the draft prose and run `{command}` before prose review.'})
                continue
            _safe_path(self.base, path)
            if ledger.is_file():
                _safe_path(self.base, ledger)
                try:
                    data = yaml.safe_load(ledger.read_text(encoding="utf-8"))
                except yaml.YAMLError as exc:
                    raise DocumentContextError(f"{ledger}: malformed preview ledger") from exc
                if not isinstance(data, dict) or not isinstance(data.get("sections"), dict):
                    raise DocumentContextError(f"{ledger}: preview ledger requires a sections mapping")
            recorded = read_ledger(self.layout, article)
            bodies = parse_section_bodies(path.read_text(encoding="utf-8"))
            current_sections = {leaf.section for leaf in self.leaves if leaf.article == article}
            removed_sections = sorted(set(bodies) - current_sections)
            if removed_sections:
                result.append({"code": "preview-stale", "article": article,
                               "state": "stale-structure", "sections": removed_sections,
                               "command": command,
                               "message": f'preview stale for "{article}" (removed sections remain: {", ".join(removed_sections)}); run `{command}` to assemble the current union structure.'})
            if dindex is None:
                dindex = project_decision_index(self.layout, self.leaves)
            selected = [leaf for leaf in self.leaves if leaf.article == article
                        and (section is None or leaf.section == section)]
            for leaf in selected:
                state, _moved = compute_sync(self.layout, leaf, recorded.get(leaf.section),
                                            by_section, dindex,
                                            needs_migration=ledger_needs_migration(self.layout, article))
                if state == "synced" and leaf.section in bodies:
                    continue
                # Software divergence remains a non-blocking, domain-separated condition.
                if state == "stale-software" and leaf.section in bodies:
                    continue
                reason = state if leaf.section in bodies else "unwritten"
                result.append({"code": "preview-stale", "article": article,
                               "section": leaf.section, "state": reason, "command": command,
                               "message": f'preview stale for "{leaf.section}" ({reason}); review/apply the current sources, then run `{command}` before prose review. Rendering alone does not rewrite stale prose.'})
            old_groups = read_ledger_groups(self.layout, article)
            if old_groups is not None and old_groups != groups_fingerprint(self.layout, article):
                result.append({"code": "preview-stale", "article": article,
                               "state": "stale-structure", "command": command,
                               "message": f'preview stale for "{article}" (group structure changed); review the draft structure and run `{command}`.'})
        return result


def load_context(layout, config, change_id=None):
    """Verify the sources once, then build the selected union entirely in memory."""
    context = DocumentContext(base=layout, config=config)
    if change_id is not None:
        if reason := chg.validate_id(change_id):
            raise DocumentContextError(f"--change {change_id!r}: {reason}")
        from dspx.engine.change_catalog import ensure_unique
        ensure_unique(layout, change_id)
        state = chg.change_state(layout, change_id)
        if state != chg.STATE_ACTIVE:
            detail = f"is {state}, not active" if state else "is not an active document change (missing or software domain)"
            raise DocumentContextError(f'--change "{change_id}" {detail}')
        try:
            change = chg.load_change(layout, change_id)
        except (chg.ChangeError, TypeError, ValueError) as exc:
            raise DocumentContextError(f"invalid document change {change_id!r}: {exc}") from exc
        _safe_path(layout, change.dir)
        problems = chg.validate_change(change)
        if change.id != change_id or problems:
            raise DocumentContextError(f"invalid document change {change_id!r}: {problems or 'id differs from folder'}")
        context.change = change
    for name in store.store_articles(layout):
        path = store.store_path(layout, name)
        article = _read_article(layout, path, name)
        context.articles[name] = article
        context.official_paths[name] = path
        context.official_leaves.extend(store.leaves_from_article(layout, article))
    if context.change is not None:
        staging = chg.staging_dir(context.change.dir)
        if staging.is_dir():
            for path in sorted(staging.glob("*.yaml")):
                name = path.stem
                staged = _read_article(layout, path, name)
                original = context.articles.get(name)
                records = {record.path: record for record in original.records} if original else {}
                for record in staged.records:
                    if record.kind == "tombstone":
                        records.pop(record.path, None)
                    else:
                        records[record.path] = record
                context.articles[name] = store.Article(name=name,
                    revision=original.revision if original else 0,
                    records=list(records.values()))
                context.staged_paths[name] = path
                context.staged_articles[name] = staged
                context.preview_articles.add(name)
        for target in context.change.targets:
            article = chg.article_of_ref(target.ref, context.official_leaves, context.change)
            if article:
                context.preview_articles.add(article)
        # These project-wide sources can affect prose throughout the forest.
        for official in (layout.writing_guide, layout.planning_home / "glossary.yaml",
                         layout.planning_home / "config.yaml"):
            if context.file_source(official) != official:
                context.preview_articles.update(context.articles)
        staged_config = context.file_source(layout.planning_home / "config.yaml")
        if staged_config != layout.planning_home / "config.yaml":
            from dspx.engine.config import ConfigError, load_config
            try:
                context.config = load_config(staged_config.parent)
            except ConfigError as exc:
                raise DocumentContextError(str(exc)) from exc
    context.layout = QueryLayout(context)
    context.leaves = sorted((store.leaf_from_record(context.layout, record)
                            for article in context.articles.values() for record in article.records
                            if record.kind == "leaf"),
                           key=lambda leaf: leaf.section)
    if context.change is not None:
        # Do not turn malformed selected doctrine into an empty, apparently valid index.
        from dspx.engine.glossary import load_glossary
        load_glossary(context.layout)
    return context
