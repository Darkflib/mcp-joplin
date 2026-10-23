"""remove_resource_links: remove only the references, never the surrounding text."""

from __future__ import annotations

import pytest

from mcp_joplin_streamable_sse.resource_links import remove_resource_links

RID = "0123456789abcdef0123456789abcdef"
OTHER = "ffffffffffffffffffffffffffffffff"


@pytest.mark.parametrize(
    ("body", "expected", "count"),
    [
        pytest.param(f"Intro\n\n[{RID}](:/{RID})\n", "Intro\n", 1, id="attach-output-on-own-line"),
        pytest.param(
            f"See ![chart](:/{RID}) for details.\n", "See for details.\n", 1, id="mid-prose"
        ),
        pytest.param(f"See ![chart](:/{RID}).\n", "See.\n", 1, id="before-punctuation"),
        pytest.param(f"![chart](:/{RID}) caption\n", "caption\n", 1, id="line-start"),
        pytest.param(
            f"- a\n  - see ![x](:/{RID}) here\n",
            "- a\n  - see here\n",
            1,
            id="nested-list-indent-kept",
        ),
        pytest.param(
            f"- one\n- ![x](:/{RID})\n- three\n", "- one\n- three\n", 1, id="bullet-only-dropped"
        ),
        pytest.param(
            f"line one ![x](:/{RID})  \nline two\n",
            "line one  \nline two\n",
            1,
            id="markdown-hard-break-kept",
        ),
        pytest.param(f'text ![x](:/{RID} "A title") more\n', "text more\n", 1, id="with-title"),
        pytest.param(f"[a \\] b](:/{RID}) after\n", "after\n", 1, id="escaped-bracket-label"),
        pytest.param(
            f'Text <img src=":/{RID}" width="200"/> more\n', "Text more\n", 1, id="html-img"
        ),
        pytest.param(f'<a href=":/{RID}">file.pdf</a>\n', "", 1, id="html-anchor"),
        pytest.param(
            f"Use [doc][1].\n\n[1]: :/{RID}\n", "Use [doc][1].\n", 1, id="reference-definition"
        ),
        pytest.param(f"![a](:/{RID}) and ![b](:/{RID})\n", "and\n", 2, id="multiple-on-one-line"),
        pytest.param(f"keep\r\n![x](:/{RID})\r\nend", "keep\r\nend", 1, id="crlf-no-final-newline"),
    ],
)
def test_removes_only_the_reference(body: str, expected: str, count: int) -> None:
    assert remove_resource_links(body, RID) == (expected, count)


def test_other_resources_on_same_line_survive() -> None:
    body = f"![a](:/{OTHER}) and ![b](:/{RID})\n"
    out, n = remove_resource_links(body, RID)
    assert n == 1
    assert out == f"![a](:/{OTHER}) and\n"


def test_id_prefix_is_not_a_match() -> None:
    body = f"![a](:/{RID}00)\n"
    assert remove_resource_links(body, RID) == (body, 0)


def test_no_match_returns_body_untouched_including_trailing_blank_lines() -> None:
    body = "nothing here\n\n\n"
    out, n = remove_resource_links(body, RID)
    assert n == 0
    assert out is body


def test_regression_old_behaviour_deleted_whole_paragraphs() -> None:
    # The previous implementation dropped every line containing "(:/<id>)".
    body = f"Quarterly numbers are in ![chart](:/{RID}) and look strong.\n"
    out, _ = remove_resource_links(body, RID)
    assert "Quarterly numbers are in" in out
    assert "and look strong." in out


def test_empty_resource_id_rejected() -> None:
    with pytest.raises(ValueError):
        remove_resource_links("x", "")


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            f'<img src="https://example.org/keep.png" data-src=":/{RID}">\n', id="data-src"
        ),
        pytest.param(
            f'<a href="https://x.org" data-href=":/{RID}">keep text</a>\n', id="data-href"
        ),
        pytest.param(
            f'<img alt=\' src=":/{RID}" \' src="keep.png">\n', id="src-inside-other-value"
        ),
        pytest.param(f'<abbr href=":/{RID}">x</abbr>\n', id="abbr-is-not-a"),
    ],
)
def test_html_only_matches_real_src_or_href_attributes(body: str) -> None:
    # Review finding: \bsrc also matched data-src and deleted unrelated embeds.
    assert remove_resource_links(body, RID) == (body, 0)


def test_label_cannot_start_at_an_earlier_bracket_in_prose() -> None:
    # Review finding: the label could start at the escaped \[ and eat the prose.
    body = f'Before \\[literal prose ![chart](:/{RID} "title") after.\n'
    assert remove_resource_links(body, RID) == ("Before \\[literal prose after.\n", 1)


def test_nested_brackets_in_label() -> None:
    body = f"[see [docs] here](:/{RID}) tail\n"
    assert remove_resource_links(body, RID) == ("tail\n", 1)


@pytest.mark.parametrize(
    "body",
    [
        f'Text <img width="2" src=":/{RID}" /> more\n',
        f"Text <img src=':/{RID}'> more\n",
    ],
    ids=["double-quoted-self-closing", "single-quoted"],
)
def test_html_img_variants_removed(body: str) -> None:
    assert remove_resource_links(body, RID) == ("Text more\n", 1)


@pytest.mark.parametrize(
    "body",
    [
        f'<img data-src=":/{RID}" src=":/{OTHER}">\n',
        f'<a data-href=":/{RID}" href=":/{OTHER}">x</a>\n',
    ],
    ids=["img", "anchor"],
)
def test_data_attribute_for_target_with_real_attribute_elsewhere_kept(body: str) -> None:
    # Review finding: the element really points at OTHER; detaching RID must keep it.
    assert remove_resource_links(body, RID) == (body, 0)


def test_trailing_blank_lines_kept_when_dropped_link_was_mid_note() -> None:
    # Review finding: only a dropped *trailing* link should normalise the tail.
    body = f"a\n![x](:/{RID})\nb\n\n\n"
    assert remove_resource_links(body, RID) == ("a\nb\n\n\n", 1)


def test_trailing_blank_lines_normalised_when_dropped_link_was_last() -> None:
    body = f"a\n\n![x](:/{RID})\n\n"
    assert remove_resource_links(body, RID) == ("a\n", 1)
