"""Tests for provenance extraction from a Docling-like document."""

from dataclasses import dataclass
from enum import StrEnum

from open_notebook.evidence.docling_adapter import build_evidence_blocks


class Label(StrEnum):
    TITLE = "title"
    SECTION_HEADER = "section_header"
    TEXT = "text"


@dataclass
class FakeBBox:
    l: float
    t: float
    r: float
    b: float


@dataclass
class FakeProvenance:
    page_no: int
    bbox: FakeBBox
    charspan: list[int]


@dataclass
class FakeItem:
    label: Label
    text: str
    prov: list[FakeProvenance]


class FakeTableItem:
    label = "table"

    def __init__(self, markdown: str, prov: list[FakeProvenance]):
        self._markdown = markdown
        self.prov = prov

    def export_to_markdown(self, *, doc):
        assert doc is not None
        return self._markdown


class FakeDocument:
    def __init__(self, items):
        self._items = items

    def iterate_items(self):
        yield from self._items


def test_blocks_preserve_page_bbox_type_and_section_path():
    document = FakeDocument(
        [
            (
                FakeItem(
                    label=Label.TITLE,
                    text="Regulamento de teste",
                    prov=[
                        FakeProvenance(
                            page_no=1,
                            bbox=FakeBBox(l=10, t=20, r=500, b=60),
                            charspan=[0, 21],
                        )
                    ],
                ),
                0,
            ),
            (
                FakeItem(
                    label=Label.SECTION_HEADER,
                    text="Artigo 12.º",
                    prov=[
                        FakeProvenance(
                            page_no=2,
                            bbox=FakeBBox(l=20, t=80, r=220, b=110),
                            charspan=[0, 11],
                        )
                    ],
                ),
                1,
            ),
            (
                FakeItem(
                    label=Label.TEXT,
                    text="Compete à entidade X autorizar a medida.",
                    prov=[
                        FakeProvenance(
                            page_no=2,
                            bbox=FakeBBox(l=20, t=120, r=500, b=180),
                            charspan=[0, 42],
                        )
                    ],
                ),
                2,
            ),
        ]
    )

    blocks = build_evidence_blocks(
        document=document,
        source_id="source:abc123",
        version_hash="a" * 64,
    )

    assert len(blocks) == 3
    text_block = blocks[2]
    assert text_block.pdf_page == 2
    assert text_block.block_type == "text"
    assert text_block.section_path == ["Regulamento de teste", "Artigo 12.º"]
    assert text_block.bbox is not None
    assert text_block.bbox.model_dump() == {
        "x0": 20.0,
        "y0": 120.0,
        "x1": 500.0,
        "y1": 180.0,
    }


def test_provenance_charspan_splits_multi_page_text():
    text = "Primeira passagem. Segunda passagem."
    document = FakeDocument(
        [
            (
                FakeItem(
                    label=Label.TEXT,
                    text=text,
                    prov=[
                        FakeProvenance(
                            page_no=1,
                            bbox=FakeBBox(l=1, t=1, r=100, b=20),
                            charspan=[0, 18],
                        ),
                        FakeProvenance(
                            page_no=2,
                            bbox=FakeBBox(l=1, t=1, r=100, b=20),
                            charspan=[19, len(text)],
                        ),
                    ],
                ),
                1,
            )
        ]
    )

    blocks = build_evidence_blocks(
        document=document,
        source_id="source:abc123",
        version_hash="b" * 64,
    )

    assert [block.pdf_page for block in blocks] == [1, 2]
    assert [block.raw_text for block in blocks] == [
        "Primeira passagem.",
        "Segunda passagem.",
    ]


def test_table_markdown_is_used_when_item_has_no_text_attribute():
    document = FakeDocument(
        [
            (
                FakeTableItem(
                    markdown="| Campo | Valor |\n| --- | --- |\n| Prazo | 24 horas |",
                    prov=[
                        FakeProvenance(
                            page_no=3,
                            bbox=FakeBBox(l=20, t=200, r=520, b=400),
                            charspan=[0, 0],
                        )
                    ],
                ),
                1,
            )
        ]
    )

    blocks = build_evidence_blocks(
        document=document,
        source_id="source:abc123",
        version_hash="c" * 64,
    )

    assert len(blocks) == 1
    assert blocks[0].block_type == "table"
    assert "24 horas" in blocks[0].raw_text
    assert blocks[0].pdf_page == 3


def test_items_without_provenance_are_preserved_but_not_given_a_fake_page():
    document = FakeDocument(
        [(FakeItem(label=Label.TEXT, text="Texto sem página.", prov=[]), 1)]
    )

    blocks = build_evidence_blocks(
        document=document,
        source_id="source:abc123",
        version_hash="d" * 64,
    )

    assert len(blocks) == 1
    assert blocks[0].pdf_page is None
    assert blocks[0].bbox is None
