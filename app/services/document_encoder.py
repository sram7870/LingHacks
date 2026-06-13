import io
import re
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text

from app.core.config import settings
from app.schemas import PaperParseRequest


class ParsedDocument:
    def __init__(self, title: str, abstract: str, sections: Dict[str, str], citations: List[str]):
        self.title = title
        self.abstract = abstract
        self.sections = sections
        self.citations = citations


class DocumentEncoder:
    def __init__(self):
        self.grobid_url = settings.grobid_url

    def parse_document(self, request: PaperParseRequest) -> ParsedDocument:
        sections = {
            "introduction": request.introduction or "",
            "methods": request.methods or "",
            "results": request.results or "",
            "discussion": request.discussion or "",
        }
        return ParsedDocument(
            title=request.title,
            abstract=request.abstract,
            sections=sections,
            citations=request.citations,
        )

    def parse_file(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        if filename.lower().endswith(".pdf"):
            return self.parse_pdf(file_bytes)
        if filename.lower().endswith(('.xml', '.nxml')):
            return self.parse_xml(file_bytes.decode('utf-8', errors='ignore'))
        if filename.lower().endswith(('.html', '.htm')):
            return self.parse_html(file_bytes.decode('utf-8', errors='ignore'))

        raw_text = file_bytes.decode('utf-8', errors='ignore')
        return self.parse_text_to_sections(raw_text)

    def parse_pdf(self, file_bytes: bytes) -> ParsedDocument:
        parsed = self.parse_pdf_with_grobid(file_bytes)
        if parsed is not None:
            return parsed

        raw_text = extract_text(io.BytesIO(file_bytes))
        return self.parse_text_to_sections(raw_text)

    def parse_pdf_with_grobid(self, file_bytes: bytes) -> Optional[ParsedDocument]:
        try:
            response = httpx.post(
                f"{self.grobid_url}/api/processFulltextDocument",
                files={"input": ("document.pdf", file_bytes, "application/pdf")},
                timeout=60.0,
            )
            response.raise_for_status()
            return self.parse_tei(response.text)
        except Exception:
            return None

    def parse_xml(self, xml_text: str) -> ParsedDocument:
        document = ET.fromstring(xml_text)
        sections = {
            "introduction": self._extract_xml_section(document, ["introduction", "background"]),
            "methods": self._extract_xml_section(document, ["methods", "materials", "methodology"]),
            "results": self._extract_xml_section(document, ["results", "findings"]),
            "discussion": self._extract_xml_section(document, ["discussion", "conclusion"]),
        }
        abstract = self._extract_xml_section(document, ["abstract"])
        title = self._extract_xml_section(document, ["title"])
        citations = self._extract_xml_citations(document)
        return ParsedDocument(title=title or "", abstract=abstract or "", sections=sections, citations=citations)

    def parse_html(self, html_text: str) -> ParsedDocument:
        soup = BeautifulSoup(html_text, "lxml")
        abstract = self._extract_html_section(soup, ["abstract"])
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        sections = {
            "introduction": self._extract_html_section(soup, ["introduction", "background"]),
            "methods": self._extract_html_section(soup, ["methods", "materials", "methodology"]),
            "results": self._extract_html_section(soup, ["results", "findings"]),
            "discussion": self._extract_html_section(soup, ["discussion", "conclusion"]),
        }
        citations = [ref.get_text(separator=" ", strip=True) for ref in soup.find_all("cite")]
        return ParsedDocument(title=title, abstract=abstract or "", sections=sections, citations=citations)

    def parse_tei(self, tei_xml: str) -> ParsedDocument:
        root = ET.fromstring(tei_xml)
        title = self._extract_tei_text(root, ["titleStmt/title", "fileDesc/titleStmt/title"])
        abstract = self._extract_tei_text(root, ["teiHeader/profileDesc/abstract", "text/front/abstract"])
        sections = {
            "introduction": self._extract_tei_text(root, ["text/body/div[@type='introduction']", "text/body/div[@type='background']"]),
            "methods": self._extract_tei_text(root, ["text/body/div[@type='methods']", "text/body/div[@type='method']"]),
            "results": self._extract_tei_text(root, ["text/body/div[@type='results']", "text/body/div[@type='findings']"]),
            "discussion": self._extract_tei_text(root, ["text/body/div[@type='discussion']", "text/body/div[@type='conclusion']"]),
        }
        citations = self._extract_tei_citations(root)
        return ParsedDocument(title=title or "", abstract=abstract or "", sections=sections, citations=citations)

    def parse_text_to_sections(self, raw_text: str) -> ParsedDocument:
        cleaned = self._clean_text(raw_text)
        sections = {
            "introduction": self._extract_section_text(cleaned, "introduction"),
            "methods": self._extract_section_text(cleaned, "methods"),
            "results": self._extract_section_text(cleaned, "results"),
            "discussion": self._extract_section_text(cleaned, "discussion"),
        }
        abstract = self._extract_section_text(cleaned, "abstract") or cleaned[:400]
        title = cleaned.splitlines()[0].strip() if cleaned else ""
        return ParsedDocument(title=title, abstract=abstract, sections=sections, citations=[])

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()

    def _extract_section_text(self, text: str, section_name: str) -> str:
        pattern = re.compile(rf"(?:\n|^).*?{section_name}.*?(?=\n\s*(?:abstract|introduction|methods|results|discussion|conclusion)|$)", re.IGNORECASE | re.DOTALL)
        match = pattern.search(text)
        if match:
            return self._clean_text(match.group(0))
        return ""

    def _extract_xml_section(self, root: ET.Element, labels: List[str]) -> str:
        for label in labels:
            for element in root.findall(f".//{label}"):
                return self._clean_text(' '.join(element.itertext()))
        return ""

    def _extract_xml_citations(self, root: ET.Element) -> List[str]:
        citations = []
        for element in root.iter():
            if self._clean_tag(element.tag) in {"citation", "ref", "biblStruct"}:
                citations.append(self._clean_text(' '.join(element.itertext())))
        return citations

    def _extract_html_section(self, soup: BeautifulSoup, labels: List[str]) -> str:
        for label in labels:
            heading = soup.find(lambda tag: tag.name in ["h1", "h2", "h3", "h4"] and tag.get_text(strip=True).lower().startswith(label))
            if heading:
                texts = []
                for sibling in heading.find_next_siblings():
                    if sibling.name and sibling.name.startswith("h"):
                        break
                    texts.append(sibling.get_text(separator=" ", strip=True))
                return self._clean_text(" ".join(texts))
        return ""

    def _extract_tei_text(self, root: ET.Element, paths: List[str]) -> str:
        for path in paths:
            element = root.find(f".//{path}")
            if element is not None:
                return self._clean_text(' '.join(element.itertext()))
        return ""

    def _extract_tei_citations(self, root: ET.Element) -> List[str]:
        citations = []
        for element in root.iter():
            if self._clean_tag(element.tag) in {"biblStruct", "ref", "ptr"}:
                citations.append(self._clean_text(' '.join(element.itertext())))
        return citations

    def _clean_tag(self, tag: str) -> str:
        return tag.split('}')[-1] if '}' in tag else tag
