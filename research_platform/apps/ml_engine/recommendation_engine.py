import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from django.db.models import Count
from apps.papers.models import Paper, Rating, Bookmark
from apps.ml_engine.models import PaperEmbedding, UserRecommendation
from apps.accounts.models import User


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

        paper_embeds = PaperEmbedding.objects.select_related('paper')
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

    def hybrid_recommend(self, user, top_k=10, alpha=0.6, beta=0.3, gamma=0.1):
        has_profile = self.get_user_profile_vector(user) is not None
        content = self.content_based_recommend(user, top_k * 2)
        collaborative = self.collaborative_filter(user, top_k * 2)

        content_ids = {paper.id for paper, _ in content}
        collab_ids = {paper.id for paper, _ in collaborative}

        popularity = {}
        for paper, _ in content:
            score = (paper.citation_count * 0.7 if hasattr(paper, 'citation_count') else 0) + \
                    (paper.download_count * 0.3 if hasattr(paper, 'download_count') else 0)
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
