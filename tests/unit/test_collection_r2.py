"""R2 inventory distinguishes versions, unknown dates and absent ledgers."""

import json
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from app.services import collection_r2_service as service
from botocore.exceptions import ClientError


def test_inventory_counts_versions_without_claiming_unique_jobs():
    client = Mock()
    client.get_paginator.return_value.paginate.return_value = [{'Contents': [
        {'Key': 'raw/topcv/2026-11-10/1_v1.json', 'Size': 10},
        {'Key': 'raw/topcv/2026-11-10/1_v2.json', 'Size': 20,
         'LastModified': datetime(2026, 11, 10, tzinfo=UTC)},
        {'Key': 'raw/topcv/unknown/2.json', 'Size': 5},
        {'Key': 'raw/topcv/note.txt', 'Size': 100},
    ]}]
    payload = {'records': {'a': {'status': 'DONE'}, 'b': {'status': 'FAILED'}}}
    with patch.object(service.r2_client, 'get_client', return_value=client), patch.object(
        service, '_read', return_value=json.dumps(payload).encode()
    ):
        row = service._source('topcv')
    assert row['raw_objects'] == 3
    assert row['bytes'] == 35
    assert row['undated_objects'] == 1
    assert sum(row['_counts'].values()) == 2
    assert row['ledger'] == {'DONE': 1, 'FAILED': 1}


def test_missing_ledger_is_unknown_not_zero_statuses():
    client = Mock()
    client.get_paginator.return_value.paginate.return_value = []
    missing = ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
    with patch.object(service.r2_client, 'get_client', return_value=client), patch.object(
        service, '_read', side_effect=missing
    ):
        row = service._source('topcv')
    assert row['ledger'] is None
    assert row['ledger_reason'] == 'NO_LEDGER'
