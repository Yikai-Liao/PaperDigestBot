"""
Tests for the render.py module.

This module tests the markdown to Telegram conversion functionality,
message validation, and the complete rendering pipeline using real test data.
"""

import pytest
import polars as pl
import os
from unittest.mock import patch, MagicMock
from src.render import (
    markdown_to_telegram,
    escape_telegram_markdown,
    validate_telegram_message,
    render_summary_tg
)


class TestMarkdownToTelegram:
    """Test the markdown to Telegram conversion functionality."""

    def test_basic_markdown_conversion(self):
        """Test basic markdown formatting conversion."""
        # Test bold conversion
        text = "This is **bold** text"
        result = markdown_to_telegram(text)
        assert "**" not in result
        assert "bold" in result

    def test_italic_conversion(self):
        """Test italic formatting conversion."""
        text = "This is *italic* text"
        result = markdown_to_telegram(text)
        assert result == "This is italic text"

    def test_link_conversion(self):
        """Test link formatting conversion."""
        text = "Check out [this link](https://example.com)"
        result = markdown_to_telegram(text)
        assert "[" not in result and "]" not in result
        assert "this link (https://example.com)" in result

    def test_complex_markdown(self):
        """Test complex markdown with multiple formatting types."""
        text = "**Bold** and *italic* with [link](https://test.com) and `code`"
        result = markdown_to_telegram(text)
        # Should remove all markdown characters
        assert "**" not in result
        assert "*" not in result
        assert "[" not in result
        assert "]" not in result
        assert "`" not in result
        assert "Bold and italic with link (https://test.com) and code" in result

    def test_problematic_characters(self):
        """Test handling of characters that could cause Telegram parsing issues."""
        text = "Text with ~strikethrough~ and `backticks`"
        result = markdown_to_telegram(text)
        assert "~" not in result
        assert "`" not in result

    def test_error_handling(self):
        """Test error handling in markdown conversion with malformed regex patterns."""
        # Test with extremely long text that might cause regex issues
        very_long_text = "**" + "a" * 10000 + "**"
        result = markdown_to_telegram(very_long_text)
        assert isinstance(result, str)
        assert len(result) > 0


class TestEscapeTelegramMarkdown:
    """Test the Telegram markdown escaping functionality."""

    def test_escape_special_characters(self):
        """Test escaping of special Telegram markdown characters."""
        text = "Text with * and _ and [ and ]"
        result = escape_telegram_markdown(text)
        assert "\\*" in result
        assert "\\_" in result
        assert "\\[" in result
        assert "\\]" in result

    def test_escape_all_special_chars(self):
        """Test escaping of all special characters."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        text = "".join(special_chars)
        result = escape_telegram_markdown(text)
        for char in special_chars:
            assert f"\\{char}" in result


class TestValidateTelegramMessage:
    """Test the Telegram message validation functionality."""

    def test_valid_message(self):
        """Test validation of a valid message."""
        text = "This is a valid message with emojis 📜 and text"
        is_valid, cleaned_text = validate_telegram_message(text)
        assert is_valid is True
        assert cleaned_text == text

    def test_message_too_long(self):
        """Test handling of messages that exceed Telegram's character limit."""
        text = "a" * 5000  # Exceeds 4096 character limit
        is_valid, cleaned_text = validate_telegram_message(text)
        assert is_valid is True
        assert len(cleaned_text) <= 4096
        assert cleaned_text.endswith("...")

    def test_empty_message(self):
        """Test handling of empty messages."""
        is_valid, error_msg = validate_telegram_message("")
        assert is_valid is False
        assert "Empty message" in error_msg

    def test_whitespace_only_message(self):
        """Test handling of whitespace-only messages."""
        is_valid, error_msg = validate_telegram_message("   \n\t   ")
        assert is_valid is False
        assert "Empty message" in error_msg

    def test_problematic_characters_removal(self):
        """Test removal of problematic characters."""
        text = "Text with\x00null and\rcarriage return"
        is_valid, cleaned_text = validate_telegram_message(text)
        assert is_valid is True
        assert "\x00" not in cleaned_text
        assert "\r" not in cleaned_text

    def test_validation_with_unicode_characters(self):
        """Test validation with unicode characters and emojis."""
        text = "Message with unicode: 📜 🌟 ✨ and special chars: àáâãäå"
        is_valid, cleaned_text = validate_telegram_message(text)
        assert is_valid is True
        assert "📜" in cleaned_text
        assert "àáâãäå" in cleaned_text


class TestRenderSummaryTg:
    """Test the complete rendering pipeline using real test data."""

    @pytest.fixture
    def test_data(self):
        """Load test data from the parquet file."""
        test_file = "tests/data/summarized.parquet"
        if not os.path.exists(test_file):
            pytest.skip(f"Test data file {test_file} not found")
        return pl.read_parquet(test_file)

    def test_render_with_real_data(self, test_data):
        """Test rendering with real test data."""
        # Take first row for testing
        single_row_df = test_data.head(1)

        with patch('src.render.logger') as mock_logger:
            result = render_summary_tg(single_row_df)

            # Should return a dictionary
            assert isinstance(result, dict)
            assert len(result) == 1

            # Should have the paper ID as key
            paper_id = single_row_df['id'][0]
            assert paper_id in result

            # Should contain expected content
            rendered_text = result[paper_id]
            assert isinstance(rendered_text, str)
            assert len(rendered_text) > 0

            # Should contain emojis from template
            assert "📜" in rendered_text
            assert "📌" in rendered_text
            assert "👥" in rendered_text

    def test_render_multiple_papers(self, test_data):
        """Test rendering multiple papers."""
        # Take first 3 rows
        multi_row_df = test_data.head(3)

        result = render_summary_tg(multi_row_df)

        # Should return correct number of results
        assert len(result) == 3

        # Each result should be valid
        for paper_id, rendered_text in result.items():
            assert isinstance(rendered_text, str)
            assert len(rendered_text) > 0
            assert "📜" in rendered_text

    def test_render_with_missing_fields(self):
        """Test rendering with missing or None fields."""
        # Create test data with missing fields
        test_df = pl.DataFrame({
            'id': ['test_paper'],
            'title': ['Test Title'],
            'authors': [None],  # Missing authors
            'institution': [[]],  # Empty institution
            'keywords': [None],  # Missing keywords
            'score': [None],  # Missing score
            # Missing other required fields
        })

        result = render_summary_tg(test_df)

        assert len(result) == 1
        assert 'test_paper' in result
        rendered_text = result['test_paper']

        # Should handle missing fields gracefully
        assert "N/A" in rendered_text  # Should show N/A for missing fields
        assert "Test Title" in rendered_text  # Should show available title

    def test_render_with_malformed_data(self):
        """Test rendering with malformed data that could cause issues."""
        # Create test data with potentially problematic content
        test_df = pl.DataFrame({
            'id': ['malformed_paper'],
            'title': ['Title with **markdown** and *formatting*'],
            'authors': [['Author with\x00null', 'Author\rwith\rcarriage']],
            'institution': [['Institution with special chars: [](){}']],
            'keywords': [['keyword-with-dashes', 'keyword with spaces']],
            'score': [0.85],
            'one_sentence_summary': ['Summary with problematic chars\x00\r'],
            'problem_background': ['Background'],
            'method': ['Method'],
            'experiment': ['Experiment'],
            'further_thoughts': ['Thoughts'],
            'updated': ['2024-01-01'],
            'model': ['test-model']
        })

        result = render_summary_tg(test_df)

        assert len(result) == 1
        assert 'malformed_paper' in result
        rendered_text = result['malformed_paper']

        # Should clean problematic characters
        assert '\x00' not in rendered_text
        assert '\r' not in rendered_text

        # Should format keywords properly
        assert '#keywordwithdashes' in rendered_text
        assert '#keywordwithspaces' in rendered_text

    def test_render_error_handling(self):
        """Test error handling in the rendering process."""
        # Create invalid DataFrame
        invalid_df = pl.DataFrame({'invalid': ['data']})

        with patch('src.render.logger') as mock_logger:
            result = render_summary_tg(invalid_df)

            # Should return fallback message
            assert len(result) == 1
            rendered_text = list(result.values())[0]
            assert "渲染错误" in rendered_text

            # Should log error
            mock_logger.error.assert_called()

    def test_template_rendering_error(self, test_data):
        """Test handling of template rendering errors."""
        single_row_df = test_data.head(1)

        # Mock template to raise an error
        with patch('jinja2.Environment') as mock_env:
            mock_template = MagicMock()
            mock_template.render.side_effect = Exception("Template error")
            mock_env.return_value.get_template.return_value = mock_template

            with patch('src.render.logger') as mock_logger:
                result = render_summary_tg(single_row_df)

                # Should return fallback message
                assert len(result) == 1
                rendered_text = list(result.values())[0]
                assert "渲染错误" in rendered_text

                # Should log error
                mock_logger.error.assert_called()

    def test_authors_and_institutions_formatting(self, test_data):
        """Test proper formatting of authors and institutions lists."""
        single_row_df = test_data.head(1)
        result = render_summary_tg(single_row_df)

        rendered_text = list(result.values())[0]

        # Should not have character-by-character breakdown
        assert ", '" not in rendered_text  # This was the bug we fixed
        assert "', ," not in rendered_text

        # Should have proper author formatting
        lines = rendered_text.split('\n')
        author_line = next((line for line in lines if line.startswith('👥 作者:')), None)
        assert author_line is not None

        # Authors should be properly joined with commas
        if "N/A" not in author_line:
            # Should contain actual author names, not character breakdown
            assert len(author_line.split(', ')) >= 1
            # Should not contain single characters separated by commas
            author_part = author_line.replace('👥 作者: ', '')
            if author_part != "N/A":
                authors = author_part.split(', ')
                for author in authors:
                    assert len(author.strip()) > 1  # Each author should be more than 1 character


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
