"""Read-only R2 inventory and ledger snapshots, independent of Airflow/local data."""

import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Lock

from app.core.config import settings
from app.core.r2_client import r2_client
from app.services.eda_r2_service import _read
from botocore.exceptions import ClientError
from fastapi import HTTPException

_lock = Lock()
_cache = None
VN_TZ = timezone(timedelta(hours=7))


def _source(source):
    client = r2_client.get_client()
    counts = Counter()
    total = size = undated = 0
    latest = None
    for page in client.get_paginator('list_objects_v2').paginate(
        Bucket=r2_client.bucket_name, Prefix=f'raw/{source}/'
    ):
        for obj in page.get('Contents', []):
            if not obj['Key'].endswith('.json'):
                continue
            total += 1
            size += obj['Size']
            modified = obj.get('LastModified')
            if modified and (latest is None or modified > latest):
                latest = modified
            parts = obj['Key'].split('/')
            try:
                day = date.fromisoformat(parts[2])
            except (ValueError, IndexError):
                undated += 1
            else:
                counts[day] += 1
    statuses = None
    try:
        payload = json.loads(_read(client, f'url_ledger/{source}/catalog_master.json'))
        records = payload.get('records', payload) if isinstance(payload, dict) else payload
        if isinstance(records, dict):
            records = list(records.values())
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ValueError('INVALID_LEDGER')
        statuses = Counter(str(r.get('status') or 'UNKNOWN').upper() for r in records)
    except ClientError as exc:
        if str(exc.response.get('Error', {}).get('Code')) not in ('NoSuchKey', '404', 'NotFound'):
            raise
    return {'source': source, 'raw_objects': total, 'bytes': size, 'undated_objects': undated,
            'latest_upload': latest.isoformat() if latest else None,
            'ledger': dict(statuses) if statuses is not None else None,
            'ledger_reason': 'NO_LEDGER' if statuses is None else None, '_counts': counts}


def get_collection(days=14):
    global _cache
    with _lock:
        if _cache and time.monotonic() - _cache[0] < 60:
            sources = _cache[1]
        else:
            try:
                if r2_client.get_client() is None:
                    raise HTTPException(503, detail={'reason': 'R2_NOT_CONFIGURED'})
                with ThreadPoolExecutor(max_workers=4) as pool:
                    sources = list(pool.map(_source, settings.SUPPORTED_SOURCES))
                _cache = (time.monotonic(), sources)
            except HTTPException:
                raise
            except ClientError as exc:
                code = str(exc.response.get('Error', {}).get('Code'))
                reason = 'R2_ACCESS_DENIED' if code in ('AccessDenied', '403', 'InvalidAccessKeyId', 'SignatureDoesNotMatch') else 'R2_READ_FAILED'
                raise HTTPException(503, detail={'reason': reason}) from None
            except Exception:
                raise HTTPException(503, detail={'reason': 'R2_READ_FAILED'}) from None
        snapshot = _cache[0]
    today = datetime.now(VN_TZ).date()
    window = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    rows = []
    for day in window:
        by_source = {s['source']: {'count': s['_counts'].get(day, 0)}
                     for s in sources}
        rows.append({'date': day.isoformat(), 'dow': ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'][day.weekday()],
                     'is_today': day == today, 'total': sum(r['count'] for r in by_source.values()),
                     'by_source': by_source})
    return {'origin': 'r2', 'generated_at': datetime.now(VN_TZ).isoformat(),
            'cache_age_seconds': round(time.monotonic() - snapshot), 'days': rows,
            'raw_objects': sum(s['raw_objects'] for s in sources),
            'bytes': sum(s['bytes'] for s in sources),
            'undated_objects': sum(s['undated_objects'] for s in sources),
            'sources': [{k: v for k, v in s.items() if k != '_counts'} for s in sources],
            'has_data': any(s['raw_objects'] for s in sources),
            'unavailable_reason': None if any(s['raw_objects'] for s in sources) else 'NO_RAW_DATA'}
