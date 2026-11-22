from __future__ import annotations

import ipaddress
import re
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import Settings
from .http_client import proxy_url_from_env


class DownloadError(RuntimeError):
    pass


@dataclass
class DownloadedPdf:
    path: Path
    original_url: str
    resolved_url: str
    filename: str


ARXIV_PATTERN = re.compile(
    r"^/(?:abs|pdf)/(?P<identifier>[^?#]+?)(?:\.pdf)?/?$", re.IGNORECASE
)


def normalize_arxiv_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname not in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        return url
    match = ARXIV_PATTERN.match(parsed.path)
    if not match:
        return url
    identifier = match.group("identifier").strip("/")
    return f"https://arxiv.org/pdf/{identifier}.pdf"


def validate_public_url(url: str, allow_private: bool) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DownloadError("只支持 http 或 https 链接。")

    if allow_private:
        return

    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror as error:
        raise DownloadError(f"无法解析链接域名：{parsed.hostname}") from error

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise DownloadError("出于 SSRF 防护，默认不允许访问内网或本机地址。")


def safe_filename(value: str, fallback: str = "paper") -> str:
    decoded = unquote(value).strip()
    decoded = Path(decoded).name
    stem = re.sub(r"\.pdf$", "", decoded, flags=re.IGNORECASE)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" ._-")
    if not stem:
        stem = fallback
    return f"{stem[:140]}.pdf"


def filename_from_headers(url: str, content_disposition: str | None) -> str:
    if content_disposition:
        utf8_match = re.search(
            r"filename\*=UTF-8''([^;]+)", content_disposition, re.IGNORECASE
        )
        if utf8_match:
            return safe_filename(utf8_match.group(1))
        match = re.search(r'filename="?([^";]+)"?', content_disposition, re.IGNORECASE)
        if match:
            return safe_filename(match.group(1))
    return safe_filename(Path(urlparse(url).path).name or "paper")


def extract_pdf_candidate(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        ('meta[name="citation_pdf_url"]', "content"),
        ('meta[property="citation_pdf_url"]', "content"),
        ('link[type="application/pdf"]', "href"),
        ('link[rel="alternate"][type="application/pdf"]', "href"),
    ]
    for selector, attribute in selectors:
        element = soup.select_one(selector)
        value = element.get(attribute) if element else None
        if value:
            return urljoin(base_url, value.strip())

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        label = anchor.get_text(" ", strip=True).lower()
        if href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        if ".pdf" in href.lower() or label in {"pdf", "download pdf", "view pdf"}:
            return urljoin(base_url, href)
    return None


async def download_pdf(url: str, settings: Settings, target_dir: Path) -> DownloadedPdf:
    normalized_url = normalize_arxiv_url(url.strip())
    validate_public_url(normalized_url, settings.allow_private_urls)
    target_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = settings.max_download_mb * 1024 * 1024
    headers = {
        "User-Agent": (
            "PaperAtlas/0.1 (+personal research library; "
            "respects publisher terms and downloads only user-provided links)"
        ),
        "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.5",
    }

    current_url = normalized_url
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(45, read=180),
        follow_redirects=True,
        headers=headers,
        proxy=proxy_url_from_env(),
        trust_env=False,
    ) as client:
        for _ in range(5):
            validate_public_url(current_url, settings.allow_private_urls)
            try:
                async with client.stream("GET", current_url) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    content_length = int(response.headers.get("content-length", "0") or "0")
                    if content_length and content_length > max_bytes:
                        raise DownloadError(
                            f"文件超过 {settings.max_download_mb} MB 的下载限制。"
                        )

                    if "text/html" in content_type or "application/xhtml" in content_type:
                        html = (await response.aread()).decode(
                            response.encoding or "utf-8", errors="replace"
                        )
                        candidate = extract_pdf_candidate(html, str(response.url))
                        if not candidate:
                            raise DownloadError(
                                "该页面未找到 PDF 下载地址，请直接提供 PDF 或 arXiv 论文链接。"
                            )
                        current_url = normalize_arxiv_url(candidate)
                        continue

                    if (
                        "application/pdf" not in content_type
                        and not str(response.url).lower().endswith(".pdf")
                    ):
                        raise DownloadError(
                            f"链接返回的不是 PDF（Content-Type: {content_type or 'unknown'}）。"
                        )

                    filename = filename_from_headers(
                        str(response.url), response.headers.get("content-disposition")
                    )
                    destination = target_dir / f"{filename[:-4]}-{uuid.uuid4().hex[:8]}.pdf"
                    temporary = destination.with_suffix(".pdf.part")
                    downloaded = 0
                    first_chunk = True
                    with temporary.open("wb") as handle:
                        async for chunk in response.aiter_bytes():
                            if not chunk:
                                continue
                            if first_chunk:
                                first_chunk = False
                                if not chunk.lstrip().startswith(b"%PDF-"):
                                    temporary.unlink(missing_ok=True)
                                    raise DownloadError("下载内容没有有效的 PDF 文件签名。")
                            downloaded += len(chunk)
                            if downloaded > max_bytes:
                                temporary.unlink(missing_ok=True)
                                raise DownloadError(
                                    f"文件超过 {settings.max_download_mb} MB 的下载限制。"
                                )
                            handle.write(chunk)
                    temporary.replace(destination)
                    return DownloadedPdf(
                        path=destination,
                        original_url=url,
                        resolved_url=str(response.url),
                        filename=destination.name,
                    )
            except DownloadError:
                raise
            except httpx.HTTPStatusError as error:
                raise DownloadError(
                    f"下载失败，目标站点返回 {error.response.status_code}。"
                ) from error
            except httpx.HTTPError as error:
                raise DownloadError(f"下载失败：{error}") from error

    raise DownloadError("链接重定向过多，未能找到 PDF。")
