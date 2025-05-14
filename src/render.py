import polars as pl
import jinja2

# Markdown to Telegram format conversion utility
def markdown_to_telegram(md_text):
    """
    Convert Markdown text to a format compatible with Telegram.
    This is a basic implementation and can be enhanced based on specific formatting needs.
    """
    # Replace Markdown bold (**text**) with Telegram bold (*text*)
    formatted_text = md_text.replace('**', '*')
    # Replace Markdown italic (_text_) with Telegram italic (_text_)
    # Already compatible, no change needed for italic
    # Replace Markdown links ([text](url)) with Telegram links (text (url))
    import re
    formatted_text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', formatted_text)
    return formatted_text

def render_summary_tg(df: pl.DataFrame) -> dict[str, str]:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader('config'))
    template = env.get_template('summary.tg.j2')
    data = df.to_dicts()
    result = {}
    for row in data:
        row['keywords'] = [
            f'#{key.replace(" ", "").replace("-", "")}'
            for key in row['keywords']
        ]
        row['score'] = f"{row['score'] * 100:.2f}"
        rendered = template.render(**row)
        result[row['id']] = markdown_to_telegram(rendered)
    return result