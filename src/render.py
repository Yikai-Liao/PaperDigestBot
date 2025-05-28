import re

import jinja2
import polars as pl
from loguru import logger


# Markdown to Telegram format conversion utility
def escape_telegram_markdown(text):
    """
    Escape special characters for Telegram MarkdownV2 format.
    """
    # Characters that need to be escaped in MarkdownV2
    special_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]

    for char in special_chars:
        text = text.replace(char, f"\\{char}")

    return text


def markdown_to_telegram(md_text):
    """
    Convert Markdown text to a format compatible with Telegram.
    Uses plain text format to avoid markdown parsing issues.

    Args:
        md_text (str): Markdown text to convert. Should always be a string.

    Returns:
        str: Plain text suitable for Telegram
    """
    try:
        # Simple and fast approach: just remove all markdown characters
        # This avoids complex regex that could cause performance issues

        # Remove markdown bold (**text**)
        formatted_text = md_text.replace("**", "")

        # Remove markdown italic (*text*)
        formatted_text = formatted_text.replace("*", "")

        # Remove markdown links [text](url) -> text (url)
        formatted_text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", formatted_text)

        # Remove remaining problematic characters
        chars_to_remove = ["~", "[", "]", "`"]
        for char in chars_to_remove:
            formatted_text = formatted_text.replace(char, "")

        return formatted_text

    except Exception as e:
        logger.error(f"Error converting markdown to telegram format: {e}")
        # Return plain text without any formatting as fallback
        try:
            return re.sub(r"[*_`~\[\]()]", "", str(md_text))
        except:
            logger.error(
                f"Critical error in markdown_to_telegram fallback with input: {type(md_text)}"
            )
            return "Error processing text"


def validate_telegram_message(text):
    """
    Validate that a message is safe to send to Telegram.
    Returns (is_valid, cleaned_text)
    """
    try:
        # Check message length (Telegram limit is 4096 characters)
        if len(text) > 4096:
            logger.warning(f"Message too long ({len(text)} chars), truncating")
            text = text[:4090] + "..."

        # Remove any null characters or other problematic characters
        text = text.replace("\x00", "").replace("\r", "")

        # Ensure the message is not empty
        if not text.strip():
            return False, "Empty message"

        return True, text

    except Exception as e:
        logger.error(f"Error validating telegram message: {e}")
        return False, str(e)


def render_summary_tg(df: pl.DataFrame) -> dict[str, str]:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("config"))
    template = env.get_template("summary.tg.j2")
    data = df.to_dicts()
    result = {}
    for row in data:
        try:
            # Safely handle keywords
            if "keywords" in row and row["keywords"]:
                row["keywords"] = [
                    f'#{key.replace(" ", "").replace("-", "")}' for key in row["keywords"] if key
                ]
            else:
                row["keywords"] = []

            # Safely handle score
            if "score" in row and row["score"] is not None:
                row["score"] = f"{row['score'] * 100:.2f}"
            else:
                row["score"] = "N/A"

            # Ensure all required fields have safe values
            safe_row = {}

            # Handle list fields specially (authors, institution)
            list_fields = ["authors", "institution"]
            for field in list_fields:
                if field in row and row[field] is not None:
                    if isinstance(row[field], list):
                        # Clean each item in the list
                        cleaned_list = []
                        for item in row[field]:
                            if item:
                                cleaned_item = (
                                    str(item).replace("\x00", "").replace("\r", "").strip()
                                )
                                if cleaned_item:
                                    cleaned_list.append(cleaned_item)
                        safe_row[field] = cleaned_list
                    else:
                        # If it's not a list, convert to string and clean
                        value = str(row[field]).replace("\x00", "").replace("\r", "").strip()
                        safe_row[field] = [value] if value else []
                else:
                    safe_row[field] = []

            # Handle string fields
            string_fields = [
                "title",
                "one_sentence_summary",
                "problem_background",
                "method",
                "experiment",
                "further_thoughts",
                "updated",
                "model",
            ]
            for field in string_fields:
                if field in row and row[field] is not None:
                    # Convert to string and clean up
                    value = str(row[field])
                    # Remove any problematic characters
                    value = value.replace("\x00", "").replace("\r", "").strip()
                    safe_row[field] = value if value else "N/A"
                else:
                    safe_row[field] = "N/A"

            # Add the processed fields
            safe_row["keywords"] = row["keywords"]
            safe_row["score"] = row["score"]
            safe_row["id"] = row.get("id", "unknown")

            rendered = template.render(**safe_row)

            # Escape for MarkdownV2 format and validate
            telegram_text = escape_telegram_markdown(rendered)
            is_valid, validated_text = validate_telegram_message(telegram_text)

            if is_valid:
                result[row["id"]] = validated_text
                logger.debug(
                    f"Successfully rendered message for paper {row['id']} (length: {len(validated_text)})"
                )
            else:
                logger.error(f"Invalid message for paper {row['id']}: {validated_text}")
                logger.debug(
                    f"Original rendered content: {rendered[:500]}..."
                )  # Log first 500 chars for debugging
                # Create a simple fallback message
                result[row["id"]] = (
                    f"📜 {row.get('title', 'Unknown Title')}\n\n❌ 消息格式错误，请联系管理员"
                )

        except Exception as e:
            logger.error(f"Error rendering summary for paper {row.get('id', 'unknown')}: {e}")
            # Create a simple fallback message
            result[row.get("id", "unknown")] = "📜 论文摘要\n\n❌ 渲染错误，请联系管理员"

    return result
