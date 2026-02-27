from django.apps import AppConfig


class PapersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.papers'

class PapersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.papers'

    def ready(self):
        import apps.papers.signals
