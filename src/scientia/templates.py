"""scientia.templates — placeholder rendering with no external engine (ADR-0008).

Templates render by ``str.format_map`` over a flat dict. There is no Jinja, no
control flow, no custom engine. Placeholders are ``{name}``; a literal brace in
template prose is escaped by doubling it (``{{`` / ``}}``). Templates load from
``references/`` only (resolved via :func:`scientia.paths.references_dir`).

This keeps the dependency surface at stdlib (ASR-9) and the output fully
deterministic: the same vars always render the same bytes.
"""

from __future__ import annotations

from pathlib import Path

from scientia import paths

__all__ = ["render", "render_to_file", "template_path", "TemplateError"]


class TemplateError(Exception):
    """Raised when a template cannot be found or references an undefined var."""


class _StrictDict(dict):
    """A format_map backing dict that raises a clear error on a missing key."""

    def __missing__(self, key):  # noqa: D401
        raise KeyError(key)


def template_path(template_name: str) -> Path:
    """Resolve a template name to a file under ``references/``.

    Accepts the exact filename (``proposal.md.tmpl``) or a logical stem
    (``proposal`` / ``proposal.md``), trying the ``.md.tmpl`` and ``.tmpl``
    suffixes in turn.
    """
    refs = paths.references_dir()
    candidates = [
        template_name,
        f"{template_name}.tmpl",
        f"{template_name}.md.tmpl",
    ]
    # If the caller passed e.g. "proposal.md", also try "proposal.md.tmpl".
    if template_name.endswith(".md"):
        candidates.append(f"{template_name}.tmpl")
    for cand in candidates:
        p = refs / cand
        if p.is_file():
            return p
    raise TemplateError(
        f"template {template_name!r} not found in {refs} "
        f"(tried: {', '.join(candidates)})"
    )


def render(template_name: str, **vars) -> str:
    """Render a template by flat-dict substitution. Returns the rendered string."""
    text = template_path(template_name).read_text(encoding="utf-8")
    try:
        return text.format_map(_StrictDict(vars))
    except KeyError as exc:
        raise TemplateError(
            f"template {template_name!r} references undefined placeholder {exc.args[0]!r}; "
            f"provided vars: {sorted(vars)}"
        ) from None
    except (ValueError, IndexError) as exc:
        raise TemplateError(
            f"template {template_name!r} has a malformed placeholder "
            f"(did you forget to double a literal brace?): {exc}"
        ) from None


def render_to_file(template_name: str, out_path: Path, **vars) -> None:
    """Render a template and write it to ``out_path`` (idempotent: an unchanged
    result leaves the file byte-identical)."""
    out_path = Path(out_path)
    rendered = render(template_name, **vars)
    if out_path.exists() and out_path.read_text(encoding="utf-8") == rendered:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
