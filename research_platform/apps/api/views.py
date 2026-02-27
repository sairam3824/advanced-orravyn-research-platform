from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import get_user_model

User = get_user_model()


class UserRegistrationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from apps.accounts.forms import UserRegistrationForm
        from apps.accounts.models import UserProfile

        form = UserRegistrationForm(request.data)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.get_or_create(user=user)
            return Response(
                {'message': 'User registered successfully.', 'username': user.username},
                status=status.HTTP_201_CREATED,
            )
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        data = {
            'username': request.user.username,
            'email': request.user.email,
            'user_type': request.user.user_type,
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'institution': profile.institution,
            'research_interests': profile.research_interests,
        }
        return Response(data)


from rest_framework.decorators import api_view

@api_view(['GET'])
def login_api_view(request):
    """Placeholder — authentication is handled via /api/auth/token/ (JWT)."""
    return Response(
        {'detail': 'Use POST /api/auth/token/ with username and password to obtain JWT tokens.'},
        status=status.HTTP_200_OK,
    )
