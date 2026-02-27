from rest_framework import serializers
from .models import Paper, Category, Bookmark, Rating, Citation

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']

class PaperSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)
    uploaded_by = serializers.StringRelatedField(read_only=True)
    average_rating = serializers.ReadOnlyField()
    citation_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Paper
        fields = [
            'id', 'title', 'abstract', 'authors', 'publication_date', 
            'doi', 'pdf_path', 'uploaded_by', 'categories', 'created_at',
            'view_count', 'download_count', 'average_rating', 'citation_count'
        ]

class BookmarkSerializer(serializers.ModelSerializer):
    paper = PaperSerializer(read_only=True)
    
    class Meta:
        model = Bookmark
        fields = ['id', 'paper', 'folder', 'created_at']

class RatingSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    paper = PaperSerializer(read_only=True)
    
    class Meta:
        model = Rating
        fields = ['id', 'user', 'paper', 'rating', 'review_text', 'created_at']
