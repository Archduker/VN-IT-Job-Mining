"""Background full raw scans. Aggregates only; never retain whole payloads."""

import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock

from app.core.r2_client import r2_client

_pool = ThreadPoolExecutor(max_workers=2)
_lock = Lock()
_jobs = {}


def _run(source):
    from app.services.eda_r2_service import _read

    fields = {}
    payload_counts = Counter()
    id_counts = Counter()
    records = objects = 0
    try:
        client = r2_client.get_client()
        if client is None:
            raise ValueError('R2_NOT_CONFIGURED')
        for page in client.get_paginator('list_objects_v2').paginate(
            Bucket=r2_client.bucket_name, Prefix=f'raw/{source}/'
        ):
            for obj in page.get('Contents', []):
                if not obj['Key'].endswith('.json'):
                    continue
                content = json.loads(_read(client, obj['Key']))
                name = obj['Key'].rsplit('/', 1)[-1][:-5]
                id_counts[re.sub(r'_v\d+$', '', name)] += 1
                for item in content if isinstance(content, list) else [content]:
                    if not isinstance(item, dict):
                        raise ValueError('INVALID_RAW')
                    payload = item.get('raw_payload', item.get('raw', item))
                    if not isinstance(payload, dict):
                        raise ValueError('INVALID_RAW')
                    records += 1
                    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
                    payload_counts[hashlib.sha256(canonical.encode()).digest()] += 1
                    for key, value in payload.items():
                        field = fields.setdefault(key, {'present': 0, 'unique': set(), 'types': set(), 'sample': None})
                        if value is None or value == '':
                            continue
                        field['present'] += 1
                        field['types'].add(type(value).__name__)
                        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
                        field['unique'].add(hashlib.sha256(encoded.encode()).digest())
                        if field['sample'] is None:
                            field['sample'] = str(value)[:60]
                objects += 1
                with _lock:
                    _jobs[source].update(status='RUNNING', records=records, objects=objects)
        inventory = sorted([{'field_name': key, 'data_type': '/'.join(sorted(f['types'])) or 'null',
                             'null_count': records - f['present'],
                             'null_rate_pct': round(100 * (records - f['present']) / records, 2),
                             'unique_count': len(f['unique']), 'sample_value': f['sample']}
                            for key, f in fields.items()], key=lambda f: f['null_rate_pct'])
        with _lock:
            _jobs[source].update(status='COMPLETE', inventory=inventory, records=records, objects=objects,
                                 duplicates={'records': records, 'unique_payloads': len(payload_counts),
                                             'duplicate_records': records - len(payload_counts),
                                             'duplicate_groups': sum(n > 1 for n in payload_counts.values()),
                                             'duplicate_pct': round(100 * (records - len(payload_counts)) / records, 2) if records else None,
                                             'filename_ids': len(id_counts),
                                             'extra_version_objects': objects - len(id_counts)},
                                 completed_at=datetime.now(UTC).isoformat())
    except Exception:
        with _lock:
            _jobs[source].update(status='ERROR', reason='R2_SCAN_FAILED', inventory=[])


def scan(source, refresh=False):
    with _lock:
        job = _jobs.get(source)
        legacy_result = job is not None and job.get('status') == 'COMPLETE' and not isinstance(job.get('duplicates'), dict)
        if job is None or legacy_result or (refresh and job['status'] not in ('QUEUED', 'RUNNING')):
            _jobs[source] = {'status': 'QUEUED', 'records': 0, 'objects': 0, 'inventory': [],
                             'duplicates': None,
                             'reason': None, 'completed_at': None, 'scope': 'ALL_RAW_VERSIONS'}
            _pool.submit(_run, source)
        return dict(_jobs[source])
