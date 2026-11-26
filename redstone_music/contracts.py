"""Versioned public contracts; validating never fetches remote schemas."""
import json
import re


def validate_contract(document, name):
    if not re.fullmatch(r'[a-z][a-z0-9-]*', name):
        raise ValueError('Invalid contract name')
    from jsonschema import Draft202012Validator
    from .kit import resource_root
    schema = json.loads((resource_root() / 'schemas' / f'{name}.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    json.dumps(document, allow_nan=False)
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda e: str(list(e.path)))
    if errors:
        raise ValueError('Invalid ' + name + ': ' + '; '.join(f'{"/".join(map(str,e.path))}: {e.message}' for e in errors[:6]))
    return {'valid': True, 'schema': name, 'schemaVersion': document.get('schemaVersion')}
