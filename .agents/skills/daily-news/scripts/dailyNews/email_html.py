"""Render saved Markdown with inline styles for HTML email clients."""

from html import escape

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML


STYLES = {
    'h1': 'font-size:26px;line-height:1.4;margin:0 0 24px;font-weight:700;',
    'h2': 'font-size:21px;line-height:1.5;margin:30px 0 16px;font-weight:700;',
    'h3': 'font-size:18px;line-height:1.5;margin:24px 0 12px;font-weight:700;',
    'h4': 'font-size:17px;margin:20px 0 10px;font-weight:700;',
    'h5': 'font-size:16px;margin:20px 0 10px;font-weight:700;',
    'h6': 'font-size:16px;margin:20px 0 10px;font-weight:700;',
    'p': 'margin:0 0 16px;',
    'a': 'color:#1264a3;text-decoration:underline;word-break:break-word;',
    'strong': 'font-weight:700;',
    'ul': 'margin:0 0 18px;padding-left:26px;',
    'ol': 'margin:0 0 18px;padding-left:26px;',
    'li': 'margin:0 0 8px;',
    'blockquote': 'margin:16px 0;padding:8px 16px;border-left:4px solid #cbd5e1;color:#475569;',
    'table': 'width:100%;table-layout:fixed;border-collapse:collapse;margin:16px 0;',
    'th': 'border:1px solid #cbd5e1;padding:8px;text-align:left;background-color:#f1f5f9;',
    'td': 'border:1px solid #cbd5e1;padding:8px;vertical-align:top;',
    'code': 'font-family:Consolas,monospace;font-size:14px;background-color:#f1f5f9;padding:2px 4px;',
    'pre': 'margin:16px 0;padding:14px;background-color:#f1f5f9;white-space:pre-wrap;word-break:break-word;font-size:14px;line-height:1.6;',
    'img': 'max-width:100%;height:auto;border:0;',
    'hr': 'border:0;border-top:1px solid #e2e8f0;margin:24px 0;',
}


class EmailRenderer(RendererHTML):
    def renderAttrs(self, token):
        style = STYLES.get(token.tag)
        if style and token.nesting != -1:
            # Keep Markdown table alignment after the default cell styles.
            token.attrSet('style', style + (token.attrGet('style') or ''))
        return super().renderAttrs(token)

    def code_block(self, tokens, idx, options, env):
        return (f'<pre style="{STYLES["pre"]}"><code>'
                + escape(tokens[idx].content) + '</code></pre>\n')

    fence = code_block


def render_report_html(report, *, title='每日早报'):
    parser = MarkdownIt('commonmark', {'html': False, 'breaks': True},
                        renderer_cls=EmailRenderer).enable(['table', 'strikethrough'])
    body = parser.render(report)
    return (
        '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{escape(title)}</title></head>'
        '<body style="margin:0;padding:0;background-color:#ffffff;">'
        '<div style="max-width:720px;margin:0 auto;padding:24px 18px;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Microsoft YaHei,Arial,sans-serif;'
        'font-size:16px;line-height:1.8;color:#1f2937;overflow-wrap:break-word;">'
        + body + '</div></body></html>\n'
    )
