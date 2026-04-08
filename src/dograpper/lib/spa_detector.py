"""SPA detection based on HTML empty shells."""

import os
import logging
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.visible_text = []
        self.in_body = False
        self.spa_id_found = False

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True
            
        if self.in_body and tag == "div":
            for attr, value in attrs:
                if attr == "id" and value in ("root", "__next", "app"):
                    self.spa_id_found = True

    def handle_endtag(self, tag):
        if tag == "body":
            self.in_body = False

    def handle_data(self, data):
        if self.in_body:
            text = data.strip()
            if text:
                self.visible_text.append(text)

    def get_text(self) -> str:
        return " ".join(self.visible_text)

def is_spa(directory: str, threshold: float = 0.7, min_text_chars: int = 200) -> bool:
    """Analyze a directory of HTML files to check if they are mostly empty SPA shells."""
    html_files = []
    
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith('.html'):
                html_files.append(os.path.join(root, f))
                
    if not html_files:
        return False
        
    empty_shells_count = 0
    total_files = len(html_files)
    
    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            parser = VisibleTextParser()
            parser.feed(content)
            
            text_len = len(parser.get_text())
            
            if text_len < min_text_chars or parser.spa_id_found:
                empty_shells_count += 1
                
        except Exception as e:
            logger.debug(f"Error parsing {html_file}: {e}")
            
    logger.debug(f"SPA detection: {empty_shells_count}/{total_files} files are empty shells")
    
    proportion = empty_shells_count / total_files
    return proportion > threshold
