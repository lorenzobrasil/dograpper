import pytest
import json
from dograpper.utils.heading_extractor import Heading, format_context_header


class TestContextV1Header:
    """Testa o novo formato dograpper-context-v1."""

    def test_basic_header(self):
        """Header básico com source e breadcrumb."""
        headings = [Heading(1, "Guide", 0), Heading(2, "Install", 100)]
        header = format_context_header(
            active_headings=headings,
            source_path="docs/guide/install.html",
        )
        assert "<!-- dograpper-context-v1" in header
        assert "-->" in header
        # Parse JSON
        json_str = header.split("<!-- dograpper-context-v1\n")[1].split("\n-->")[0]
        data = json.loads(json_str)
        assert data["source"] == "docs/guide/install.html"
        assert data["context_breadcrumb"] == ["Guide", "Install"]
        assert data["schema_version"] == "v1"

    def test_with_chunk_position(self):
        """chunk_index/total_chunks presentes quando split."""
        header = format_context_header(
            active_headings=[Heading(1, "API", 0)],
            source_path="api.html",
            chunk_index=2,
            total_chunks=5,
        )
        data = json.loads(header.split("<!-- dograpper-context-v1\n")[1].split("\n-->")[0])
        assert data["chunk_index"] == 2
        assert data["total_chunks"] == 5

    def test_single_chunk_omits_position(self):
        """Arquivo não splitado omite chunk_index/total_chunks."""
        header = format_context_header(
            active_headings=[Heading(1, "Title", 0)],
            source_path="page.html",
            chunk_index=1,
            total_chunks=1,
        )
        data = json.loads(header.split("<!-- dograpper-context-v1\n")[1].split("\n-->")[0])
        assert "chunk_index" not in data
        assert "total_chunks" not in data

    def test_with_url(self):
        """URL inclusa quando disponível."""
        header = format_context_header(
            active_headings=[],
            source_path="page.html",
            url="https://example.com/page.html",
        )
        data = json.loads(header.split("<!-- dograpper-context-v1\n")[1].split("\n-->")[0])
        assert data["url"] == "https://example.com/page.html"

    def test_with_word_count(self):
        """word_count incluso."""
        header = format_context_header(
            active_headings=[Heading(1, "T", 0)],
            source_path="p.html",
            word_count=4820,
        )
        data = json.loads(header.split("<!-- dograpper-context-v1\n")[1].split("\n-->")[0])
        assert data["word_count"] == 4820

    def test_with_readiness(self):
        """llm_readiness incluso quando --score ativo."""
        header = format_context_header(
            active_headings=[Heading(1, "T", 0)],
            source_path="p.html",
            readiness={"score": 0.92, "grade": "A", "noise_ratio": 0.08},
        )
        data = json.loads(header.split("<!-- dograpper-context-v1\n")[1].split("\n-->")[0])
        assert data["llm_readiness"]["grade"] == "A"

    def test_no_headings_omits_breadcrumb(self):
        """Sem headings, context_breadcrumb omitido."""
        header = format_context_header(
            active_headings=[],
            source_path="readme.txt",
        )
        data = json.loads(header.split("<!-- dograpper-context-v1\n")[1].split("\n-->")[0])
        assert "context_breadcrumb" not in data

    def test_empty_returns_empty(self):
        """Sem source nem headings → string vazia."""
        header = format_context_header(active_headings=[])
        assert header == ""

    def test_json_is_parseable(self):
        """JSON extraído do header é válido."""
        header = format_context_header(
            active_headings=[Heading(1, "A", 0), Heading(2, "B", 50), Heading(3, "C", 100)],
            source_path="deep/nested/page.html",
            chunk_index=3,
            total_chunks=7,
            word_count=3200,
            url="https://example.com/deep/nested/page.html",
            readiness={"score": 0.75, "grade": "B", "noise_ratio": 0.15},
        )
        json_str = header.split("<!-- dograpper-context-v1\n")[1].split("\n-->")[0]
        data = json.loads(json_str)  # Não deve lançar exceção
        assert len(data["context_breadcrumb"]) == 3
        assert data["schema_version"] == "v1"
