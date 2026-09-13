"""
Web Content Fetcher and Cleaner for Sovereign AI Global Knowledge Mode.
Extracts clean, readable text from public web pages using standard library HTMLParser.
Removes scripts, styles, navigation, headers, footers, and advertisement noise.
Enforces SSRF defense via backend.app.security.ssrf.
"""

import re
import urllib.parse
from html.parser import HTMLParser
from typing import Dict, Any, List

from backend.app.security.ssrf import (
    fetch_url_safely,
    validate_safe_url,
    SSRFSecurityError,
    URLFetchTimeoutError,
    URLSizeLimitExceededError,
    MAX_EXTRACTED_TEXT_CHARS,
)


class CleanTextHTMLParser(HTMLParser):
    """
    Strips noise elements and extracts main body text and title.
    Only includes container tags that enclose ignored text.
    """

    IGNORE_TAGS = {
        "script", "style", "noscript", "svg", "iframe"
    }

    BLOCK_TAGS = {
        "p", "h1", "h2", "h3", "h4", "h5", "h6", "div", "section",
        "article", "li", "tr", "blockquote", "hr", "br", "pre"
    }

    def __init__(self):
        super().__init__()
        self.title_parts: List[str] = []
        self.text_parts: List[str] = []
        self.in_title = False
        self.ignored_stack: List[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag_lower = tag.lower()
        if tag_lower in self.IGNORE_TAGS:
            self.ignored_stack.append(tag_lower)
        elif tag_lower == "title":
            self.in_title = True
        elif tag_lower in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if self.ignored_stack and self.ignored_stack[-1] == tag_lower:
            self.ignored_stack.pop()
        elif tag_lower == "title":
            self.in_title = False
        elif tag_lower in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str):
        if self.ignored_stack:
            return
        if self.in_title:
            self.title_parts.append(data)
            return

        text = data.strip()
        if text:
            self.text_parts.append(data)


def clean_extracted_text(raw_text: str) -> str:
    """
    Normalizes whitespace and removes common web noise artifacts.
    """
    # Replace carriage returns
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove Wikipedia-style edit links like "[edit]"
    text = re.sub(r"\[edit\]", "", text, flags=re.IGNORECASE)

    # Collapse multiple blank lines into at most 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse internal horizontal whitespace
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    cleaned = "\n".join(line for line in lines if line)

    # Limit to maximum characters
    if len(cleaned) > MAX_EXTRACTED_TEXT_CHARS:
        cleaned = cleaned[:MAX_EXTRACTED_TEXT_CHARS] + " ... [content truncated at limit]"

    return cleaned.strip()


def extract_page_content(html: str, url: str) -> Dict[str, Any]:
    """
    Parses HTML, extracts title, meta descriptions, and clean text content.
    Supports both traditional static HTML pages and client-rendered SPAs (React/Next.js).
    """
    raw_title = ""
    raw_body = ""
    meta_descriptions: List[str] = []

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            raw_title = soup.title.string.strip()

        # Extract meta tags (crucial for SPAs like Next.js/React where body DOM is hydrated client-side)
        for meta in soup.find_all("meta"):
            name = (meta.get("name") or meta.get("property") or "").lower()
            content = (meta.get("content") or "").strip()
            if content and name in ("description", "og:description", "twitter:description", "keywords"):
                if content not in meta_descriptions and content != raw_title:
                    meta_descriptions.append(content)

        # Decompose noisy script/style/svg/reference elements
        noise_selectors = [
            "script", "style", "noscript", "svg", "iframe", "nav", "header", "footer", "form", "aside",
            ".reflist", ".references", ".navbox", "#catlinks", ".printfooter", ".mw-jump-link",
            ".vector-toc", ".mw-editsection", ".reference", ".mw-references-wrap", "#footer", ".extiw"
        ]
        for sel in noise_selectors:
            for element in soup.select(sel):
                element.decompose()

        raw_body = soup.get_text(separator="\n", strip=True)
    except Exception:
        # Fallback to standard library parser
        parser = CleanTextHTMLParser()
        try:
            parser.feed(html)
        except Exception:
            pass
        raw_title = "".join(parser.title_parts).strip()
        raw_body = "".join(parser.text_parts)

    body_cleaned = clean_extracted_text(raw_body)
    
    # Combine title, meta descriptions, and body text
    content_parts = []
    if raw_title:
        content_parts.append(f"Title: {raw_title}")
    if meta_descriptions:
        content_parts.append("Page Overview & Description:\n" + "\n".join(meta_descriptions))
    if body_cleaned and body_cleaned != raw_title:
        content_parts.append("Content:\n" + body_cleaned)

    full_content = "\n\n".join(content_parts).strip()

    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc or parsed_url.path

    if not raw_title:
        # Fallback to domain or path
        raw_title = domain.replace("www.", "")

    if len(full_content) < 30:
        raise ValueError("Unable to extract readable content from this URL.")

    return {
        "url": url,
        "title": raw_title[:200],
        "content": full_content,
        "length": len(full_content),
        "domain": domain,
    }


def fetch_and_clean_public_url(url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Full pipeline:
    1. Validates URL against SSRF rules
    2. Fetches content safely (within size and timeout bounds)
    3. Cleans HTML and extracts readable text
    """
    raw_html, final_url, _ = fetch_url_safely(url, timeout=timeout)
    data = extract_page_content(raw_html, final_url)
    return data


# Alias for compatibility
fetch_and_clean_web_content = fetch_and_clean_public_url

