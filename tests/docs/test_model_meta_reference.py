"""Execute the metadata guide and its supported introspection contracts."""

import re
from pathlib import Path

from aksara.registry import ModelRegistry


def test_metadata_guide_example():
    source = (Path(__file__).resolve().parents[2] / 'docs/docs/orm/model-meta.md').read_text()
    code = re.search(r'```python title="inspect_models.py"\n(.*?)```', source, re.DOTALL)[1]
    saved = ModelRegistry.snapshot()
    namespace = {'__name__': 'documents.models'}
    try:
        exec(compile(code, 'inspect_models.py', 'exec'), namespace)  # noqa: S102
        result = namespace['describe_document']()
        assert result['name'] == 'MetadataDocument'
        assert result['table'] == 'metadata_documents'
        assert result['app'] == 'documents'
        assert result['primary_key'] == 'id'
        assert result['title_limit'] == 200
        assert result['owner_is_foreign_key'] is True
        assert {'id', 'title', 'owner'} <= set(result['field_names'])
        model = namespace['MetadataDocument']
        assert not hasattr(model, '_meta')
        meta = model.meta
        assert meta.has_field('title') and not meta.has_field('missing')
        assert meta.get_field('missing') is None
        assert meta.pk is meta.get_field('id')
        assert meta.foreign_keys == meta.relations
        assert meta.many_to_many == {}
        assert meta.fields is not meta.fields
        assert meta.foreign_keys is not meta.foreign_keys
        assert meta.relations is meta.relations
        snapshot = meta.to_dict()
        assert snapshot['name'] == meta.name
        assert snapshot['relations']['owner']['related_model'] == 'MetadataOwner'
        assert namespace['MetadataOwner'].meta.app_label == 'documents'
    finally:
        ModelRegistry.clear()
        for model in saved.values():
            ModelRegistry.register(model)
