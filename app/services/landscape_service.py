import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict

LANDSCAPES_DIR = "data/landscapes"

class LandscapeService:
    def __init__(self):
        os.makedirs(LANDSCAPES_DIR, exist_ok=True)

    def create_landscape(self, name: str, description: str) -> Dict:
        landscape_id = str(uuid.uuid4())
        landscape = {
            "id": landscape_id,
            "name": name,
            "description": description,
            "paper_ids": [],
            "created_at": datetime.now().isoformat(),
            "last_analysis": None,
            "graph_built": False,
            "topic_metrics": None
        }
        self._save_landscape(landscape)
        return landscape

    def get_landscape(self, landscape_id: str) -> Optional[Dict]:
        filepath = os.path.join(LANDSCAPES_DIR, f"{landscape_id}.json")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)
        return None

    def list_landscapes(self) -> List[Dict]:
        landscapes = []
        if not os.path.exists(LANDSCAPES_DIR):
            return []
        for filename in os.listdir(LANDSCAPES_DIR):
            if filename.endswith(".json"):
                with open(os.path.join(LANDSCAPES_DIR, filename), "r") as f:
                    landscapes.append(json.load(f))
        return sorted(landscapes, key=lambda x: x.get("created_at", ""), reverse=True)

    def update_landscape(self, landscape_id: str, **kwargs) -> bool:
        landscape = self.get_landscape(landscape_id)
        if landscape:
            landscape.update(kwargs)
            self._save_landscape(landscape)
            return True
        return False

    def delete_landscape(self, landscape_id: str):
        filepath = os.path.join(LANDSCAPES_DIR, f"{landscape_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)

    def add_paper_to_landscape(self, landscape_id: str, paper_id: str) -> bool:
        landscape = self.get_landscape(landscape_id)
        if landscape:
            if paper_id not in landscape["paper_ids"]:
                landscape["paper_ids"].append(paper_id)
                self._save_landscape(landscape)
            return True
        return False

    def remove_paper_from_landscape(self, landscape_id: str, paper_id: str) -> bool:
        landscape = self.get_landscape(landscape_id)
        if landscape:
            if paper_id in landscape["paper_ids"]:
                landscape["paper_ids"].remove(paper_id)
                self._save_landscape(landscape)
            return True
        return False

    def _save_landscape(self, landscape: Dict):
        filepath = os.path.join(LANDSCAPES_DIR, f"{landscape['id']}.json")
        with open(filepath, "w") as f:
            json.dump(landscape, f, indent=2)
