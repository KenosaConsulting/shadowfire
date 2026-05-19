from dataclasses import dataclass, field


@dataclass
class Metadata:
    # Core
    title: str | None = None
    description: str | None = None
    language: str | None = None
    keywords: str | None = None
    robots: str | None = None
    favicon: str | None = None
    # Open Graph
    og_title: str | None = None
    og_description: str | None = None
    og_url: str | None = None
    og_image: str | None = None
    og_site_name: str | None = None
    og_locale: str | None = None
    og_video: str | None = None
    og_audio: str | None = None
    # Article
    published_time: str | None = None
    modified_time: str | None = None
    article_tag: str | None = None
    article_section: str | None = None
    # Dublin Core
    dc_date: str | None = None
    dc_description: str | None = None
    dc_keywords: str | None = None
    dc_type: str | None = None
    # Request info
    url: str | None = None
    source_url: str | None = None
    status_code: int = 0
    content_type: str | None = None
    # Catch-all for any remaining <meta> tags
    extra: dict = field(default_factory=dict)


@dataclass
class Document:
    markdown: str | None = None
    html: str | None = None       # cleaned HTML (post noise removal)
    raw_html: str | None = None   # raw HTML as fetched
    links: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)
