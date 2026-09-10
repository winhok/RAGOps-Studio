"""Create local credentials and optionally ingest the explicit reference corpus."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
ACCOUNTS = [('agentic-admin', '蓝鲸 · 知识管理员', 'bluewhale', 'platform', 'admin'), ('kb-admin', '蓝鲸企业 · 管理员', 'bluewhale-kb', 'platform', 'admin'), ('kb-support', '蓝鲸企业 · 客服', 'bluewhale-kb', 'customer-service', 'employee'), ('kb-finance', '蓝鲸企业 · 财务', 'bluewhale-kb', 'finance', 'employee'), ('starlight-admin', '星河 · 管理员', 'starlight', 'platform', 'admin')]

def create_credentials(path: Path):
    if path.exists():
        print(f'Existing identity registry preserved: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 448)
    registry = []
    lines = ['RAGOps local access credentials — keep private; do not commit or record these on video.', '']
    for uid, name, tenant, dept, role in ACCOUNTS:
        token = secrets.token_urlsafe(32)
        principal = dict(user_id=uid, name=name, tenant_id=tenant, department_id=dept, role=role)
        registry.append(dict(token_sha256=hashlib.sha256(token.encode()).hexdigest(), principal=principal))
        lines.extend([f'{uid} | tenant={tenant} | department={dept} | role={role}', token, ''])
    # The runtime reads only SHA-256 digests. The plaintext copy is local operator material.
    with path.open('x', encoding='utf-8') as f:
        os.chmod(path, 384)
        json.dump(registry, f, ensure_ascii=False, indent=2)
    credentials = path.parent / 'access-credentials.txt'
    with credentials.open('x', encoding='utf-8') as f:
        os.chmod(credentials, 384)
        f.write('\n'.join(lines))
    print(f'Credentials generated: {credentials}')

def seed(runtime, root: Path=ROOT) -> int:
    from app.api.schemas import SaveDocumentRequest
    from app.core.models import Principal
    from app.core.errors import NotFound
    count = 0
    for row in json.loads((root / 'data/corpus.json').read_text(encoding='utf-8')):
        principal = Principal(user_id='corpus-loader', name='Corpus loader', tenant_id=row['tenant_id'], department_id='platform', role='admin')
        try:
            runtime.store.versions(principal, row['id'])
            # Never overwrite an edited or intentionally deleted source on a second bootstrap.
            continue
        except NotFound:
            pass
        data = SaveDocumentRequest(title=row['title'], content=(root / row['file']).read_text(encoding='utf-8'), department_id=row['department_id'], visibility=row['visibility'], evidence_type=row['evidence_type'], effective_at=row['effective_at'], additional_evidence_types=row.get('additional_evidence_types', []), expected_version=0)
        result = runtime.store.publish(principal, data, runtime.embeddings, runtime.index, row['id'])
        if not row.get('active', True):
            runtime.store.delete(principal, row['id'], result['document']['version'])
        count += 1
    return count

def main():
    from app.core.config import Settings
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-sample-data', action='store_true', help='Ingest the supplied synthetic reference corpus')
    args = parser.parse_args()
    settings = Settings.from_env(ROOT)
    create_credentials(settings.principals_file)
    if args.with_sample_data:
        from app.services.runtime import Runtime
        runtime = Runtime(settings)
        try:
            print(f'Published {seed(runtime)} new source documents. Existing sources were not changed.')
        finally:
            runtime.close()
    print('Start the service with: python scripts/serve.py')
if __name__ == '__main__':
    main()
