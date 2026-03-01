import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, UserProfile

class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    institution = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    research_interests = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    user_type = forms.ChoiceField(choices=User.USER_TYPES, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'user_type', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_type'].choices = [c for c in User.USER_TYPES if c[0] in ('publisher', 'reader')]
        # Add form-control class to password fields
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

    def clean_username(self):
        username = self.cleaned_data.get('username', '')
        if not re.fullmatch(r'[A-Za-z0-9]+', username):
            raise forms.ValidationError(
                'Username may only contain letters and numbers — no spaces or special characters.'
            )
        if not re.search(r'\d', username):
            raise forms.ValidationError('Username must include at least one number.')
        return username


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'first_name', 'last_name', 'institution', 'research_interests', 
            'bio', 'avatar', 'orcid', 'h_index', 'website', 
            'google_scholar', 'research_gate', 'credentials_document'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'institution': forms.TextInput(attrs={'class': 'form-control'}),
            'research_interests': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'orcid': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0000-0002-1825-0097'}),
            'h_index': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
            'google_scholar': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://scholar.google.com/'}),
            'research_gate': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.researchgate.net/'}),
            'credentials_document': forms.FileInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'orcid': 'Your ORCID identifier (e.g., 0000-0002-1825-0097)',
            'h_index': 'Your current H-index score',
            'credentials_document': 'Upload academic credentials for verification (PDF, max 5MB)',
        }



class SavedSearchForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Machine Learning Papers 2024'
        })
    )
