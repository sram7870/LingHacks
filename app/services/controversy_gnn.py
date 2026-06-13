from typing import Dict, List, Optional, Tuple
import torch
import torch.nn as nn
import numpy as np

try:
    from torch_geometric.nn import HeteroConv, GATConv
    from torch_geometric.data import HeteroData
    HAS_PYTORCH_GEOMETRIC = True
except ImportError:
    HAS_PYTORCH_GEOMETRIC = False


class ControversyGNN(nn.Module):
    """Heterogeneous Graph Neural Network for predicting controversy and consensus."""

    def __init__(self, hidden_dim: int = 128, num_layers: int = 2):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        if HAS_PYTORCH_GEOMETRIC:
            self.layers = nn.ModuleList([
                HeteroConv({
                    ("paper", "cites", "paper"): GATConv((-1, -1), hidden_dim),
                    ("paper", "contains", "claim"): GATConv((-1, -1), hidden_dim),
                    ("claim", "from", "paper"): GATConv((-1, -1), hidden_dim),
                }, aggr="mean")
                for _ in range(num_layers)
            ])

            self.controversy_head = nn.Sequential(
                nn.Linear(hidden_dim, 64),
                nn.ReLU(),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )

            self.consensus_head = nn.Sequential(
                nn.Linear(hidden_dim, 64),
                nn.ReLU(),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )

    def forward(self, x_dict: Dict, edge_index_dict: Dict) -> Dict[str, torch.Tensor]:
        """Forward pass on heterogeneous graph."""
        if not HAS_PYTORCH_GEOMETRIC:
            return self._fallback_forward()

        x = x_dict.copy()

        for layer in self.layers:
            x = layer(x, edge_index_dict)
            x = {key: torch.nn.functional.relu(val) for key, val in x.items()}

        paper_repr = x.get("paper", torch.zeros((1, self.hidden_dim)))

        if paper_repr.numel() > 0:
            controversy = self.controversy_head(paper_repr)
            consensus = self.consensus_head(paper_repr)
        else:
            controversy = torch.tensor([[0.5]])
            consensus = torch.tensor([[0.5]])

        return {
            "controversy": controversy,
            "consensus": consensus,
        }

    def _fallback_forward(self) -> Dict[str, torch.Tensor]:
        """Fallback when PyTorch Geometric is not available."""
        return {
            "controversy": torch.tensor([[0.5]]),
            "consensus": torch.tensor([[0.5]]),
        }


class ControversyGraphBuilder:
    """Build and manage a heterogeneous graph for controversy analysis."""

    def __init__(self):
        self.gnn = ControversyGNN() if HAS_PYTORCH_GEOMETRIC else None
        self.node_features = {}
        self.edge_indices = {}

    def add_paper_node(self, paper_id: str, features: np.ndarray) -> None:
        """Add a paper node with features."""
        self.node_features[("paper", paper_id)] = torch.tensor(features, dtype=torch.float32)

    def add_claim_node(self, claim_id: str, features: np.ndarray) -> None:
        """Add a claim node with features."""
        self.node_features[("claim", claim_id)] = torch.tensor(features, dtype=torch.float32)

    def add_citation_edge(self, from_paper: str, to_paper: str) -> None:
        """Add a citation edge between papers."""
        key = ("paper", "cites", "paper")
        if key not in self.edge_indices:
            self.edge_indices[key] = []
        self.edge_indices[key].append((from_paper, to_paper))

    def add_claim_edge(self, paper_id: str, claim_id: str) -> None:
        """Add an edge between a paper and its claims."""
        key = ("paper", "contains", "claim")
        if key not in self.edge_indices:
            self.edge_indices[key] = []
        self.edge_indices[key].append((paper_id, claim_id))

    def predict_controversy(self) -> Dict[str, float]:
        """Predict controversy and consensus scores for the graph."""
        if not HAS_PYTORCH_GEOMETRIC or self.gnn is None:
            return self._fallback_prediction()

        try:
            x_dict = self._build_node_dict()
            edge_index_dict = self._build_edge_dict()

            with torch.no_grad():
                output = self.gnn(x_dict, edge_index_dict)

            controversy = float(output["controversy"].mean().item())
            consensus = float(output["consensus"].mean().item())

            return {
                "controversy_score": round(controversy, 3),
                "consensus_score": round(consensus, 3),
                "emerging_topic_score": round(1.0 - consensus, 3),
            }
        except Exception:
            return self._fallback_prediction()

    def _build_node_dict(self) -> Dict:
        """Build node feature dictionary for GNN."""
        node_dict = {}
        for (node_type, node_id), features in self.node_features.items():
            if node_type not in node_dict:
                node_dict[node_type] = []
            node_dict[node_type].append(features)

        for node_type in node_dict:
            if node_dict[node_type]:
                node_dict[node_type] = torch.stack(node_dict[node_type])
            else:
                node_dict[node_type] = torch.zeros((1, 128), dtype=torch.float32)

        return node_dict

    def _build_edge_dict(self) -> Dict:
        """Build edge index dictionary for GNN."""
        edge_dict = {}
        for edge_key, edges in self.edge_indices.items():
            if not edges:
                continue
            edge_indices = list(zip(*edges))
            if len(edge_indices) == 2:
                edge_dict[edge_key] = torch.tensor(edge_indices, dtype=torch.long)

        return edge_dict

    def _fallback_prediction(self) -> Dict[str, float]:
        """Fallback prediction when GNN is unavailable."""
        return {
            "controversy_score": 0.5,
            "consensus_score": 0.5,
            "emerging_topic_score": 0.5,
        }
