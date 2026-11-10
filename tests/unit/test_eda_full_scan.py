import json
from unittest.mock import Mock, patch

from app.services import eda_raw_scan_service as service


def test_full_scan_goes_beyond_200_and_counts_absent_fields():
    client = Mock()
    client.get_paginator.return_value.paginate.return_value = [
        {'Contents': [{'Key': 'raw/test/a.json'}]},
        {'Contents': [{'Key': 'raw/test/b.json'}]},
    ]
    service._jobs['test'] = {}
    contents = [json.dumps([{'raw_payload': {'a': 1}}] * 205).encode(),
                json.dumps({'raw_payload': {'b': 'late'}}).encode()]
    with patch.object(service.r2_client, 'get_client', return_value=client), patch(
        'app.services.eda_r2_service._read', side_effect=contents
    ):
        service._run('test')
    job = service._jobs.pop('test')
    assert job['status'] == 'COMPLETE'
    assert job['records'] == 206
    assert job['objects'] == 2
    fields = {r['field_name']: r for r in job['inventory']}
    assert fields['a']['null_count'] == 1
    assert fields['b']['null_count'] == 205
    assert fields['a']['unique_count'] == 1
    assert job['duplicates']['unique_payloads'] == 2
    assert job['duplicates']['duplicate_records'] == 204
    assert job['duplicates']['duplicate_groups'] == 1


def test_failed_full_scan_does_not_publish_partial_inventory():
    client = Mock()
    client.get_paginator.return_value.paginate.return_value = [{'Contents': [{'Key': 'raw/test/a.json'}]}]
    service._jobs['test'] = {}
    with patch.object(service.r2_client, 'get_client', return_value=client), patch(
        'app.services.eda_r2_service._read', return_value=b'not json'
    ):
        service._run('test')
    job = service._jobs.pop('test')
    assert job['status'] == 'ERROR'
    assert job['inventory'] == []


def test_completed_legacy_cache_without_duplicates_is_rebuilt():
    service._jobs['legacy'] = {'status': 'COMPLETE', 'records': 2755, 'inventory': []}
    with patch.object(service._pool, 'submit') as submit:
        job = service.scan('legacy')
    assert job['status'] == 'QUEUED'
    assert job['duplicates'] is None
    submit.assert_called_once_with(service._run, 'legacy')
    service._jobs.pop('legacy')
