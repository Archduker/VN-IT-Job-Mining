import pandas as pd
from app.services.pipeline_report_service import pipeline_report_service


def test_histogram_includes_all_numeric_rows_even_zero_negative_and_high_outliers():
    frame = pd.DataFrame({'salary_min_vnd': [-1e6, 0, 10e6, 2e9, None, float('inf')],
                          'salary_max_vnd': [-1e6, 0, 20e6, 4e9, None, float('inf')]})
    charts = pipeline_report_service.eda_charts_from_frame(frame, 'test')
    assert charts['records'] == 6
    assert charts['salary_records'] == 4
    assert sum(b['count'] for b in charts['salary_histogram']) == 4
    assert charts['salary_histogram'][-1]['count'] == 1


def test_histogram_handles_absent_salary_columns():
    charts = pipeline_report_service.eda_charts_from_frame(pd.DataFrame({'job': ['A']}), 'test')
    assert charts['salary_records'] == 0
    assert charts['salary_histogram'] == []
