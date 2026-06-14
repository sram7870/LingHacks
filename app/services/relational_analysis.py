import math
import logging
from typing import Dict, List, Optional, Any
import numpy as np

from app.schemas import RelationalAnalysisResult, ClaimCAS, ClaimCNS
from app.services.controversy_gnn import ControversyGraphBuilder

logger = logging.getLogger(__name__)


class RelationalAnalyzer:
    """
    RelationalAnalyzer performs cross-literature positioning of a single input paper
    against the broader corpus already stored in Neo4j.
    """

    def __init__(self, graph_client, gnn_model, evolution_tracker):
        """
        Initialize the RelationalAnalyzer with references to system services.

        Args:
            graph_client: Existing Neo4j client from graph.py.
            gnn_model: Existing ControversyGNN instance.
            evolution_tracker: Existing SemanticEvolution instance.
        """
        self.graph_client = graph_client
        self.gnn_model = gnn_model
        self.evolution_tracker = evolution_tracker
        self.landscape_paper_titles = None

    def _get_total_papers_count(self) -> int:
        """Count the total number of Paper nodes currently stored in Neo4j (filtered by landscape if provided)."""
        if self.graph_client is None or not getattr(self.graph_client, "available", False):
            logger.warning("Neo4j client unavailable during paper count.")
            return 0

        try:
            with self.graph_client.driver.session() as session:
                if self.landscape_paper_titles:
                    res = session.run("MATCH (p:Paper) WHERE p.title IN $titles RETURN count(p) AS count", titles=self.landscape_paper_titles)
                else:
                    res = session.run("MATCH (p:Paper) RETURN count(p) AS count")
                single = res.single()
                return single["count"] if single else 0
        except Exception as exc:
            logger.error("Failed to count papers in Neo4j: %s", exc)
            return 0

    def analyze(
        self,
        paper_id: str,
        paper_title: str,
        paper_year: int,
        extracted_claims: List[Any],
        methodology_quality: float,
        stance_label: str,
        landscape_paper_titles: Optional[List[str]] = None,
    ) -> RelationalAnalysisResult:
        self.landscape_paper_titles = landscape_paper_titles
        claim_dicts = [self._claim_to_dict(claim) for claim in extracted_claims]

        # Check if the corpus (or landscape) has fewer than 2 papers total
        total_papers = self._get_total_papers_count()
        
        if total_papers < 2:
            diag_msg = f"Insufficient data: found only {total_papers} papers in "
            diag_msg += f"landscape (filtered from {len(landscape_paper_titles) if landscape_paper_titles else 'global'}) "
            diag_msg += "matching the selected criteria in the knowledge graph. "
            diag_msg += "Ensure papers are analyzed on the homepage first."
            
            return RelationalAnalysisResult(
                paper_id=paper_id,
                paper_title=paper_title,
                aggregate_cas=None,
                cas_interpretation=None,
                per_claim_cas=[],
                fci_score=None,
                fci_label=None,
                subgraph_paper_count=total_papers,
                edge_controversy_ratio=None,
                stance_distribution=None,
                mss_percentile=None,
                mss_label=None,
                contradicting_papers_median_quality=None,
                methodological_underdog=None,
                comparison_pool_size=0,
                aggregate_cns=None,
                cns_interpretation=None,
                per_claim_cns=[],
                publication_year=paper_year,
                field_trajectory_at_publication=None,
                alignment_with_trajectory=None,
                debate_maturity=None,
                papers_published_same_period=None,
                drift_velocity_at_publication=None,
                corpus_too_small=True,
                message=diag_msg
            )

        try:
            cas = self._compute_cas(claim_dicts, paper_title)
            fci = self._compute_fci(paper_id, paper_title, stance_label)
            mss = self._compute_mss(paper_id, paper_title, methodology_quality, stance_label, claim_dicts)
            cns = self._compute_cns(claim_dicts, paper_title, cas["per_claim_cas"])
            tfp = self._compute_tfp(paper_id, paper_title, paper_year, stance_label)
        except Exception as exc:
            logger.exception("Relational analysis failed for %s", paper_title)
            return RelationalAnalysisResult(
                paper_id=paper_id,
                paper_title=paper_title,
                publication_year=paper_year,
                corpus_too_small=False,
                message=f"Relational analysis failed: {exc}",
            )

        return RelationalAnalysisResult(
            paper_id=paper_id,
            paper_title=paper_title,
            aggregate_cas=cas["aggregate_cas"],
            cas_interpretation=cas["cas_interpretation"],
            per_claim_cas=cas["per_claim_cas"],
            fci_score=fci["fci_score"],
            fci_label=fci["fci_label"],
            subgraph_paper_count=fci["subgraph_paper_count"],
            edge_controversy_ratio=fci["edge_controversy_ratio"],
            stance_distribution=fci["stance_distribution"],
            mss_percentile=mss["mss_percentile"],
            mss_label=mss["mss_label"],
            contradicting_papers_median_quality=mss["contradicting_papers_median_quality"],
            methodological_underdog=mss["methodological_underdog"],
            comparison_pool_size=mss["comparison_pool_size"],
            aggregate_cns=cns["aggregate_cns"],
            cns_interpretation=cns["cns_interpretation"],
            per_claim_cns=cns["per_claim_cns"],
            publication_year=paper_year,
            field_trajectory_at_publication=tfp["field_trajectory_at_publication"],
            alignment_with_trajectory=tfp["alignment_with_trajectory"],
            debate_maturity=tfp["debate_maturity"],
            papers_published_same_period=tfp["papers_published_same_period"],
            drift_velocity_at_publication=tfp["drift_velocity_at_publication"],
            corpus_too_small=False,
            message=None,
        )

    def _claim_to_dict(self, claim: Any) -> Dict[str, Any]:
        if isinstance(claim, dict):
            return claim
        if hasattr(claim, "model_dump"):
            return claim.model_dump()
        if hasattr(claim, "dict"):
            return claim.dict()
        return {
            "text": getattr(claim, "text", ""),
            "polarity": getattr(claim, "polarity", "neutral"),
            "confidence": getattr(claim, "confidence", 0.0),
            "embedding": getattr(claim, "embedding", None),
        }

    def _compute_cas(self, extracted_claims: List[dict], input_title: str, K: int = 20) -> dict:
        """
        Compute Consensus Alignment Score (CAS).
        Measures semantic and stance consensus of the corpus for each input claim.
        """
        with self.graph_client.driver.session() as session:
            # Query all claims from other papers that have embeddings
            query = """
                MATCH (p:Paper)-[:SUPPORTED_BY|MAKES_CLAIM]-(c:Claim)
                WHERE p.title <> $input_title AND c.embedding IS NOT NULL
            """
            if self.landscape_paper_titles:
                query += " AND p.title IN $titles"
            
            query += """
                RETURN DISTINCT c.text AS text, c.embedding AS embedding,
                                p.stance_label AS stance_label,
                                COALESCE(p.methodology_quality, p.methodological_quality, 0.5) AS method_quality
            """
            
            res = session.run(query, input_title=input_title, titles=self.landscape_paper_titles)
            existing_claims = []
            for record in res:
                existing_claims.append({
                    "text": record["text"],
                    "embedding": record["embedding"],
                    "stance_label": record["stance_label"] or "neutral",
                    "method_quality": record["method_quality"] if record["method_quality"] is not None else 0.5
                })

        per_claim_cas = []
        all_cas_scores = []

        for claim in extracted_claims:
            claim_text = claim["text"]
            claim_emb = claim.get("embedding")

            if not claim_emb or not existing_claims:
                per_claim_cas.append(ClaimCAS(
                    claim_text=claim_text,
                    cas_score=0.5,
                    supporting_count=0,
                    contradicting_count=0,
                    neutral_count=0,
                    low_corpus_coverage=True
                ))
                all_cas_scores.append(0.5)
                continue

            # Compute similarities
            similarities = []
            for ec in existing_claims:
                sim = self._cosine_similarity(claim_emb, ec["embedding"])
                similarities.append((sim, ec))

            # Sort by similarity descending, take top K
            similarities.sort(key=lambda x: x[0], reverse=True)
            top_k_matches = similarities[:K]

            supporting_count = 0
            contradicting_count = 0
            neutral_count = 0

            weighted_stance_sum = 0.0
            method_quality_sum = 0.0

            for sim, ec in top_k_matches:
                stance = ec["stance_label"]
                quality = ec["method_quality"]

                # Map stance to weight: 1.0 supporting, 0.5 neutral, 0.0 contradicting/opposing
                if stance == "supporting":
                    stance_weight = 1.0
                    supporting_count += 1
                elif stance in ("opposing", "contradicting"):
                    stance_weight = 0.0
                    contradicting_count += 1
                else:
                    stance_weight = 0.5
                    neutral_count += 1

                weighted_stance_sum += stance_weight * quality
                method_quality_sum += quality

            if method_quality_sum > 0:
                cas_score = weighted_stance_sum / method_quality_sum
            else:
                cas_score = 0.5

            low_coverage = len(top_k_matches) < 5

            per_claim_cas.append(ClaimCAS(
                claim_text=claim_text,
                cas_score=round(cas_score, 4),
                supporting_count=supporting_count,
                contradicting_count=contradicting_count,
                neutral_count=neutral_count,
                low_corpus_coverage=low_coverage
            ))
            all_cas_scores.append(cas_score)

        aggregate_cas = np.mean(all_cas_scores) if all_cas_scores else 0.5
        aggregate_cas = round(float(aggregate_cas), 4)

        if aggregate_cas > 0.75:
            interpretation = "Strong Consensus"
        elif aggregate_cas >= 0.5:
            interpretation = "Moderate Consensus"
        elif aggregate_cas >= 0.25:
            interpretation = "Contested"
        else:
            interpretation = "Contrary to Field"

        return {
            "per_claim_cas": per_claim_cas,
            "aggregate_cas": aggregate_cas,
            "cas_interpretation": interpretation
        }

    def _compute_fci(self, paper_id: str, paper_title: str, stance_label: str) -> dict:
        """
        Compute Field Controversy Index (FCI).
        Blends GNN controversy prediction with topological graph controversy proxies.
        """
        with self.graph_client.driver.session() as session:
            # Query paper nodes within 2 hops
            query_papers = """
                MATCH (p:Paper {title: $title})
                OPTIONAL MATCH (p)-[:SUPPORTED_BY|CITES|USES_METHOD*..2]-(other:Paper)
                WHERE other <> p
            """
            if self.landscape_paper_titles:
                query_papers += " AND other.title IN $titles"
            
            query_papers += " RETURN DISTINCT other.title AS title, other.stance_label AS stance_label"
            
            res_papers = session.run(query_papers, title=paper_title, titles=self.landscape_paper_titles)
            subgraph_papers = [{"title": paper_title, "stance_label": stance_label}]
            for record in res_papers:
                if record["title"] is not None:
                    subgraph_papers.append({
                        "title": record["title"],
                        "stance_label": record["stance_label"] or "neutral"
                    })

            # Query claim nodes in the subgraph
            query_claims = """
                MATCH (p:Paper)-[:SUPPORTED_BY|MAKES_CLAIM]-(c:Claim)
                WHERE (p.title = $title OR (p)-[:SUPPORTED_BY|CITES|USES_METHOD*..2]-(:Paper {title: $title}))
            """
            if self.landscape_paper_titles:
                query_claims += " AND p.title IN ($titles + [$title])"
            
            query_claims += """
                RETURN DISTINCT p.title AS paper_title, c.text AS claim_text,
                                COALESCE(c.confidence, 0.5) AS confidence
            """
            
            res_claims = session.run(query_claims, title=paper_title, titles=self.landscape_paper_titles)
            subgraph_claims = []
            for record in res_claims:
                subgraph_claims.append({
                    "paper_title": record["paper_title"],
                    "claim_text": record["claim_text"],
                    "confidence": record["confidence"]
                })

            # Count contradictions and supports edges
            query_edges = """
                MATCH (p:Paper)-[:SUPPORTED_BY|MAKES_CLAIM]-(c:Claim)
                WHERE (p.title = $title OR (p)-[:SUPPORTED_BY|CITES|USES_METHOD*..2]-(:Paper {title: $title}))
            """
            if self.landscape_paper_titles:
                query_edges += " AND p.title IN ($titles + [$title])"
                
            query_edges += """
                WITH DISTINCT c
                MATCH (c)-[r:CONTRADICTS|SUPPORTS]-(other:Claim)
                RETURN type(r) AS rel_type, count(r) AS count
            """
            
            res_edges = session.run(query_edges, title=paper_title, titles=self.landscape_paper_titles)
            contradicts_count = 0
            supports_count = 0
            for record in res_edges:
                if record["rel_type"] == "CONTRADICTS":
                    contradicts_count += record["count"]
                elif record["rel_type"] == "SUPPORTS":
                    supports_count += record["count"]

            # Query paper-to-paper citations (via shared Citation nodes)
            query_citations = """
                MATCH (p1:Paper)-[:CITES]->(c:Citation)<-[:CITES]-(p2:Paper)
                WHERE p1 <> p2 AND
                      (p1.title = $title OR (p1)-[:SUPPORTED_BY|CITES|USES_METHOD*..2]-(:Paper {title: $title})) AND
                      (p2.title = $title OR (p2)-[:SUPPORTED_BY|CITES|USES_METHOD*..2]-(:Paper {title: $title}))
            """
            if self.landscape_paper_titles:
                query_citations += " AND p1.title IN ($titles + [$title]) AND p2.title IN ($titles + [$title])"
            
            query_citations += " RETURN DISTINCT p1.title AS from_title, p2.title AS to_title"
            
            res_citations = session.run(query_citations, title=paper_title, titles=self.landscape_paper_titles)
            citations = []
            for record in res_citations:
                citations.append((record["from_title"], record["to_title"]))

        # Build local GNN graph input representation and score
        builder = ControversyGraphBuilder()
        if self.gnn_model is not None:
            builder.gnn = self.gnn_model

        for paper in subgraph_papers:
            builder.add_paper_node(paper["title"], np.ones(128))
        for claim in subgraph_claims:
            builder.add_claim_node(claim["claim_text"], np.ones(128) * claim["confidence"])
            builder.add_claim_edge(claim["paper_title"], claim["claim_text"])
        for from_t, to_t in citations:
            builder.add_citation_edge(from_t, to_t)

        gnn_res = builder.predict_controversy()
        gnn_controversy_score = gnn_res.get("controversy_score", 0.5)

        total_edges = contradicts_count + supports_count
        edge_controversy_ratio = contradicts_count / total_edges if total_edges > 0 else 0.0

        # Compile stance distribution & normalized Shannon entropy
        stance_distribution = {"supporting": 0, "opposing": 0, "neutral": 0}
        for paper in subgraph_papers:
            s = paper["stance_label"]
            if s in stance_distribution:
                stance_distribution[s] += 1
            else:
                stance_distribution["neutral"] += 1

        subgraph_paper_count = len(subgraph_papers)
        stance_entropy = 0.0
        if subgraph_paper_count > 0:
            for count in stance_distribution.values():
                if count > 0:
                    p_i = count / subgraph_paper_count
                    stance_entropy -= p_i * math.log2(p_i)

        stance_entropy_normalized = stance_entropy / math.log2(3)

        # Blended FCI score
        fci_score = 0.6 * (gnn_controversy_score * 100.0) + \
                    0.25 * (edge_controversy_ratio * 100.0) + \
                    0.15 * (stance_entropy_normalized * 100.0)

        fci_score = round(fci_score, 4)

        if fci_score < 20:
            fci_label = "Settled"
        elif fci_score <= 45:
            fci_label = "Emerging Debate"
        elif fci_score <= 70:
            fci_label = "Actively Contested"
        else:
            fci_label = "Deeply Polarized"

        return {
            "fci_score": fci_score,
            "fci_label": fci_label,
            "subgraph_paper_count": subgraph_paper_count,
            "edge_controversy_ratio": round(edge_controversy_ratio, 4),
            "stance_distribution": stance_distribution
        }

    def _compute_mss(
        self,
        paper_id: str,
        paper_title: str,
        methodology_quality: float,
        stance_label: str,
        extracted_claims: List[dict]
    ) -> dict:
        """
        Compute Methodological Standing Score (MSS).
        Calculates percentile rank of paper methodology quality relative to local debate.
        """
        with self.graph_client.driver.session() as session:
            # Query papers connected via Claim supports/contradicts relationships
            query_conn = """
                MATCH (p1:Paper {title: $title})-[r1:SUPPORTED_BY|MAKES_CLAIM]-(c1:Claim)-[r:SUPPORTS|CONTRADICTS]-(c2:Claim)-[r2:SUPPORTED_BY|MAKES_CLAIM]-(p2:Paper)
                WHERE p2 <> p1
            """
            if self.landscape_paper_titles:
                query_conn += " AND p2.title IN $titles"
            
            query_conn += """
                RETURN DISTINCT p2.title AS title,
                                COALESCE(p2.methodology_quality, p2.methodological_quality, 0.5) AS methodology_quality,
                                p2.stance_label AS stance_label,
                                type(r) AS rel_type
            """
            
            res_conn = session.run(query_conn, title=paper_title, titles=self.landscape_paper_titles)
            connected_papers = {}
            for record in res_conn:
                title = record["title"]
                connected_papers[title] = {
                    "title": title,
                    "methodology_quality": record["methodology_quality"] if record["methodology_quality"] is not None else 0.5,
                    "stance_label": record["stance_label"] or "neutral",
                    "rel_type": record["rel_type"]
                }

            # Query all claims from other papers to find semantically similar ones
            query_all = """
                MATCH (p:Paper)-[:SUPPORTED_BY|MAKES_CLAIM]-(c:Claim)
                WHERE p.title <> $title AND c.embedding IS NOT NULL
            """
            if self.landscape_paper_titles:
                query_all += " AND p.title IN $titles"
                
            query_all += """
                RETURN p.title AS title,
                       COALESCE(p.methodology_quality, p.methodological_quality, 0.5) AS methodology_quality,
                       p.stance_label AS stance_label,
                       c.embedding AS embedding
            """
            
            res_all_claims = session.run(query_all, title=paper_title, titles=self.landscape_paper_titles)

            paper_max_sims = {}
            for record in res_all_claims:
                p_title = record["title"]
                p_quality = record["methodology_quality"] if record["methodology_quality"] is not None else 0.5
                p_stance = record["stance_label"] or "neutral"
                ec_emb = record["embedding"]

                max_sim = -1.0
                for claim in extracted_claims:
                    claim_emb = claim.get("embedding")
                    if claim_emb:
                        sim = self._cosine_similarity(claim_emb, ec_emb)
                        if sim > max_sim:
                            max_sim = sim

                if p_title not in paper_max_sims:
                    paper_max_sims[p_title] = {
                        "title": p_title,
                        "methodology_quality": p_quality,
                        "stance_label": p_stance,
                        "max_sim": max_sim
                    }
                else:
                    if max_sim > paper_max_sims[p_title]["max_sim"]:
                        paper_max_sims[p_title]["max_sim"] = max_sim

        # Select top 20 semantically similar papers
        sorted_similar_papers = sorted(paper_max_sims.values(), key=lambda x: x["max_sim"], reverse=True)
        top_similar_papers = sorted_similar_papers[:20]

        # Assemble the comparison pool
        comparison_pool = {}
        for title, p_info in connected_papers.items():
            comparison_pool[title] = {
                "title": title,
                "methodology_quality": p_info["methodology_quality"],
                "stance_label": p_info["stance_label"],
                "is_contradiction": p_info["rel_type"] == "CONTRADICTS"
            }

        for p_info in top_similar_papers:
            title = p_info["title"]
            if title not in comparison_pool:
                is_contradiction = False
                if stance_label == "supporting" and p_info["stance_label"] == "opposing":
                    is_contradiction = True
                elif stance_label == "opposing" and p_info["stance_label"] == "supporting":
                    is_contradiction = True

                comparison_pool[title] = {
                    "title": title,
                    "methodology_quality": p_info["methodology_quality"],
                    "stance_label": p_info["stance_label"],
                    "is_contradiction": is_contradiction
                }

        pool_list = list(comparison_pool.values())
        comparison_pool_size = len(pool_list)

        # Compute percentile rank (including the input paper score itself)
        all_scores = [p["methodology_quality"] for p in pool_list] + [methodology_quality]
        below = sum(1 for s in all_scores if s < methodology_quality)
        equal = sum(1 for s in all_scores if s == methodology_quality)
        mss_percentile = (below + 0.5 * equal) / len(all_scores) * 100.0 if all_scores else 50.0
        mss_percentile = round(mss_percentile, 4)

        if mss_percentile > 75:
            mss_label = "Methodologically Strong"
        elif mss_percentile >= 25:
            mss_label = "Average"
        else:
            mss_label = "Methodologically Weak"

        # Separate contradiction-based standing
        contradicting_scores = [p["methodology_quality"] for p in pool_list if p["is_contradiction"]]
        if contradicting_scores:
            contradicting_papers_median_quality = float(np.median(contradicting_scores))
            methodological_underdog = methodology_quality < contradicting_papers_median_quality
        else:
            contradicting_papers_median_quality = 0.0
            methodological_underdog = False

        return {
            "mss_percentile": mss_percentile,
            "mss_label": mss_label,
            "contradicting_papers_median_quality": round(contradicting_papers_median_quality, 4),
            "methodological_underdog": underdog_check(methodological_underdog),
            "comparison_pool_size": comparison_pool_size
        }

    def _compute_cns(
        self,
        extracted_claims: List[dict],
        paper_title: str,
        per_claim_cas: List[ClaimCAS]
    ) -> dict:
        """
        Compute Claim Novelty Score (CNS).
        Quantifies claim novelty relative to other claim embeddings, using FAISS if count exceeds 10,000.
        """
        with self.graph_client.driver.session() as session:
            query = """
                MATCH (p:Paper)-[:SUPPORTED_BY|MAKES_CLAIM]-(c:Claim)
                WHERE p.title <> $title AND c.embedding IS NOT NULL
            """
            if self.landscape_paper_titles:
                query += " AND p.title IN $titles"
                
            query += " RETURN DISTINCT c.text AS text, c.embedding AS embedding"
            
            res = session.run(query, title=paper_title, titles=self.landscape_paper_titles)
            existing_claims = []
            for record in res:
                existing_claims.append({
                    "text": record["text"],
                    "embedding": record["embedding"]
                })

        try:
            import faiss
            HAS_FAISS = True
        except ImportError:
            HAS_FAISS = False

        use_faiss = HAS_FAISS and len(existing_claims) > 10000
        faiss_index = None

        if use_faiss:
            embeddings_matrix = np.array([ec["embedding"] for ec in existing_claims], dtype=np.float32)
            d = embeddings_matrix.shape[1]
            faiss_index = faiss.IndexFlatIP(d)
            # Normalize to unit length
            norms = np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1e-8
            normalized_embeddings = embeddings_matrix / norms
            faiss_index.add(normalized_embeddings)

        per_claim_cns = []
        all_cns_scores = []

        cas_by_claim = {cas.claim_text: cas.cas_score for cas in per_claim_cas}

        for claim in extracted_claims:
            claim_text = claim["text"]
            claim_emb = claim.get("embedding")

            if not claim_emb or not existing_claims:
                per_claim_cns.append(ClaimCNS(
                    claim_text=claim_text,
                    cns_score=1.0,
                    most_similar_existing_claim="None",
                    similarity_score=0.0,
                    replication_candidate=False
                ))
                all_cns_scores.append(1.0)
                continue

            query_vec = np.array(claim_emb, dtype=np.float32)

            if use_faiss:
                q_norm = np.linalg.norm(query_vec)
                q_vec_normed = query_vec / q_norm if q_norm > 0 else query_vec
                D, I = faiss_index.search(np.array([q_vec_normed], dtype=np.float32), 1)
                best_sim = float(D[0][0])
                idx = I[0][0]
                best_claim = existing_claims[idx]["text"] if idx >= 0 else "None"
            else:
                best_sim = -1.0
                best_claim = "None"
                for ec in existing_claims:
                    sim = self._cosine_similarity(claim_emb, ec["embedding"])
                    if sim > best_sim:
                        best_sim = sim
                        best_claim = ec["text"]

            cns_score = 1.0 - best_sim
            cns_score = max(0.0, min(1.0, cns_score))

            claim_cas = cas_by_claim.get(claim_text, 0.5)
            replication_candidate = (cns_score < 0.15) and (claim_cas > 0.7)

            per_claim_cns.append(ClaimCNS(
                claim_text=claim_text,
                cns_score=round(cns_score, 4),
                most_similar_existing_claim=best_claim,
                similarity_score=round(best_sim, 4),
                replication_candidate=replication_candidate
            ))
            all_cns_scores.append(cns_score)

        aggregate_cns = np.mean(all_cns_scores) if all_cns_scores else 1.0
        aggregate_cns = round(float(aggregate_cns), 4)

        if aggregate_cns > 0.75:
            interpretation = "Highly Novel"
        elif aggregate_cns >= 0.5:
            interpretation = "Moderately Novel"
        elif aggregate_cns >= 0.25:
            interpretation = "Incremental"
        else:
            interpretation = "Restatement/Replication"

        return {
            "per_claim_cns": per_claim_cns,
            "aggregate_cns": aggregate_cns,
            "cns_interpretation": interpretation
        }

    def _compute_tfp(self, paper_id: str, paper_title: str, paper_year: int, stance_label: str) -> dict:
        """
        Compute Temporal Field Position (TFP).
        Analyzes field trajectories, publications, and semantic drift at publication year.
        """
        with self.graph_client.driver.session() as session:
            # Query sub-graph papers and publication years
            query = """
                MATCH (p:Paper {title: $title})
                OPTIONAL MATCH (p)-[:SUPPORTED_BY|CITES|USES_METHOD*..2]-(other:Paper)
                WHERE other <> p
            """
            if self.landscape_paper_titles:
                query += " AND other.title IN $titles"
            
            query += """
                RETURN DISTINCT other.title AS title,
                                COALESCE(other.year, 2026) AS year
            """
            
            res = session.run(query, title=paper_title, titles=self.landscape_paper_titles)
            subgraph_papers = [{"title": paper_title, "year": paper_year}]
            for record in res:
                if record["title"] is not None:
                    subgraph_papers.append({
                        "title": record["title"],
                        "year": record["year"] if record["year"] is not None else 2026
                    })

        subgraph_papers.sort(key=lambda x: x["year"])
        subgraph_years = [p["year"] for p in subgraph_papers]

        if len(subgraph_years) < 2:
            debate_maturity = "Foundational"
        else:
            try:
                idx = subgraph_years.index(paper_year)
                pct = idx / (len(subgraph_years) - 1)
            except ValueError:
                pct = 0.5

            if pct <= 0.2:
                debate_maturity = "Foundational"
            elif pct >= 0.8:
                debate_maturity = "Late-Stage"
            else:
                debate_maturity = "Mid-Debate"

        same_period_papers = [p for p in subgraph_papers if paper_year - 2 <= p["year"] <= paper_year + 2]
        papers_published_same_period = len(same_period_papers)

        snapshots = self.evolution_tracker.snapshots.get("lyme_disease", [])
        if not snapshots and self.evolution_tracker.snapshots:
            first_topic = next(iter(self.evolution_tracker.snapshots.keys()))
            snapshots = self.evolution_tracker.snapshots[first_topic]

        by_year = {}
        for s in snapshots:
            if s.year not in by_year:
                by_year[s.year] = []
            by_year[s.year].append(s.embedding)

        avg_embeddings = {}
        for y, embs in by_year.items():
            avg_embeddings[y] = np.mean(embs, axis=0)

        sorted_years = sorted(avg_embeddings.keys())
        drift_by_year = {}
        for i in range(len(sorted_years) - 1):
            y_curr = sorted_years[i]
            y_next = sorted_years[i+1]
            dist = np.linalg.norm(avg_embeddings[y_curr] - avg_embeddings[y_next])
            drift_by_year[y_next] = float(dist)

        drift_vals = []
        for yr in sorted(drift_by_year.keys()):
            if paper_year - 3 <= yr <= paper_year:
                drift_vals.append(drift_by_year[yr])

        if len(drift_vals) < 2:
            field_trajectory_at_publication = "Insufficient Data"
        else:
            diffs = np.diff(drift_vals)
            mean_diff = np.mean(diffs)
            if mean_diff < -1e-5:
                field_trajectory_at_publication = "Converging"
            elif mean_diff > 1e-5:
                field_trajectory_at_publication = "Diverging"
            else:
                field_trajectory_at_publication = "Stable"

        if field_trajectory_at_publication == "Converging":
            if stance_label == "supporting":
                alignment_with_trajectory = "Aligned"
            elif stance_label == "opposing":
                alignment_with_trajectory = "Contrarian"
            else:
                alignment_with_trajectory = "Neutral"
        elif field_trajectory_at_publication == "Diverging":
            if stance_label == "opposing":
                alignment_with_trajectory = "Aligned"
            elif stance_label == "supporting":
                alignment_with_trajectory = "Contrarian"
            else:
                alignment_with_trajectory = "Neutral"
        else:
            alignment_with_trajectory = "Neutral"

        drift_velocity_at_publication = drift_by_year.get(paper_year, 0.0)
        if drift_velocity_at_publication == 0.0 and drift_vals:
            drift_velocity_at_publication = float(np.mean(drift_vals))

        return {
            "field_trajectory_at_publication": field_trajectory_at_publication,
            "alignment_with_trajectory": alignment_with_trajectory,
            "debate_maturity": debate_maturity,
            "papers_published_same_period": papers_published_same_period,
            "drift_velocity_at_publication": round(drift_velocity_at_publication, 4)
        }

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2 + 1e-8))


def underdog_check(val: bool) -> bool:
    """Helper function to cast or check boolean value."""
    return bool(val)
