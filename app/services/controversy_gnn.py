from typing import Dict, List, Optional, Tuple
import logging
import torch
import torch.nn as nn
import numpy as np

logger = logging.getLogger(__name__)

try:
    from torch_geometric.nn import HeteroConv, GATConv
    from torch_geometric.data import HeteroData

    try:
        HeteroConv({
            ("paper", "cites", "paper"): GATConv((-1, -1), 16, add_self_loops=False),
            ("paper", "contains", "claim"): GATConv((-1, -1), 16, add_self_loops=False),
            ("claim", "from", "paper"): GATConv((-1, -1), 16, add_self_loops=False),
        }, aggr="mean")
        HAS_PYTORCH_GEOMETRIC = True
    except Exception as exc:
        logger.warning("Torch Geometric installed but incompatible: %s", exc)
        HAS_PYTORCH_GEOMETRIC = False
except Exception as exc:
    logger.warning("Torch Geometric import failed: %s", exc)
    HAS_PYTORCH_GEOMETRIC = False


class ControversyGNN(nn.Module):
    """Heterogeneous Graph Neural Network for predicting controversy and consensus."""

    def __init__(self, hidden_dim: int = 128, num_layers: int = 2):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.layers = None
        self.controversy_head = None
        self.consensus_head = None
        self.initialized = False

        if HAS_PYTORCH_GEOMETRIC:
            try:
                self.layers = nn.ModuleList([
                    HeteroConv({
                        ("paper", "cites", "paper"): GATConv((-1, -1), hidden_dim, add_self_loops=False),
                        ("paper", "contains", "claim"): GATConv((-1, -1), hidden_dim, add_self_loops=False),
                        ("claim", "from", "paper"): GATConv((-1, -1), hidden_dim, add_self_loops=False),
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
                self.initialized = True
            except Exception as exc:
                logger.warning("Failed to initialize ControversyGNN, falling back to deterministic behavior: %s", exc)
                self.layers = None
                self.controversy_head = None
                self.consensus_head = None
                self.initialized = False

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
        try:
            self.gnn = ControversyGNN() if HAS_PYTORCH_GEOMETRIC else None
            if self.gnn is not None and not self.gnn.initialized:
                logger.warning("ControversyGNN fallback active because initialization did not complete successfully.")
                self.gnn = None
        except Exception as exc:
            logger.warning("ControversyGraphBuilder failed to initialize, falling back: %s", exc)
            self.gnn = None
        
        self.node_features = {}  # (node_type, node_id) -> features
        self.edge_indices = {}   # (src_type, rel, dst_type) -> List[Tuple[src_id, dst_id]]
        self.id_maps = {}        # node_type -> {node_id -> index}

    def _get_index(self, node_type: str, node_id: str) -> int:
        """Get or create index for a node ID."""
        if node_type not in self.id_maps:
            self.id_maps[node_type] = {}
        if node_id not in self.id_maps[node_type]:
            self.id_maps[node_type][node_id] = len(self.id_maps[node_type])
        return self.id_maps[node_type][node_id]

    def add_paper_node(self, paper_id: str, features: np.ndarray) -> None:
        """Add a paper node with features."""
        idx = self._get_index("paper", paper_id)
        self.node_features[("paper", paper_id)] = torch.tensor(features, dtype=torch.float32)

    def add_claim_node(self, claim_id: str, features: np.ndarray) -> None:
        """Add a claim node with features."""
        idx = self._get_index("claim", claim_id)
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

            if not x_dict or not edge_index_dict:
                return self._fallback_prediction()

            with torch.no_grad():
                output = self.gnn(x_dict, edge_index_dict)

            controversy = float(output["controversy"].mean().item())
            consensus = float(output["consensus"].mean().item())

            return {
                "controversy_score": round(controversy, 3),
                "consensus_score": round(consensus, 3),
                "emerging_topic_score": round(1.0 - consensus, 3),
            }
        except Exception as exc:
            logger.warning("GNN prediction failed: %s", exc)
            return self._fallback_prediction()

    def _build_node_dict(self) -> Dict:
        """Build node feature dictionary for GNN."""
        node_dict = {}
        for node_type, id_map in self.id_maps.items():
            indices = sorted(id_map.values())
            # Map index back to features
            rev_map = {idx: nid for nid, idx in id_map.items()}
            features_list = []
            for idx in indices:
                nid = rev_map[idx]
                feat = self.node_features.get((node_type, nid))
                if feat is None:
                    feat = torch.zeros(128, dtype=torch.float32)
                features_list.append(feat)
            
            if features_list:
                node_dict[node_type] = torch.stack(features_list)
            else:
                node_dict[node_type] = torch.zeros((1, 128), dtype=torch.float32)

        return node_dict

    def _build_edge_dict(self) -> Dict:
        """Build edge index dictionary for GNN."""
        edge_dict = {}
        for (src_type, rel, dst_type), edges in self.edge_indices.items():
            if not edges:
                continue
            
            indices = []
            for src_id, dst_id in edges:
                src_idx = self._get_index(src_type, src_id)
                dst_idx = self._get_index(dst_type, dst_id)
                indices.append([src_idx, dst_idx])
            
            if indices:
                # [2, num_edges]
                edge_dict[(src_type, rel, dst_type)] = torch.tensor(indices, dtype=torch.long).t().contiguous()

        return edge_dict

    def _fallback_prediction(self) -> Dict[str, float]:
        """Fallback prediction when GNN is unavailable."""
        return {
            "controversy_score": 0.5,
            "consensus_score": 0.5,
            "emerging_topic_score": 0.5,
        }
