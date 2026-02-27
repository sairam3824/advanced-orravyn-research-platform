from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .recommendation_engine import RecommendationEngine
from .models import UserRecommendation

@login_required
def generate_recommendations_for_user(request):
    engine = RecommendationEngine()
    recs = engine.generate_for_user(request.user, top_k=10)
    return render(request, "recommend/recommendations.html", {"recommendations": recs})

@login_required
def user_recommendations(request):
    recs = UserRecommendation.objects.filter(user=request.user).select_related('paper').order_by('-score')[:10]
    return render(request, "recommend/recommendations.html", {"recommendations": recs})
