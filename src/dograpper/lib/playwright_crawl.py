"""Headless crawler using playwright."""

import os
import logging
import time
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass
from typing import List, Any
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class CrawlResult:
    success: bool
    output_dir: str
    files_downloaded: List[str]
    errors: List[str]

def run_playwright_crawl(
    url: str,
    output_dir: str,
    depth: int = 0,
    delay: int = 0,
    include_extensions: str = "html,md,txt",
    manifest_data: Any = None
) -> CrawlResult:
    """Crawl SPAs using playwright."""
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("playwright is required for SPA crawling. Install with: uv add playwright && playwright install chromium")

    parsed_initial = urlparse(url)
    base_domain = parsed_initial.netloc
    
    visited = set()
    to_visit = [(url, 0)]
    files_downloaded = []
    errors = []
    
    extensions = [ext.strip().lower() for ext in include_extensions.split(',') if ext.strip()]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        while to_visit:
            current_url, current_depth = to_visit.pop(0)
            
            if current_url in visited:
                continue
                
            if depth > 0 and current_depth > depth:
                continue
                
            visited.add(current_url)
            
            if current_url != url and delay > 0:
                time.sleep(delay / 1000.0)
                
            logger.info(f"Crawling {current_url}")
            
            try:
                page.goto(current_url, wait_until="networkidle")
                content = page.content()
                
                # Determine file path
                parsed_current = urlparse(current_url)
                path = parsed_current.path
                if not path or path.endswith('/'):
                    path += 'index.html'
                elif not any(path.endswith(f".{ext}") for ext in extensions):
                    path += '.html' # default to html for SPAs
                    
                path = path.lstrip('/')
                
                # Create directory and save
                full_path = os.path.join(output_dir, parsed_initial.netloc, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                files_downloaded.append(full_path)
                
                # Extract links
                links = page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('a[href]')).map(a => a.href);
                }''')
                
                for link in links:
                    parsed_link = urlparse(link)
                    if parsed_link.netloc == base_domain or not parsed_link.netloc:
                        absolute_link = urljoin(current_url, link)
                        
                        # Strip fragments
                        absolute_link = urlparse(absolute_link)._replace(fragment="").geturl()
                        
                        if absolute_link not in visited:
                            to_visit.append((absolute_link, current_depth + 1))
                            
            except Exception as e:
                logger.error(f"Error crawling {current_url}: {e}")
                errors.append(f"Error crawling {current_url}: {e}")
                
        browser.close()
        
    return CrawlResult(
        success=True,
        output_dir=output_dir,
        files_downloaded=files_downloaded,
        errors=errors
    )
