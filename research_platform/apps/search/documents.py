from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from apps.papers.models import Paper

@registry.register_document
class PaperDocument(Document):
    title = fields.TextField(
        analyzer='standard',
        fields={
            'suggest': fields.CompletionField(),
        }
    )
    abstract = fields.TextField(analyzer='standard')
    authors = fields.TextField(analyzer='standard')
    categories = fields.NestedField(properties={
        'name': fields.TextField(),
    })
    uploaded_by = fields.ObjectField(properties={
        'username': fields.TextField(),
        'profile': fields.ObjectField(properties={
            'institution': fields.TextField(),
        })
    })
    
    class Index:
        name = 'papers'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }
    
    class Django:
        model = Paper
        fields = [
            'id',
            'publication_date',
            'doi',
            'created_at',
            'view_count',
            'download_count',
            'is_approved',
        ]
        
        related_models = ['categories', 'uploaded_by']
    
    def get_queryset(self):
        return super().get_queryset().filter(is_approved=True)
