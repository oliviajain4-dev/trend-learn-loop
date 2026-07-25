"""HTML 본문 → 읽을 수 있는 텍스트 (의존성 0, stdlib html.parser).

목적: 가져온 공식 문서의 '본문'을 확보 → 이후 인용-대조(L1)·집필의 실제 근거.
품질은 기본(메뉴 등 잡음이 섞일 수 있음)이나 인용 대조엔 충분하다
(진짜 문장이 텍스트 안에 있기만 하면 됨). readability 고급화는 이후 개선.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_SKIP = {"script", "style", "noscript", "svg", "template"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_title = False
        self.body: list[str] = []
        self.title: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        s = data.strip()
        if not s:
            return
        (self.title if self._in_title else self.body).append(s)


def extract_text(html: str, *, max_chars: int = 8000) -> tuple[str, str]:
    """(title, body_text). 공백 정규화 후 body 를 max_chars 로 자름."""
    p = _Extractor()
    try:
        p.feed(html)
    except Exception:  # 깨진 HTML 이어도 최대한 회수
        pass
    title = re.sub(r"\s+", " ", " ".join(p.title)).strip()
    body = re.sub(r"\s+", " ", " ".join(p.body)).strip()
    return title, body[:max_chars]
