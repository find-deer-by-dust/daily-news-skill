from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.agents/skills/daily-news/scripts'))
from dailyNews.email_html import render_report_html


class ParsedHTML(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.elements = []
        self.text = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


class EmailHTMLTests(unittest.TestCase):
    def test_markdown_structure_and_styles(self):
        report = '''# 中文新闻

## 今日摘要

### 重点

**加粗**、*强调*、~~删除~~ 和 `x < 2`。

- 第一条
- 第二条

1. 步骤一
2. 步骤二

> 引用

| 项目 | 数值 |
| :--- | ---: |
| 甲 | 10 |

[来源](https://example.com/news?a=1&b=2)

![图片](https://example.com/photo.png)

```python
print("<tag>")
```

    code < 3

---
'''
        parsed = ParsedHTML(render_report_html(report))
        tags = [tag for tag, attrs in parsed.elements]
        for tag in ('h1','h2','h3','strong','em','s','code','ul','ol','li',
                    'blockquote','table','th','td','a','img','pre','hr'):
            with self.subTest(tag=tag):
                self.assertIn(tag,tags)
        for tag, attrs in parsed.elements:
            if tag in {'h1','h2','h3','p','strong','ul','ol','li','blockquote',
                       'table','th','td','a','img','pre','hr'}:
                self.assertIn('style',attrs)
        self.assertIn(('a',{'href':'https://example.com/news?a=1&b=2',
                            'style':next(a['style'] for t,a in parsed.elements if t=='a')}),
                      parsed.elements)
        self.assertTrue(any(t=='th' and 'text-align:right' in a['style']
                            for t,a in parsed.elements))
        self.assertIn('print("<tag>")',''.join(parsed.text))
        self.assertNotIn('tag',tags)

    def test_raw_html_and_unsafe_links_cannot_become_active_markup(self):
        report = '<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[危险](javascript:alert(1))'
        parsed = ParsedHTML(render_report_html(report,title='<unsafe> & 标题'))
        self.assertFalse(any(t in {'script','img','unsafe'} for t,a in parsed.elements))
        self.assertFalse(any(a.get('href','').startswith('javascript:') for t,a in parsed.elements))
        self.assertIn('<script>alert(1)</script>',''.join(parsed.text))
        self.assertIn('<unsafe> & 标题',''.join(parsed.text))

    def test_plain_text_and_line_breaks_stay_readable(self):
        parsed = ParsedHTML(render_report_html('中文第一行\n第二行 & <第三行>'))
        self.assertIn(('br',{}),parsed.elements)
        self.assertIn('中文第一行',''.join(parsed.text))
        self.assertIn('第二行 & <第三行>',''.join(parsed.text))


if __name__ == '__main__':
    unittest.main()
