from django.apps import AppConfig

class UatsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'uats'
    
    def ready(self):
        import uats.signals