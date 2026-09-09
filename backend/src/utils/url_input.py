import time

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from configs.logger import get_logger, preview

logger = get_logger(__name__)

REQUEST_TIMEOUT = 10
MAX_CHARS = 8000
STRIPPED_TAGS = ["script", "style", "nav", "footer", "header"]


@tool
def fetch_url(url: str) -> str:
    started = time.perf_counter()
    logger.info("fetching %s (timeout=%ds)", url, REQUEST_TIMEOUT)

    try:
        response = requests.get(
            url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"}
        )
    except Exception:
        logger.exception("fetch FAILED for %s", url)
        raise

    logger.info(
        "fetched %s | status=%s, %d bytes of HTML in %d ms",
        url, response.status_code, len(response.text),
        round((time.perf_counter() - started) * 1000),
    )

    if response.status_code >= 400:
        logger.warning(
            "%s returned HTTP %s — the extracted text is probably an error page",
            url, response.status_code,
        )

    soup = BeautifulSoup(response.text, "html.parser")

    removed = 0
    for junk in soup(STRIPPED_TAGS):
        junk.decompose()
        removed += 1
    logger.debug("stripped %d non-content element(s) (%s)", removed, ", ".join(STRIPPED_TAGS))

    paragraphs = soup.find_all("p")
    text = " ".join(p.get_text(strip=True) for p in paragraphs)

    if not text.strip():
        logger.warning(
            "extracted NO readable text from %s (%d <p> tags found) — the page is "
            "likely JavaScript-rendered, so there is nothing to write a brief from",
            url, len(paragraphs),
        )
        return ""

    if len(text) > MAX_CHARS:
        logger.info(
            "truncating extracted text from %d to %d chars for %s",
            len(text), MAX_CHARS, url,
        )

    result = text[:MAX_CHARS]
    logger.info(
        "extracted %d chars from %d paragraph(s) at %s", len(result), len(paragraphs), url
    )
    logger.debug("extracted text starts: %s", preview(result))
    return result
