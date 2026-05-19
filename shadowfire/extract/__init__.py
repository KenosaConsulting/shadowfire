from bs4 import BeautifulSoup
from .cleaner import clean
from .converter import to_markdown
from .metadata import extract as extract_metadata
from .document import Document, Metadata


def process(raw_html: str, url: str = "", only_main_content: bool = True) -> Document:
    cleaned_html = clean(raw_html, page_url=url, only_main_content=only_main_content)
    markdown = to_markdown(cleaned_html)

    # Fallback: if onlyMainContent strips everything, retry with full content
    if only_main_content and not markdown.strip():
        cleaned_html = clean(raw_html, page_url=url, only_main_content=False)
        markdown = to_markdown(cleaned_html)

    soup = BeautifulSoup(cleaned_html, "lxml")
    links = [a["href"] for a in soup.find_all("a", href=True)]
    images = [
        img["src"] for img in soup.find_all("img", src=True)
        if not img["src"].startswith("data:")
    ]

    # Strip data: URI images from markdown — they're noise for LLMs
    import re
    markdown = re.sub(r"!\[[^\]]*\]\(data:[^)]+\)", "", markdown)

    metadata = extract_metadata(raw_html, page_url=url)

    return Document(
        markdown=markdown,
        html=cleaned_html,
        raw_html=raw_html,
        links=links,
        images=images,
        metadata=metadata,
    )
