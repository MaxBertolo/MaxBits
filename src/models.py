from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawArticle:
    id: str
    title: str
    url: str
    source: str
    published_at: datetime
    content: str
    language: str = "en"
