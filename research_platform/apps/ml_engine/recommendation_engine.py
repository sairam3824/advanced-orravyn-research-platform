import logging
import os

import numpy as np
from django.db.models import Count
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from apps.accounts.models import User
from apps.ml_engine.models import PaperEmbedding, UserRecommendation
from apps.papers.models import Bookmark, Paper, Rating

logger = logging.getLogger(__name__)

_FUSION_MODEL_PATH = os.path.join(os.path.dirname(__file__), "signal_fusion_weights.npy")


class SignalFusionAttention:
    """
    Learned attention over three recommendation signals:
      [0] content-based   (embedding similarity)
      [1] collaborative   (similar-user preference)
      [2] popularity      (citation + download counts)

    The weight vector W ∈ R^3 is learned from implicit feedback via a
    lightweight softmax attention conditioned on user profile richness.

    Features used for attention:
      f0 = number of rated papers by user  (interaction depth)
      f1 = number of bookmarked papers
      f2 = number of group memberships

    A linear layer maps f → logits → softmax → [alpha, beta, gamma].
    Falls back to (0.6, 0.3, 0.1) when no model is trained yet.
    """

    _DEFAULT = np.array([0.6, 0.3, 0.1], dtype=np.float32)

    def __init__(self, n_features: int = 3, n_signals: int = 3):
        self.n_features = n_features
        self.n_signals  = n_signals
        self.W: np.ndarray = np.zeros((n_signals, n_features), dtype=np.float32)
        self.b: np.ndarray = np.log(self._DEFAULT)   # softmax bias init
        self._trained = False
        self._try_load()

    def _try_load(self):
        if os.path.exists(_FUSION_MODEL_PATH):
            try:
                data = np.load(_FUSION_MODEL_PATH, allow_pickle=True).item()
                self.W = data["W"]
                self.b = data["b"]
                self._trained = True
                logger.debug("SignalFusionAttention: loaded from %s", _FUSION_MODEL_PATH)
            except Exception as exc:
                logger.warning("SignalFusionAttention: load failed (%s), using defaults.", exc)

    def save(self, path: str = _FUSION_MODEL_PATH):
        np.save(path, {"W": self.W, "b": self.b})
        logger.info("SignalFusionAttention saved to %s", path)

    def get_weights(self, user) -> tuple:
        """
        Return (alpha, beta, gamma) conditioned on user's interaction profile.
        Falls back to defaults when model is untrained.
        """
        try:
            f = self._user_features(user)
            logits = self.W @ f + self.b
            exp_l  = np.exp(logits - logits.max())
            weights = exp_l / exp_l.sum()
            return float(weights[0]), float(weights[1]), float(weights[2])
        except Exception:
            return 0.6, 0.3, 0.1

    @staticmethod
    def _user_features(user) -> np.ndarray:
        n_rated     = Rating.objects.filter(user=user).count()
        n_bookmarked = Bookmark.objects.filter(user=user).count()
        try:
            from apps.groups.models import GroupMember
            n_groups = GroupMember.objects.filter(user=user).count()
        except Exception:
            n_groups = 0
        return np.array([n_rated, n_bookmarked, n_groups], dtype=np.float32)

    def train(self, feedback_samples: list, lr: float = 0.01, epochs: int = 50):
        """
        Train with implicit feedback.

        feedback_samples: list of dicts:
          {"user": User, "clicked_signal": int}
          where clicked_signal ∈ {0=content, 1=collaborative, 2=popularity}
        """
        for _ in range(epochs):
            for sample in feedback_samples:
                user   = sample["user"]
                target = sample["clicked_signal"]
                f      = self._user_features(user)
                logits = self.W @ f + self.b
                exp_l  = np.exp(logits - logits.max())
                probs  = exp_l / exp_l.sum()
                # Cross-entropy gradient
                grad   = probs.copy()
                grad[target] -= 1.0
                self.W -= lr * np.outer(grad, f)
                self.b -= lr * grad
        self._trained = True
        self.save()


_fusion_attention = SignalFusionAttention()


class ImprovedRecommendationEngine:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def build_embeddings(self):
        papers = Paper.objects.filter(is_approved=True)
        docs = [f"{p.title} {p.summary or ''} {p.abstract or ''}" for p in papers]
        embeddings = self.model.encode(docs, convert_to_numpy=True)
        for paper, emb in zip(papers, embeddings):
            PaperEmbedding.objects.update_or_create(
                paper=paper,
                defaults={'embedding': emb.tolist(), 'model_version': 'bert-mini-v1'}
            )

    def get_user_profile_vector(self, user):
        paper_ids = list(
            Rating.objects.filter(user=user, rating__gte=4).values_list('paper_id', flat=True)
        ) + list(
            Bookmark.objects.filter(user=user).values_list('paper_id', flat=True)
        )
        embeddings = PaperEmbedding.objects.filter(paper_id__in=paper_ids)
        if not embeddings.exists():
            return None
        arr = np.array([np.array(e.embedding) for e in embeddings])
        return arr.mean(axis=0)

    def content_based_recommend(self, user, top_k=10):
        user_vec = self.get_user_profile_vector(user)
        if user_vec is None:
            popular = Paper.objects.filter(is_approved=True).order_by('-view_count')[:top_k]
            return [(paper, paper.view_count) for paper in popular]

        paper_embeds = PaperEmbedding.objects.filter(
            paper__is_approved=True
        ).select_related('paper')
        vectors = np.array([pe.embedding for pe in paper_embeds])
        similarities = cosine_similarity([user_vec], vectors)[0]
        exclude_ids = set(
            Rating.objects.filter(user=user).values_list('paper_id', flat=True)
        ) | set(
            Bookmark.objects.filter(user=user).values_list('paper_id', flat=True)
        )
        scored = [
            (pe.paper, sim) for pe, sim in zip(paper_embeds, similarities)
            if pe.paper.id not in exclude_ids
        ]
        scored.sort(key=lambda tup: tup[1], reverse=True)
        return scored[:top_k]

    def collaborative_filter(self, user, top_k=10):
        my_rated = list(
            Rating.objects.filter(user=user, rating__gte=4).values_list('paper_id', flat=True)
        )
        if not my_rated:
            return []
        similar_users = Rating.objects.filter(
            paper_id__in=my_rated, rating__gte=4
        ).exclude(user=user).values_list('user', flat=True).distinct()
        recs = Rating.objects.filter(
            user_id__in=similar_users, rating__gte=4
        ).exclude(paper_id__in=my_rated).values('paper_id').annotate(score=Count('id'))
        rec_rows = list(recs.order_by('-score')[:top_k])
        papers_map = Paper.objects.in_bulk([row['paper_id'] for row in rec_rows])
        result = [
            (papers_map[row['paper_id']], row['score'])
            for row in rec_rows
            if row['paper_id'] in papers_map
        ]
        return result

    def normalize_scores(self, scores):
        if not scores:
            return scores
        min_s = min(scores.values())
        max_s = max(scores.values())
        denom = max_s - min_s if max_s != min_s else 1e-8
        return {k: (v - min_s) / denom for k, v in scores.items()}

    def hybrid_recommend(self, user, top_k=10, alpha=None, beta=None, gamma=None):
        # Use learned attention weights unless caller supplies explicit overrides
        if alpha is None or beta is None or gamma is None:
            alpha, beta, gamma = _fusion_attention.get_weights(user)
            logger.debug(
                "SignalFusion weights for user %s: α=%.3f β=%.3f γ=%.3f",
                user.id, alpha, beta, gamma,
            )

        has_profile = self.get_user_profile_vector(user) is not None

        # Cold-start path: no personal history → try Group-Guided Cold-Start
        if not has_profile:
            group_recs = self.group_cold_start_recommend(user, top_k=top_k)
            if group_recs:
                logger.info(
                    "GG-CSR activated for cold-start user %s — returning %d group recs.",
                    user.id, len(group_recs),
                )
                return group_recs
            # No group activity either → fall through to global popularity below
            logger.info(
                "GG-CSR: no group signal for user %s — falling back to global popularity.",
                user.id,
            )

        content = self.content_based_recommend(user, top_k * 2)
        collaborative = self.collaborative_filter(user, top_k * 2)

        content_ids = {paper.id for paper, _ in content}
        collab_ids = {paper.id for paper, _ in collaborative}

        popularity = {}
        for paper, _ in content:
            score = ((paper.citation_count or 0) * 0.7 if hasattr(paper, 'citation_count') else 0) + \
                    ((paper.download_count or 0) * 0.3 if hasattr(paper, 'download_count') else 0)
            popularity[paper.id] = score

        scores = {}
        for paper, score in content:
            scores[paper.id] = scores.get(paper.id, 0) + alpha * score
        for paper, score in collaborative:
            scores[paper.id] = scores.get(paper.id, 0) + beta * score
        for pid, pop_score in popularity.items():
            scores[pid] = scores.get(pid, 0) + gamma * pop_score

        scores = self.normalize_scores(scores)
        papers = Paper.objects.in_bulk(scores.keys())
        ranked_raw = sorted(
            ((papers[pid], score) for pid, score in scores.items()),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        # Attach a human-readable reason per paper
        result = []
        for paper, score in ranked_raw:
            in_content = paper.id in content_ids
            in_collab = paper.id in collab_ids
            if not has_profile:
                reason = "Trending paper in the research community"
            elif in_content and in_collab:
                reason = "Matches your interests and is popular among researchers like you"
            elif in_content:
                reason = "Similar to papers you have rated or bookmarked"
            elif in_collab:
                reason = "Highly rated by researchers with similar interests"
            else:
                reason = "Trending in your research area"
            result.append((paper, score, reason))
        return result

    # ------------------------------------------------------------------
    # Group-Guided Cold-Start Resolution (GG-CSR)
    # ------------------------------------------------------------------

    def group_cold_start_recommend(self, user, top_k: int = 10):
        """
        GG-CSR: Build a group-centroid profile for a cold-start user.

        Algorithm
        ---------
        1. Collect papers from every research group the user belongs to:
             a. Papers explicitly shared into the group (GroupPaper)
             b. Papers rated ≥4 by other group members
             c. Papers bookmarked by other group members
        2. Average their embeddings → group centroid vector.
        3. Rank all approved platform papers by cosine similarity to the centroid.
        4. Return top_k as (paper, score, reason) triples.

        Returns [] if the user has no group memberships or the groups have
        no paper activity yet (caller falls back to global popularity).
        """
        from apps.groups.models import GroupMember, GroupPaper

        # --- 1. Group memberships ----------------------------------------
        memberships = list(
            GroupMember.objects.filter(user=user).select_related("group")
        )
        if not memberships:
            logger.info("GG-CSR: user %s has no group memberships — skipping.", user.id)
            return []

        group_ids = [m.group_id for m in memberships]
        group_names = {m.group_id: m.group.name for m in memberships}

        # --- 2. Collect group paper IDs -----------------------------------
        # a) Explicitly shared papers
        explicit_ids = set(
            GroupPaper.objects.filter(group_id__in=group_ids)
            .values_list("paper_id", flat=True)
        )

        # b) Papers rated ≥4 by other group members
        peer_user_ids = list(
            GroupMember.objects.filter(group_id__in=group_ids)
            .exclude(user=user)
            .values_list("user_id", flat=True)
            .distinct()
        )
        rated_ids = set(
            Rating.objects.filter(user_id__in=peer_user_ids, rating__gte=4)
            .values_list("paper_id", flat=True)
        )

        # c) Papers bookmarked by other group members
        bookmarked_ids = set(
            Bookmark.objects.filter(user_id__in=peer_user_ids)
            .values_list("paper_id", flat=True)
        )

        group_paper_ids = explicit_ids | rated_ids | bookmarked_ids

        if not group_paper_ids:
            logger.info(
                "GG-CSR: user %s groups have no paper activity — skipping.", user.id
            )
            return []

        # --- 3. Build group centroid from embeddings ----------------------
        group_embeds = list(
            PaperEmbedding.objects.filter(paper_id__in=group_paper_ids)
        )
        if not group_embeds:
            return []

        group_matrix = np.array([np.array(e.embedding) for e in group_embeds])
        group_centroid = group_matrix.mean(axis=0)

        # --- 4. Score all approved papers against centroid ----------------
        all_embeds = list(
            PaperEmbedding.objects.select_related("paper").filter(
                paper__is_approved=True
            )
        )
        if not all_embeds:
            return []

        vectors = np.array([np.array(pe.embedding) for pe in all_embeds])
        similarities = cosine_similarity([group_centroid], vectors)[0]

        # Exclude papers the user has already interacted with
        user_seen = set(
            Rating.objects.filter(user=user).values_list("paper_id", flat=True)
        ) | set(
            Bookmark.objects.filter(user=user).values_list("paper_id", flat=True)
        )

        scored = [
            (pe.paper, float(sim))
            for pe, sim in zip(all_embeds, similarities)
            if pe.paper_id not in user_seen
        ]
        scored.sort(key=lambda t: t[1], reverse=True)

        # Pick the group with the most shared papers for the reason string
        primary_name = "your research group"
        if explicit_ids:
            from django.db.models import Count as _Count
            top = (
                GroupPaper.objects.filter(group_id__in=group_ids)
                .values("group_id")
                .annotate(n=_Count("id"))
                .order_by("-n")
                .first()
            )
            if top:
                primary_name = f"'{group_names[top['group_id']]}'"

        reason = f"Recommended based on {primary_name} group's research focus"
        return [(paper, score, reason) for paper, score in scored[:top_k]]

    def save_recommendations(self, user, ranked_papers):
        UserRecommendation.objects.filter(user=user).delete()
        for item in ranked_papers:
            paper, score = item[0], item[1]
            reason = item[2] if len(item) == 3 else "Recommended based on your research activity"
            UserRecommendation.objects.create(
                user=user,
                paper=paper,
                score=score,
                reason=reason,
            )

    def generate_for_user(self, user, top_k=10, rebuild_embeddings=False):
        if rebuild_embeddings:
            self.build_embeddings()
        ranked = self.hybrid_recommend(user, top_k=top_k)
        self.save_recommendations(user, ranked)
        return ranked
