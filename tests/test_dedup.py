"""Tests for content deduplication across documentation files."""

import os
import tempfile

from click.testing import CliRunner

from dograpper.utils.dedup import (
    _split_blocks,
    _normalize,
    _simhash,
    _hamming_distance,
    deduplicate,
    MIN_BLOCK_WORDS,
)
from dograpper.commands.pack import pack


# ---------------------------------------------------------------------------
# _split_blocks
# ---------------------------------------------------------------------------

class TestSplitBlocks:

    def test_splits_by_double_newline(self):
        text = "Primeiro parágrafo.\n\nSegundo parágrafo.\n\nTerceiro."
        blocks = _split_blocks(text)
        assert len(blocks) == 3
        assert blocks[0] == "Primeiro parágrafo."
        assert blocks[1] == "Segundo parágrafo."
        assert blocks[2] == "Terceiro."

    def test_strips_whitespace(self):
        text = "  Bloco com espaços  \n\n  Outro bloco  "
        blocks = _split_blocks(text)
        assert blocks[0] == "Bloco com espaços"
        assert blocks[1] == "Outro bloco"

    def test_ignores_empty_blocks(self):
        text = "Bloco real\n\n\n\n\n\nOutro bloco"
        blocks = _split_blocks(text)
        assert len(blocks) == 2

    def test_single_block(self):
        text = "Uma única linha de texto."
        blocks = _split_blocks(text)
        assert len(blocks) == 1

    def test_empty_text(self):
        assert _split_blocks("") == []


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------

class TestNormalize:

    def test_lowercases(self):
        assert "hello world" in _normalize("Hello World")

    def test_collapses_whitespace(self):
        result = _normalize("hello   world\t\nnewline")
        assert result == "hello world newline"

    def test_strips(self):
        assert _normalize("  text  ") == "text"

    def test_empty(self):
        assert _normalize("") == ""


# ---------------------------------------------------------------------------
# _simhash and _hamming_distance
# ---------------------------------------------------------------------------

class TestSimhash:

    def test_identical_texts_same_hash(self):
        text = "the quick brown fox jumps over the lazy dog near the river"
        assert _simhash(text) == _simhash(text)

    def test_similar_texts_close_hash(self):
        text1 = "the quick brown fox jumps over the lazy dog near the river bank"
        text2 = "the quick brown fox jumps over the lazy cat near the river bank"
        h1 = _simhash(text1)
        h2 = _simhash(text2)
        distance = _hamming_distance(h1, h2)
        # Similar texts should be closer than completely different texts
        text3 = "classical music composed by beethoven in the eighteenth century europe"
        h3 = _simhash(text3)
        distance_different = _hamming_distance(h1, h3)
        assert distance < distance_different

    def test_different_texts_distant_hash(self):
        text1 = "python programming language used for web development and automation"
        text2 = "classical music composed by beethoven in the eighteenth century europe"
        h1 = _simhash(text1)
        h2 = _simhash(text2)
        distance = _hamming_distance(h1, h2)
        assert distance > 10

    def test_short_text_does_not_crash(self):
        h = _simhash("ab")
        assert isinstance(h, int)

    def test_returns_integer(self):
        assert isinstance(_simhash("some text for hashing purposes here"), int)


class TestHammingDistance:

    def test_identical(self):
        assert _hamming_distance(42, 42) == 0

    def test_one_bit_diff(self):
        assert _hamming_distance(0b1010, 0b1011) == 1

    def test_all_bits_diff(self):
        assert _hamming_distance(0, 0xFF) == 8

    def test_symmetric(self):
        assert _hamming_distance(123, 456) == _hamming_distance(456, 123)


# ---------------------------------------------------------------------------
# deduplicate — exact mode
# ---------------------------------------------------------------------------

class TestDeduplicateExact:

    def test_removes_identical_blocks(self):
        texts = {
            "a.txt": "Unique content in file A with enough words to pass the minimum.\n\nShared block that appears in both files with enough words.",
            "b.txt": "Unique content in file B with enough words to pass the minimum.\n\nShared block that appears in both files with enough words.",
        }
        result = deduplicate(texts, mode="exact")
        assert "Shared block" in result.texts["a.txt"]
        assert "Shared block" not in result.texts["b.txt"]
        assert "Unique content in file A" in result.texts["a.txt"]
        assert "Unique content in file B" in result.texts["b.txt"]

    def test_stats_exact(self):
        texts = {
            "a.txt": "Block one with enough words for dedup minimum threshold to be met properly.\n\nBlock two with enough words for dedup minimum threshold to be met properly.",
            "b.txt": "Block one with enough words for dedup minimum threshold to be met properly.\n\nSomething completely different with enough words here and there for testing.",
        }
        result = deduplicate(texts, mode="exact")
        assert result.stats.blocks_removed_exact == 1
        assert result.stats.blocks_removed_fuzzy == 0

    def test_preserves_first_occurrence(self):
        texts = {
            "z_last.txt": "Repeated block with enough words to meet the minimum word count.\n\nAnother block with words.",
            "a_first.txt": "Repeated block with enough words to meet the minimum word count.\n\nDifferent block with words.",
        }
        result = deduplicate(texts, mode="exact")
        assert "Repeated block" in result.texts["a_first.txt"]
        assert "Repeated block" not in result.texts["z_last.txt"]

    def test_ignores_short_blocks(self):
        short_block = "Short block."  # < 10 words
        texts = {
            "a.txt": f"{short_block}\n\nLonger content with enough words for testing purposes.",
            "b.txt": f"{short_block}\n\nDifferent longer content with enough words for testing.",
        }
        result = deduplicate(texts, mode="exact")
        assert short_block in result.texts["a.txt"]
        assert short_block in result.texts["b.txt"]

    def test_case_insensitive_match(self):
        texts = {
            "a.txt": "This Block Has Mixed Case and enough words for dedup threshold.",
            "b.txt": "this block has mixed case and enough words for dedup threshold.",
        }
        result = deduplicate(texts, mode="exact")
        assert result.stats.blocks_removed_exact == 1

    def test_no_duplicates_no_removal(self):
        texts = {
            "a.txt": "Completely unique content in file A with enough words to pass.",
            "b.txt": "Totally different content in file B with enough words to pass.",
        }
        result = deduplicate(texts, mode="exact")
        assert result.stats.blocks_removed == 0

    def test_multiple_duplicates(self):
        shared_1 = "First shared block with enough words for the minimum threshold."
        shared_2 = "Second shared block also with enough words for the minimum threshold."
        texts = {
            "a.txt": f"{shared_1}\n\n{shared_2}\n\nUnique A content with enough words.",
            "b.txt": f"{shared_1}\n\nUnique B content with enough words for testing.",
            "c.txt": f"{shared_2}\n\nUnique C content with enough words for testing.",
        }
        result = deduplicate(texts, mode="exact")
        assert result.stats.blocks_removed_exact == 2


# ---------------------------------------------------------------------------
# deduplicate — fuzzy mode
# ---------------------------------------------------------------------------

class TestDeduplicateFuzzy:

    def test_removes_near_duplicates(self):
        texts = {
            "a.txt": "This feature was introduced in version 2.0 and provides comprehensive API access for all registered users of the platform.",
            "b.txt": "This feature was introduced in version 3.0 and provides comprehensive API access for all registered users of the platform.",
        }
        result = deduplicate(texts, mode="fuzzy", hamming_threshold=10)
        assert result.stats.blocks_removed_fuzzy == 1

    def test_does_not_remove_different_blocks(self):
        texts = {
            "a.txt": "Python is a programming language used for web development and automation tasks.",
            "b.txt": "Beethoven composed classical symphonies in Vienna during the eighteenth century in Europe.",
        }
        result = deduplicate(texts, mode="fuzzy")
        assert result.stats.blocks_removed_fuzzy == 0

    def test_threshold_zero_is_exact_only(self):
        texts = {
            "a.txt": "Almost the same block of text here with enough words for testing purposes.",
            "b.txt": "Almost the same block of text here with enough words for testing purpose.",
        }
        result = deduplicate(texts, mode="fuzzy", hamming_threshold=0)
        assert result.stats.blocks_removed_fuzzy == 0

    def test_high_threshold_aggressive(self):
        texts = {
            "a.txt": "Configuration guide for setting up the application server with default parameters and options.",
            "b.txt": "Configuration manual for deploying the application server with custom parameters and settings.",
        }
        result_conservative = deduplicate(texts, mode="fuzzy", hamming_threshold=1)
        result_aggressive = deduplicate(texts, mode="fuzzy", hamming_threshold=15)
        assert result_aggressive.stats.blocks_removed_fuzzy >= result_conservative.stats.blocks_removed_fuzzy


# ---------------------------------------------------------------------------
# deduplicate — both mode
# ---------------------------------------------------------------------------

class TestDeduplicateBoth:

    def test_both_applies_exact_and_fuzzy(self):
        exact_dup = "Exact duplicate block with enough words to pass the minimum threshold for dedup."
        texts = {
            "a.txt": f"{exact_dup}\n\nThis feature was released in version 1.0 with full support for all platforms.",
            "b.txt": f"{exact_dup}\n\nThis feature was released in version 2.0 with full support for all platforms.",
        }
        result = deduplicate(texts, mode="both")
        assert result.stats.blocks_removed_exact >= 1
        assert result.stats.blocks_removed >= 1

    def test_exact_runs_before_fuzzy(self):
        dup = "Identical block in both files with enough words for the minimum threshold."
        texts = {
            "a.txt": dup,
            "b.txt": dup,
        }
        result = deduplicate(texts, mode="both")
        assert result.stats.blocks_removed_exact == 1
        assert result.stats.blocks_removed_fuzzy == 0


# ---------------------------------------------------------------------------
# deduplicate — edge cases
# ---------------------------------------------------------------------------

class TestDeduplicateEdgeCases:

    def test_empty_texts(self):
        result = deduplicate({})
        assert result.texts == {}
        assert result.stats.blocks_removed == 0

    def test_single_file_internal_dedup(self):
        texts = {
            "only.txt": "Block one with enough words to pass the minimum threshold for dedup.\n\nBlock one with enough words to pass the minimum threshold for dedup.",
        }
        result = deduplicate(texts, mode="exact")
        assert result.stats.blocks_removed_exact == 1

    def test_all_blocks_identical(self):
        block = "Repeated content across all files with enough words for dedup."
        texts = {
            "a.txt": block,
            "b.txt": block,
            "c.txt": block,
        }
        result = deduplicate(texts, mode="exact")
        assert result.stats.blocks_removed_exact == 2
        assert "Repeated content" in result.texts["a.txt"]

    def test_unicode_content(self):
        texts = {
            "pt.txt": "Documentação em português com acentuação: é, ã, ç, ñ e palavras suficientes.",
            "pt2.txt": "Documentação em português com acentuação: é, ã, ç, ñ e palavras suficientes.",
        }
        result = deduplicate(texts, mode="exact")
        assert result.stats.blocks_removed_exact == 1

    def test_deterministic_output(self):
        texts = {
            "b.txt": "Second file block with enough words for testing purposes here.\n\nShared block present in both files with enough words.",
            "a.txt": "First file block with enough words for testing purposes here.\n\nShared block present in both files with enough words.",
        }
        r1 = deduplicate(texts, mode="exact")
        r2 = deduplicate(texts, mode="exact")
        assert r1.texts == r2.texts
        assert r1.stats.blocks_removed_exact == r2.stats.blocks_removed_exact

    def test_words_removed_count(self):
        block = "This is a shared block containing exactly twelve words for testing."  # 11 words
        texts = {
            "a.txt": block,
            "b.txt": block,
        }
        result = deduplicate(texts, mode="exact")
        assert result.stats.words_removed == len(block.split())


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestDeduplicateCLI:

    def _create_files_with_shared_content(self, tmp_dir):
        input_dir = os.path.join(tmp_dir, "input")
        os.makedirs(input_dir)

        shared = "This block of important documentation text appears in multiple pages across the entire site and contains enough words to pass the minimum dedup threshold for testing."

        with open(os.path.join(input_dir, "page_a.txt"), "w") as f:
            f.write(
                f"Unique content for page A with enough context and words.\n\n{shared}"
            )
        with open(os.path.join(input_dir, "page_b.txt"), "w") as f:
            f.write(
                f"Unique content for page B with different text and words.\n\n{shared}"
            )
        return input_dir

    def test_dedup_off_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = self._create_files_with_shared_content(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", output_dir,
            ])

            assert result.exit_code == 0
            assert "dedup" not in result.output.lower()

    def test_dedup_exact_via_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = self._create_files_with_shared_content(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", output_dir, "--dedup", "exact",
            ])

            assert result.exit_code == 0

    def test_dedup_with_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = self._create_files_with_shared_content(tmp)

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", os.path.join(tmp, "out"),
                "--dedup", "both", "--dry-run",
            ])

            assert result.exit_code == 0
            assert not os.path.exists(os.path.join(tmp, "out"))

    def test_dedup_reduces_word_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = self._create_files_with_shared_content(tmp)

            runner = CliRunner()

            out_no_dedup = os.path.join(tmp, "no_dedup")
            runner.invoke(pack, [input_dir, "-o", out_no_dedup])

            out_dedup = os.path.join(tmp, "with_dedup")
            runner.invoke(pack, [input_dir, "-o", out_dedup, "--dedup", "exact"])

            def total_words(path):
                total = 0
                for f in os.listdir(path):
                    with open(os.path.join(path, f)) as fh:
                        total += len(fh.read().split())
                return total

            words_no_dedup = total_words(out_no_dedup)
            words_dedup = total_words(out_dedup)
            assert words_dedup < words_no_dedup

    def test_pack_without_dedup_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = self._create_files_with_shared_content(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [input_dir, "-o", output_dir])

            assert result.exit_code == 0
            assert os.path.exists(output_dir)
            assert len(os.listdir(output_dir)) > 0
