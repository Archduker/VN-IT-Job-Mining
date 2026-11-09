"""Build an observed-only vocabulary proposal; never modify approved inputs."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

# Human-review proposals, not a production taxonomy. '=' introduces explicit
# same-concept spelling aliases. Only values actually found in P4 are retained.
PROPOSED_RULES = {
    'Programming Languages': '''Python
Java
JavaScript
TypeScript
C#
C++
C
Go=Golang
PHP
Ruby
Rust
Kotlin
Swift
Dart
Scala
PowerShell=Powershell
SQL
PL/SQL
VBA
ABAP
COBOL
Bash=Bash Shell''',
    'Frameworks & Libraries': '''React
Vue
Angular
Node.js
Next.js=NextJS
jQuery
HTML/CSS
Entity Framework
Spring Boot=Java Spring Boot
Django
FastAPI
Flask
Laravel
Flutter
React Native
Unity
WordPress=Wordpress
.NET=.net
TensorFlow Serving=Tensorflow Serving
Pandas
NumPy
OpenCV
Bootstrap
Tailwind CSS
Hibernate
Selenium
Cypress
Appium
JUnit
Pytest
NUnit
Jest
Robot Framework
NestJS
Express.js
ASP.NET
ASP.NET Core
WPF
Qt
Scikit-learn
Keras
Nuxt.js
Redux
Unreal Engine''',
    'Databases & Caching': '''NoSQL
Kafka=Apache Kafka
RabbitMQ
Oracle=Oracle Database
SQL Server=Microsoft SQL Server
PostgreSQL=Postgres
MySQL
MongoDB
Redis
Elasticsearch
Firebase
SQLite
MariaDB
Cassandra
DynamoDB
Neo4j
ClickHouse
InfluxDB
Microsoft Azure SQL Database
Data Warehousing=Data Warehouse|Data warehouse
Data Modeling=Data modeling
Data Management
Data Governance
Master Data Management
Data Quality
Data Integration
ETL
ELT
DBT
Apache Spark
Databricks''',
    'Cloud & DevOps': '''AWS=Amazon Web Services (AWS)
Microsoft Azure=Azure
Google Cloud=GCP
AWS Lambda
Docker
Kubernetes
Terraform
Ansible
Linux
CI/CD
DevSecOps
MLOps
Kubeflow
Prometheus
Grafana
ArgoCD
VMware=VMWare
Windows Server
Windows
Active Directory
Power Automate
Microsoft 365
Jenkins
GitLab CI
GitHub Actions
Cloud Security
Cloud Infrastructure
Cloud-native Architecture
Infrastructure as Code=Infrastructure As Code
Incident Response
Disaster Recovery
System Administration=Quản trị hệ thống|IT System Administration
Linux System Administration
Monitoring
IT Operations
IT Infrastructure''',
    'Tools, Architecture & Protocols': '''Git
REST API=RESTful API|Restful Api|Restful API|API RESTful
GraphQL
gRPC
Microservices=Microservices Architecture
OOP
Design Patterns=Design Pattern
SOLID Principles
Clean Architecture
Software Architecture=Kiến Trúc Phần Mềm
System Architecture
Enterprise Architecture
Solution Architecture
MVC
MVVM
JSON
XML
DNS
DHCP
TCP/IP
VPN
VLAN
LAN
Routing
Cisco
CCNA
CCNP
Juniper
Firewall
Network Security
Application Security
Penetration Testing=Pentest
Information Security=An Toàn Thông Tin|an toàn thông tin
Cybersecurity=An ninh mạng|An Ninh Mạng
OWASP
ISO 27001
PCI DSS
ITIL Foundation
CISSP
CEH
Figma
Adobe Photoshop=Photoshop
Adobe Illustrator=Illustrator
Adobe InDesign=Indesign|InDesign
Adobe XD
Sketch
Design Systems=Design System
UI/UX Design=UI-UX|UI/UX
Wireframing=wireframe
Typography
User Flow=user flow
Prototyping=Prototype
Postman
JMeter
API Testing=Api Testing
Automation Testing=Automation Test|Test Automation
Manual Testing
Regression Testing
Functional Testing
Software Testing=Kiểm thử phần mềm|Kiểm Thử Phần Mềm
Integration Testing=Integration test
Unit Testing=Unit Test
Test Plan
Test Case
Defect Management
A/B Testing
UAT
Debugging
Troubleshooting
Network Troubleshooting
Hardware Troubleshooting
Hardware Maintenance
RTOS
Firmware
AUTOSAR
Embedded Systems
PCB
FPGA
MATLAB
Simulink
Jira
Confluence=confluence
Power BI=Power Bi|PowerBI
Tableau
Looker Studio
Microsoft Excel=Excel
Microsoft Word
PowerPoint
Google Sheets
SAP
SAP FICO
SAP Integration Suite
Odoo
ERP
CRM
UML
BPMN
BRD
SRS
User Story=User story
Use Case
Requirements Elicitation=Thu Thập Yêu Cầu''',
    'Methodologies & Soft Skills': '''Agile/Scrum=Agile Scrum|Agile & Scrum|Agile / Scrum
Waterfall
Problem Solving=problem-solving|Problem-solving|Giải quyết vấn đề
Teamwork=Làm việc nhóm|Collaboration
Communication=Communication skills|Communication Skills|Giao tiếp|Kỹ năng giao tiếp
English=English Language|English Communication|Tiếng Anh
Japanese=Japanese Language|Tiếng Nhật
Time Management=Quản lý thời gian
Presentation Skills=Thuyết trình|kỹ năng thuyết trình
Technical Writing
Technical Documentation
Project Management=Quản Lý Dự Án|Project management
Project Planning
Stakeholder Management=Stakeholder management
Risk Management=Quản Lý Rủi Ro
Change Management
Team Management
Leadership=Lãnh đạo
Business Analysis=Phân Tích Nghiệp Vụ|Business analysis
Data Analysis=Data Analytics|Phân tích dữ liệu|Phân Tích Dữ Liệu|Data analysis
Data Visualization
Data Mining
Machine Learning
Deep Learning
Computer Vision
Natural Language Processing=NLP|Natural Language Processing (NLP)
Large Language Models=LLM
Generative AI
Prompt Engineering
Reinforcement Learning
Pattern Recognition
Neural Network
Transformer
CNN
GNN
KNN
RAG
Statistics
Algorithms=Thuật Toán
Data Structures=Cấu Trúc Dữ Liệu
Business Intelligence
Data Engineering
Process Improvement
Continuous Improvement
Analytical Skills=analytical skills
Attention to Detail=Cẩn thận
Independent Working=Làm việc độc lập
Backlog Management
Product Strategy=Product strategy
Product Roadmapping=Product roadmap''',
}


def make_proposal(rows):
    counts = Counter(v for row in rows for v in row)
    case_values = {}
    for value in counts:
        case_values.setdefault(value.casefold(), set()).add(value)
    owners, definitions = {}, []
    for group, lines in PROPOSED_RULES.items():
        for line in lines.splitlines():
            name, _, aliases = line.partition('=')
            source_names = [name, *aliases.split('|')] if aliases else [name]
            matched = set()
            for spelling in source_names:
                matched.update(case_values.get(spelling.casefold(), set()))
            if not matched:
                continue
            for value in matched:
                if value in owners:
                    raise ValueError(f'Proposed alias collision: {value}')
                owners[value] = name
            job_ids = [i for i, row in enumerate(rows) if row & matched]
            definitions.append(dict(canonical=name,aliases=' | '.join(sorted(matched)),
                                    group=group,jobs=len(job_ids),
                                    rationale='Observed skill/tool/concept; explicit same-concept naming proposal',
                                    issue=('below20; explicit threshold approval required; ' if len(job_ids)<20 else '') +
                                    ('upstream broad grouping; do not recover TensorFlow/PyTorch; ' if name=='Machine Learning' else '') +
                                    'group/alias scope proposed, not approved',
                                    status='proposed',decision=''))
    definitions.sort(key=lambda r:(-r['jobs'],r['canonical']))
    return definitions, owners


def main():
    snapshot=ROOT/'reports/preprocessing/05_encoding/snapshot_audit_2026-11-08'
    review=ROOT/'reports/preprocessing/05_encoding/review_2026-11-08'
    out=ROOT/'reports/preprocessing/05_encoding/approval_package_v1'
    out.mkdir(exist_ok=False)
    protected=[review/'candidate_decisions.csv',review/'candidate_generated.csv']
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    manifest=json.loads((snapshot/'manifest.json').read_text())
    frames=[]
    for item in manifest:
        path=snapshot/(item['key'].split('/')[1]+'.parquet')
        assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
        d=pd.read_parquet(path)
        assert len(d)==item['rows'] and set(d.source_platform)=={item['key'].split('/')[1]}
        frames.append(d)
    df=pd.concat(frames,ignore_index=True)
    assert df.job_id_global.notna().all() and df.job_id_global.is_unique
    rows=[set(map(str,s)) for s in df.skills_std]
    tensor=[]
    for i,row in enumerate(rows):
        matches=[s for s in row if 'tensorflow' in s.casefold()]
        if matches:
            tensor.append(dict(job_id_global=df.iloc[i].job_id_global,matching_values=' | '.join(matches),
                               exact_TensorFlow='TensorFlow' in row,casefold_exact='tensorflow' in {s.casefold() for s in row},
                               substring=True))
    pd.DataFrame(tensor).to_csv(out/'tensorflow_count_explanation.csv',index=False)
    definitions, owners=make_proposal(rows)
    pd.DataFrame(definitions[:230]).to_csv(out/'vocabulary_proposed.csv',index=False)
    pd.DataFrame(definitions[230:260]).to_csv(out/'vocabulary_reserves.csv',index=False)
    pd.DataFrame(definitions).to_csv(out/'all_curated_proposals.csv',index=False)
    observed=Counter(v for row in rows for v in row)
    unresolved=[dict(value=v,jobs=n,reason='Not admitted automatically; ambiguity/role/domain/no reviewed rule',status='unresolved')
                for v,n in sorted(observed.items(),key=lambda p:(-p[1],p[0])) if v not in owners]
    pd.DataFrame(unresolved).to_csv(out/'unresolved_observed_values.csv',index=False)
    proposal={'status':'proposed_not_production','version':'p5-review-rules-v1','groups':PROPOSED_RULES}
    (out/'mapping_proposed.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(jobs=len(rows),curated_observed_candidates=len(definitions),selected_proposed=min(230,len(definitions)),
                 shortfall=max(0,230-len(definitions)),reserves=min(30,max(0,len(definitions)-230)),
                 proposed_below20=sum(r['jobs']<20 for r in definitions[:230]),
                 group_counts=Counter(r['group'] for r in definitions[:230]),
                 tensor_exact=sum('TensorFlow' in row for row in rows),
                 tensor_substring=sum(any('tensorflow' in s.casefold() for s in row) for row in rows),
                 protected_sha256=hashes,
                 snapshot_manifest_sha256=hashlib.sha256((snapshot/'manifest.json').read_bytes()).hexdigest(),
                 source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 representation='frozen snapshot skills_std with explicit proposed mappings; no JD extraction',
                 production_changed=False)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    for p in protected:
        assert hashlib.sha256(p.read_bytes()).hexdigest()==hashes[p.name]
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
