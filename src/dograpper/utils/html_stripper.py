"""HTML Stripping utility."""

from html.parser import HTMLParser
import re
import html

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []
        self.ignore = False
        self.ignore_tags = {'script', 'style'}

    def handle_starttag(self, tag, attrs):
        if tag in self.ignore_tags:
            self.ignore = True

    def handle_endtag(self, tag):
        if tag in self.ignore_tags:
            self.ignore = False

    def handle_data(self, d):
        if not self.ignore:
            self.text.append(d)

    def get_data(self):
        return ''.join(self.text)

def strip_html(text: str) -> str:
    """Read an HTML string and strip all tags, script contents, and style contents."""
    s = HTMLStripper()
    s.feed(text)
    data = s.get_data()
    # Unescape HTML entities that might be lingering
    data = html.unescape(data)
    # Collapse multiple whitespaces into a single space
    data = re.sub(r'\s+', ' ', data)
    return data.strip()
