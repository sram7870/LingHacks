import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict

DATA_DIR = "data"
PAPERS_DIR = os.path.join(DATA_DIR, "papers")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
REGISTRY_FILE = os.path.join(DATA_DIR, "paper_registry.json")

class PaperService:
    def __init__(self):
        self._ensure_dirs()
        self.registry = self._load_registry()

    def _ensure_dirs(self):
        os.makedirs(PAPERS_DIR, exist_ok=True)
        os.makedirs(PROCESSED_DIR, exist_ok=True)

    def _load_registry(self) -> Dict:
        if os.path.exists(REGISTRY_FILE):
            try:
                with open(REGISTRY_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_registry(self):
        with open(REGISTRY_FILE, "w") as f:
            json.dump(self.registry, f, indent=2)

    def register_paper(
        self,
        title: str,
        filename: str,
        file_bytes: bytes,
        authors: List[str] = None,
        year: int = None,
        deduplicate: bool = True,
    ) -> str:
        if deduplicate:
            for pid, p in self.registry.items():
                if p["title"] == title:
                    return pid

        paper_id = str(uuid.uuid4())
        # Sanitized filename to avoid path traversal
        safe_filename = "".join([c for c in filename if c.isalnum() or c in "._-"]).strip()
        filepath = os.path.join(PAPERS_DIR, f"{paper_id}_{safe_filename}")
        
        with open(filepath, "wb") as f:
            f.write(file_bytes)
            
        self.registry[paper_id] = {
            "paper_id": paper_id,
            "title": title,
            "authors": authors or [],
            "year": year or datetime.now().year,
            "filepath": filepath,
            "filename": filename,
            "upload_timestamp": datetime.now().isoformat(),
            "processed_path": None
        }
        self._save_registry()
        return paper_id

    def save_processed_output(self, paper_id: str, output: Dict):
        filepath = os.path.join(PROCESSED_DIR, f"{paper_id}.json")
        with open(filepath, "w") as f:
            json.dump(output, f, indent=2)
        if paper_id in self.registry:
            self.registry[paper_id]["processed_path"] = filepath
            self._save_registry()

    def get_paper(self, paper_id: str) -> Optional[Dict]:
        return self.registry.get(paper_id)

    def get_paper_by_title(self, title: str) -> Optional[Dict]:
        for p in self.registry.values():
            if p["title"] == title:
                return p
        return None

    def list_papers(self) -> List[Dict]:
        return list(self.registry.values())

    def delete_paper(self, paper_id: str):
        if paper_id in self.registry:
            paper = self.registry[paper_id]
            if os.path.exists(paper["filepath"]):
                os.remove(paper["filepath"])
            if paper.get("processed_path") and os.path.exists(paper["processed_path"]):
                os.remove(paper["processed_path"])
            del self.registry[paper_id]
            self._save_registry()
