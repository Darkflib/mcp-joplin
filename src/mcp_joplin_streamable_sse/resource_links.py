"""Remove references to a Joplin resource from a note body without touching other text.

Joplin links resources from Markdown as ``:/<resource id>``:

- inline links and images: ``[label](:/id)``, ``![alt](:/id)``, optionally with a
  title: ``![alt](:/id "title")``
- reference definitions: ``[ref]: :/id`` on a line of their own
- HTML embeds the editor can produce: ``<img src=":/id" ...>`` and
  ``<a href=":/id">label</a>``

Only those constructs are removed. Surrounding prose on the same line stays; a
line is dropped only when the removal leaves nothing but whitespace on it.
"""

from __future__ import annotations

import re

# One HTML attribute: a name, optionally `= value` where a quoted value is
# consumed whole (so text inside another attribute's quotes can never match).
_HTML_ATTR = r"""[^\s=>/"']+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>"']+))?"""

# A Markdown link label: escaped characters, anything but brackets, or one level
# of balanced [nested] brackets (CommonMark allows those). A raw unbalanced `[`
# is not allowed, so a match can never start at an earlier bracket in the prose.
_LABEL = r"(?:\\.|[^\[\]\\]|\[(?:\\.|[^\[\]\\])*\])*"


def _link_constructs(resource_id: str) -> list[str]:
    rid = re.escape(resource_id)
    # The target must end right after the id: `:/abc` must not match `:/abcdef`.
    target = rf":/{rid}(?![0-9A-Za-z])"

    def html_tag(tag: str, attr: str, *, closing: bool) -> str:
        # <tag ...attrs... attr=":/id" ...attrs...> where `attr` is a whole
        # attribute name (data-src is not src).
        open_tag = (
            # No back-reference for the quote: this text is embedded in several
            # alternatives, which would renumber the groups.
            rf"<{tag}(?:\s+{_HTML_ATTR})*?\s+{attr}\s*=\s*(?:\"{target}\"|'{target}')"
            rf"(?:\s+{_HTML_ATTR})*\s*/?>"
        )
        return open_tag + (rf".*?</{tag}\s*>" if closing else "")

    return [
        # [label](:/id) / ![alt](:/id) / ![alt](:/id "title"); not after a `\`.
        rf"(?<!\\)!?\[{_LABEL}\]\(\s*<?{target}>?(?:\s+\"[^\"]*\")?\s*\)",
        html_tag("img", "src", closing=False),
        html_tag("a", "href", closing=True),
    ]


def _patterns(resource_id: str) -> list[re.Pattern[str]]:
    """One pattern per construct, also consuming exactly one adjacent space.

    Alternatives, tried in order, so removing a link from prose leaves single
    spacing without touching indentation or a trailing hard line break:
    1. preceded by a space and followed by one -> eat the following space
    2. preceded by a space, followed by punctuation or end of line -> eat the
       preceding space
    3. at the start of the line, followed by spaces -> eat those spaces
    4. anywhere else -> just the construct
    """
    compiled = []
    for link in _link_constructs(resource_id):
        compiled.append(
            re.compile(
                rf"(?<=[ \t])(?:{link})[ \t]"
                rf"|[ \t](?:{link})(?=[.,;:!?)\]]|$)"
                rf"|^(?:{link})[ \t]+"
                rf"|(?:{link})",
                re.IGNORECASE | re.DOTALL,
            )
        )
    return compiled


# A line left holding only a list/quote marker once its link is gone.
_EMPTY_MARKER_LINE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)]|>)[ \t]*$")


def _reference_definition(resource_id: str) -> re.Pattern[str]:
    rid = re.escape(resource_id)
    return re.compile(
        rf"^[ \t]*\[[^\]]+\]:[ \t]*<?:/{rid}(?![0-9A-Za-z])>?(?:[ \t]+\"[^\"]*\")?[ \t]*$"
    )


def remove_resource_links(body: str, resource_id: str) -> tuple[str, int]:
    """Return ``(new_body, removed_count)`` with every reference to the resource removed.

    The body is returned unchanged (same object, count 0) when nothing matches,
    so callers can skip writing the note back.
    """
    if not resource_id:
        raise ValueError("resource_id must not be empty")

    patterns = _patterns(resource_id)
    ref_def = _reference_definition(resource_id)
    removed = 0
    dropped_line = False
    out: list[str] = []

    # keepends=True preserves each line's own terminator (\n, \r\n) and whether
    # the body ends with a newline.
    for line in body.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        ending = line[len(content) :]

        if ref_def.match(content):
            removed += 1
            dropped_line = True
            continue

        new_content = content
        for pattern in patterns:
            new_content, n = pattern.subn("", new_content)
            removed += n

        if new_content == content:
            out.append(line)
        elif new_content.strip() and not _EMPTY_MARKER_LINE.match(new_content):
            # Prose remained on the line; keep it as-is.
            out.append(new_content + ending)
        else:
            # The line held nothing but the link(s) (and perhaps a bullet); drop it.
            dropped_line = True

    if removed == 0:
        return body, 0
    result = "".join(out)
    if dropped_line:
        # A dropped trailing link (attach appends one after a blank line) would
        # otherwise leave blank lines at the end; keep a single final newline.
        stripped = result.rstrip("\r\n")
        if stripped != result:
            result = stripped + ("\r\n" if result.endswith("\r\n") else "\n")
    return result, removed
