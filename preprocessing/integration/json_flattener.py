import os
import json
import pathlib
import pandas as pd

def run_flatten_and_integrate():
    p_in = pathlib.Path('data/preprocessing/01_clean')
    p_out = pathlib.Path('data/preprocessing/02_integration')
    p_out.mkdir(parents=True, exist_ok=True)
    all_rows = []
    
    for f in p_in.glob('*.jsonl'):
        with open(f, 'r', encoding='utf-8') as infile:
            for line in infile:
                if not line.strip():
                    continue
                item = json.loads(line)
                meta = item.get('metadata', {})
                raw = item.get('raw_payload', {})
                row = {
                    'source': meta.get('source', f.stem),
                    'job_id': meta.get('job_id', ''),
                    'source_url': meta.get('source_url', ''),
                    'title': raw.get('title', ''),
                    'company': raw.get('company', ''),
                    'salary': raw.get('salary', ''),
                    'location': raw.get('location', ''),
                    'description': raw.get('description', ''),
                    'requirements': raw.get('requirements', ''),
                    'skills': str(raw.get('skills', [])),
                    'benefits': str(raw.get('benefits', [])),
                    'it_status': meta.get('clean', {}).get('it_status', 'IT_CONFIRMED')
                }
                all_rows.append(row)
                
    df = pd.DataFrame(all_rows)
    out_file = p_out / 'all.parquet'
    df.to_parquet(out_file, index=False)
    print(f'Hoan tat: {len(df)} ban ghi vao {out_file}')

if __name__ == '__main__':
    run_flatten_and_integrate()
