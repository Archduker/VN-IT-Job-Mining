"""Explicit agent-review proposals, not approved labels or automatic JD extraction.

Each line is an individually authored entity interpretation/reason. Only snapshot
skills_std whole values establish membership; JD excerpts are review evidence only.
"""

# canonical | entity_type | specific reason
NOTES = """SQL|technology|Query language, not a database vendor or job title.
REST API|method_practice|HTTP API design/integration style; no inference of every web skill.
Python|technology|Programming in the Python language.
Machine Learning|technical_knowledge|Broad learning knowledge; upstream grouped frameworks cannot be recovered.
Agile/Scrum|composite|Keep source composite; neither AND semantics nor separate Agile/Scrum bits.
Git|tool|Distributed version-control tool.
CI/CD|method_practice|Continuous integration/delivery practice, not a DevOps job title.
Docker|tool|Container build/runtime tooling.
Java|technology|Java programming language, independent from Spring.
AWS|technology|Explicit cloud platform; no inference of AWS products from the platform bit.
NoSQL|technical_knowledge|Broad non-relational data-system knowledge, not a specific engine.
Linux|technology|Operating-system knowledge; not inferred from Docker.
JavaScript|technology|JavaScript language; no framework parent/child propagation.
Kubernetes|tool|Container orchestration platform.
Microservices|method_practice|Distributed service architecture practice; alias architecture wording is explicit.
Microsoft Azure|technology|Named cloud platform; canonical itself must be a lookup key.
C#|technology|C-sharp language; punctuation distinguishes C and C++.
React|technology|UI library, not every JavaScript skill.
Google Cloud|technology|Named cloud platform; GCP is an explicit platform abbreviation.
Data Engineering|ambiguous|Metadata can name a team/career domain; do not assert competence for all tagged jobs.
Node.js|technology|JavaScript runtime, documented exception to the framework/library task bucket.
English|technical_knowledge|Learned language proficiency, distinct from behavioral communication skill.
HTML/CSS|composite|Preserve combined source value; not proof both languages are independently required.
Kafka|tool|Event streaming/broker technology; not a database/cache engine.
TypeScript|technology|Typed programming language distinct from JavaScript.
Unit Testing|method_practice|Unit-level testing practice; canonical works without repeated alias.
C++|technology|C++ language; not canonicalized to C by punctuation removal.
Kotlin|technology|Kotlin programming language, not inferred from Android roles.
C|technology|C language from explicit metadata; no one-letter JD scan.
Automation Testing|method_practice|Automated testing practice; Test Automation/Automation Test need explicit alias review.
Swift|technology|Swift programming language.
Business Analysis|method_practice|Business-requirements analysis activity, not Business Analyst title.
Communication|soft_skill|Interpersonal communication behavior; source language-proficiency bits stay separate.
Data Analysis|method_practice|Data analysis activity; Data Analytics is an explicit conceptual alias proposal.
PHP|technology|PHP programming language.
Cybersecurity|technical_knowledge|Security discipline; no certification-to-competence inference.
Angular|technology|Angular web framework.
RabbitMQ|tool|Message broker; relocate out of database/cache bucket.
Vue|technology|Vue UI framework.
Project Management|method_practice|Project delivery practice; not a project-manager role label.
Go|technology|Go programming language; Golang is explicit alias, not English verb matching.
Teamwork|soft_skill|Team cooperation; Collaboration will be represented separately, not generalized into this owner.
Dart|technology|Dart programming language distinct from Flutter framework.
Adobe Illustrator|tool|Vector-design application relevant to observed IT design jobs; vendor prefix alone is not the evidence.
GraphQL|technology|API query technology, distinct from REST.
Power BI|tool|Analytics/reporting product; does not imply generic BI competence automatically.
Adobe Photoshop|tool|Raster-image editing tool in observed design skill metadata.
Problem Solving|soft_skill|Behavioral problem-solving capability.
UI/UX Design|method_practice|Interface/experience design practice within IT jobs; preserve combined UI/UX scope.
Large Language Models|technical_knowledge|Model-family knowledge as job demand; does not authorize running a model in preprocessing.
Team Management|soft_skill|Managing people and team behavior, not a manager job title.
Leadership|soft_skill|People leadership capability independent of seniority.
ERP|ambiguous|System category or deployment competence varies by job; keep unresolved rather than assert implementation skill.
Figma|tool|Interface design/prototyping product.
Software Testing|method_practice|Software validation activity, distinct from Tester role labels.
Information Security|technical_knowledge|Protection-of-information knowledge broader than a particular security product.
Natural Language Processing|technical_knowledge|Language-processing knowledge; NLP alias does not imply specific libraries.
Ruby|technology|Ruby programming language.
Software Architecture|method_practice|Software structure/design discipline, not architect job title.
Computer Vision|technical_knowledge|Visual-computing knowledge area; no implicit OpenCV bit.
Microsoft Excel|tool|Spreadsheet application, not generic Office inferred from a child product.
SQL Server|technology|Named database product; canonical name is recognized independently of Microsoft prefix alias.
Japanese|technical_knowledge|Japanese language proficiency; not a behavioral soft-skill label.
Stakeholder Management|soft_skill|Working with stakeholder relationships; no job-title inference.
System Administration|method_practice|System administration activity; excludes System Administrator role strings.
Data Modeling|method_practice|Designing data models, not database-vendor knowledge.
SAP|vendor|Bare ecosystem/vendor lacks a specific product capability; ABAP/FICO remain separate if explicit.
Next.js|technology|React-based application framework; no React parent propagation.
Adobe InDesign|tool|Document-layout application observed in design-related IT postings.
Risk Management|method_practice|Risk identification/mitigation practice; not proof of a certification.
Terraform|tool|Infrastructure provisioning tool.
OOP|method_practice|Object-oriented programming paradigm.
Penetration Testing|method_practice|Offensive security assessment practice; Pentest is explicit terminology alias.
Data Warehousing|technical_knowledge|Warehouse-system concepts; a warehouse is not automatically a database product.
Design Systems|method_practice|Reusable interface-component system design practice.
Cloud Security|technical_knowledge|Cloud security knowledge, not an inferred parent of security tools.
Network Security|technical_knowledge|Network protection knowledge independent from vendor names.
System Architecture|method_practice|System-level architecture design practice.
Manual Testing|method_practice|Human-executed testing activity, distinct from Manual Tester role.
Presentation Skills|soft_skill|Communicating ideas through presentations.
Regression Testing|method_practice|Testing for regressions after changes.
Solution Architecture|method_practice|Solution architecture practice; not Solution Architect title.
Tableau|tool|Data visualization product.
VMware|technology|Explicit virtualization technology ecosystem; retained proposal is not certification evidence.
Business Intelligence|technical_knowledge|Analytics/reporting knowledge supported by BI work excerpts; not renamed from a job title.
Firewall|technology|Network filtering technology class rather than a vendor.
Rust|technology|Rust programming language.
Time Management|soft_skill|Managing personal time; explicit Vietnamese translation is a semantic alias proposal.
Unity|tool|Game/application engine; valid IT tool, not inferred from Game domain tags.
Defect Management|method_practice|Defect tracking and resolution practice.
MLOps|method_practice|Operationalizing ML systems, not an ML engineer title.
Postman|tool|API development/testing client.
API Testing|method_practice|Testing API interfaces, distinct from a particular API client.
Generative AI|technical_knowledge|Generative-model knowledge; no LLM invocation permission.
Troubleshooting|method_practice|Diagnosing technical faults, not a support role.
jQuery|technology|JavaScript DOM library.
CRM|ambiguous|Software category, business process or integration task may be intended; do not choose a skill meaning globally.
DevSecOps|method_practice|Integrating security into development/operations practice.
Test Plan|document|Observed planning actions exist, but this label names a document; do not rename globally to test planning.
Typography|technical_knowledge|Type/layout design knowledge relevant to IT interface/design work.
Data Mining|method_practice|Knowledge-discovery methods, not merely an industry domain.
Integration Testing|method_practice|Testing interactions between components.
AUTOSAR|technology|Automotive software architecture standard used in embedded engineering.
Analytical Skills|soft_skill|Analytical reasoning behavior, distinct from specific statistics techniques.
Ansible|tool|Configuration-management automation tool.
Data Management|method_practice|Managing data assets rather than a storage engine.
User Story|document|A requirements artifact; authoring competence cannot be asserted solely from the whole-value label.
Windows Server|technology|Server operating-system product.
IT Infrastructure|technical_knowledge|Broad infrastructure knowledge; not a title or named vendor.
Independent Working|soft_skill|Ability to work independently, not job employment type.
PowerShell|technology|Shell/scripting language with meaningful product spelling.
RAG|method_practice|Retrieval-augmented generation technique; no implicit LLM bit.
Clean Architecture|method_practice|Software dependency/design practice.
DNS|technology|Name-resolution protocol/system knowledge.
Oracle|technology|Proposed database-product sense from Oracle Database alias; bare Oracle remains scope-sensitive.
Windows|technology|Operating-system family, not every Microsoft product.
Data Visualization|method_practice|Visual communication of data through analytical graphics.
Functional Testing|method_practice|Checking behavior against functional requirements.
ISO 27001|technical_knowledge|Security-management standard knowledge in excerpts; not proof of certification held.
MVVM|method_practice|Model-view-viewmodel architecture pattern.
Algorithms|technical_knowledge|Algorithmic knowledge, not a soft behavioral capability.
Design Patterns|method_practice|Reusable software-design solutions.
Enterprise Architecture|method_practice|Enterprise architecture design/governance practice.
JSON|technology|Data-interchange format competence, not a document title.
Microsoft 365|tool|Named productivity suite, distinct from the bare Microsoft vendor.
Pattern Recognition|technical_knowledge|Recognition-method knowledge within computing.
Prototyping|method_practice|Prototype-building activity; bare Prototype alias is deferred pending context-specific approval.
DHCP|technology|Dynamic network-address configuration protocol.
Firmware|technology|Embedded software technology; not an Embedded Engineer role.
Grafana|tool|Monitoring/observability visualization product.
Microsoft Word|tool|Document-editing application, not a document itself.
Network Troubleshooting|method_practice|Diagnosing network faults, without vendor inference.
Neural Network|technical_knowledge|Neural-model concepts; no framework inference.
Odoo|technology|Named ERP application platform rather than bare ERP category.
Prompt Engineering|method_practice|Prompt-design practice in job demand; does not enable preprocessing model calls.
Test Case|document|Cases are artifacts and may be written or executed; no global renaming to authoring competence.
VPN|technology|Virtual-private-network technology class.
Attention to Detail|soft_skill|Specific attention-to-detail behavior; broader Carefulness/Cẩn thận alias deferred.
Data Governance|method_practice|Data ownership/control governance practice.
Hardware Maintenance|method_practice|Maintaining physical computing equipment.
Power Automate|tool|Workflow automation product; not automatically a DevOps platform.
Sketch|tool|Interface/vector design product.
Wireframing|method_practice|Low-fidelity interface layout practice; wireframe noun alias remains explicit proposal.
A/B Testing|method_practice|Controlled comparison experiment technique.
Active Directory|technology|Directory/identity service product.
Application Security|technical_knowledge|Application protection knowledge distinct from a named scanner.
Bash|technology|Shell scripting language.
CCNA|certification|Certification label; keep certification table without inferring networking competence.
Cisco|vendor|Network-vendor label even where equipment context exists; no one specific product skill established globally.
PowerPoint|tool|Presentation-authoring application, not presentation behavior itself.
Process Improvement|method_practice|Improving work processes as a practice.
Product Roadmapping|method_practice|Planning product evolution; roadmap noun alias needs explicit conceptual review.
Product Strategy|method_practice|Product-direction planning practice, not Product Manager title.
Spring Boot|technology|Java application framework; never infer a Java or Spring parent bit.
Statistics|technical_knowledge|Quantitative knowledge; not a behavioral soft skill.
TCP/IP|technology|Network protocol suite, not a device vendor.
BPMN|technology|Business-process modeling notation.
Confluence|tool|Team documentation/collaboration product.
Data Integration|method_practice|Combining data systems/sources, not a database engine.
Debugging|method_practice|Diagnosing and correcting software faults.
ELT|method_practice|Extract-load-transform processing pattern.
Linux System Administration|method_practice|Linux-specific administration; no implicit System Administration parent bit.
Monitoring|method_practice|Observing operational system state; not a specific monitoring product.
OWASP|technical_knowledge|Proposed web-security guidance knowledge supported by Top10 excerpts; not membership of an organization.
RTOS|technology|Real-time operating-system technology class.
SRS|document|Software-requirements specification artifact; some authoring context does not establish all tagged rows.
Scala|technology|Scala programming language.
VLAN|technology|Virtual LAN network-segmentation technology.
gRPC|technology|Remote procedure-call framework/protocol technology.
Cloud Infrastructure|technical_knowledge|Cloud infrastructure concepts rather than bare cloud-vendor name.
Data Quality|method_practice|Assessing and maintaining quality of data.
Databricks|tool|Data-processing platform, not a database/cache engine.
Entity Framework|technology|Object-relational data-access framework.
IT Operations|method_practice|Operating IT systems, not IT operator title.
Incident Response|method_practice|Responding to technical/security incidents.
MVC|method_practice|Model-view-controller architecture pattern.
Master Data Management|method_practice|Managing shared authoritative data entities, not a storage engine.
Microsoft Azure SQL Database|technology|Specific managed database product; no parent Azure bit.
PCI DSS|technical_knowledge|Payment-security compliance standard knowledge, not evidence of a personal certificate.
SOLID Principles|method_practice|Object-oriented software-design principles.
UML|technology|Software/system modeling notation.
Use Case|document|Requirements/modeling artifact; activity varies, so no invented use-case-authoring canonical.
VBA|technology|Visual Basic for Applications programming language.
Waterfall|method_practice|Sequential software-delivery methodology.
WordPress|technology|Web content/application platform.
XML|technology|Structured markup/data representation format.
AWS Lambda|technology|Specific serverless execution service, without implicit AWS parent propagation.
Adobe XD|tool|Interface prototyping/design application.
Apache Spark|tool|Distributed data-processing engine, not a database/cache.
BRD|document|Business-requirements document; keep activity excerpts but exclude bare artifact label from skills.
Change Management|method_practice|Managing process/organizational change as a delivery practice.
Cloud-native Architecture|method_practice|Architecture practice for cloud-native systems.
DBT|tool|Data-transformation/build tool, not a database engine.
Data Structures|technical_knowledge|Computing data-structure knowledge, not a soft skill.
Disaster Recovery|method_practice|Recovering IT services after disruption.
Embedded Systems|technical_knowledge|Embedded-computing knowledge distinct from an embedded job title.
Firebase|technology|Explicit application/backend service platform, not purely a database/cache.
Google Sheets|tool|Spreadsheet application product.
ITIL Foundation|certification|Foundation certification label; retain separately without inferring service-management skill.
Infrastructure as Code|method_practice|Managing infrastructure through versioned definitions.
Kubeflow|tool|ML workflow platform; no implicit ML competence.
PL/SQL|technology|Oracle procedural SQL language, without Oracle parent propagation.
Project Planning|method_practice|Planning project work/delivery rather than a manager title.
Prometheus|tool|Metrics collection/monitoring system.
Reinforcement Learning|technical_knowledge|Learning-from-reward methodology knowledge, not generic learning behavior.
Requirements Elicitation|method_practice|Gathering requirements; explicit Vietnamese activity alias is not just alternate spelling.
Routing|technical_knowledge|Network routing knowledge; no router-vendor inference.
SAP FICO|technology|Specific SAP financial/controlling module knowledge, distinct from bare SAP vendor.
SAP Integration Suite|technology|Named integration platform, not bare ecosystem name.
Technical Documentation|method_practice|Technical documentation practice as stated; no BRD/SRS-to-skill inference.
Technical Writing|method_practice|Writing technical material, distinct from owning a document tag.
Transformer|technical_knowledge|Transformer model architecture knowledge; no parent LLM inference.
UAT|method_practice|User acceptance testing practice.
User Flow|method_practice|Interface/user-journey flow design notation/practice; noun-to-practice interpretation remains proposed.
ABAP|technology|Explicit SAP programming language, not inferred from SAP.
ArgoCD|tool|GitOps continuous-delivery tool.
Backlog Management|method_practice|Prioritizing and managing delivery backlog.
CCNP|certification|Professional network certification label, not a networking skill bit.
CEH|certification|Security certification label; no implied penetration-testing bit.
CNN|technical_knowledge|Convolutional neural-network model-family knowledge.
COBOL|technology|COBOL programming language.
Continuous Improvement|method_practice|Iterative process-improvement practice; not a behavioral catch-all.
GNN|technical_knowledge|Graph neural-network knowledge.
Hardware Troubleshooting|method_practice|Diagnosing computing hardware faults.
JMeter|tool|Load/performance testing tool.
Juniper|vendor|Bare networking-vendor tag; device context varies, so no invented Juniper administration skill.
KNN|technical_knowledge|Nearest-neighbor algorithm knowledge.
LAN|technical_knowledge|Local-area-network concepts.
Looker Studio|tool|Reporting/dashboard product.
MATLAB|tool|Numerical-computing environment.
Pandas|technology|Dataframe processing library.
TensorFlow Serving|tool|Model-serving system, separate from TensorFlow framework.
Unreal Engine|tool|Interactive/game application engine.
ASP.NET Core|technology|Web application framework; no .NET parent propagation.
DynamoDB|technology|Specific managed NoSQL database; no AWS/NoSQL parent inference.
NumPy|technology|Numerical-array computing library.
Nuxt.js|technology|Vue application framework; no Vue parent inference.
OpenCV|technology|Computer-vision library; no implicit Computer Vision bit.
Redux|technology|Application state-management library.
Robot Framework|tool|Test automation framework; no parent testing bit.
CISSP|certification|Information-security certification, not proof of a specific skill.
Keras|technology|Neural-network library API, not inferred from Machine Learning.
MariaDB|technology|Named relational database engine.
WPF|technology|Windows desktop UI framework.
AutoCAD|tool|Observed CAD software tool; do not infer it from mechanical/domain tags.
Logical Reasoning|soft_skill|Logical-thinking behavior translated explicitly from Tu duy logic metadata, not from JD.
Creativity|soft_skill|Creative-thinking behavior; observed Vietnamese labels are explicit proposed translations.
Negotiation|soft_skill|Negotiation behavior, distinct from sales-domain tags.
Systems Thinking|soft_skill|Systemic-thinking behavior distinct from System Architecture technical practice.
Requirements Analysis|method_practice|Explicit requirements-analysis activity, not Business Analyst role.
Security Audit|method_practice|Security audit activity, not inferred from compliance certification.
IT Governance|method_practice|Governing IT decisions/controls, not IT Manager title.
Collaboration|soft_skill|Collaborative behavior retained separately; not silently generalized into Teamwork.
"""

ENTITY_NOTES = {}
for _line in NOTES.splitlines():
    if _line:
        _name, _entity, _reason = _line.split("|", 2)
        if _name in ENTITY_NOTES:
            raise ValueError(f"Repeated scope note: {_name}")
        ENTITY_NOTES[_name] = (_entity, _reason)

DEFERRED_ALIASES = {
    "Teamwork": {"collaboration": "Broader collaboration is not identical to team membership/cooperation; separate owner."},
    "Attention to Detail": {"cẩn thận": "Carefulness is broader than attention to detail; defer this generalization."},
    "Prototyping": {"prototype": "Artifact noun to activity inference; excerpts support some jobs, not global equivalence."},
}

EXTRA_RULES = {
    "AutoCAD": ([], "Tools, Architecture & Protocols"),
    "Logical Reasoning": (["Tư duy logic"], "Methodologies & Soft Skills"),
    "Creativity": (["Sáng tạo", "Tư duy sáng tạo"], "Methodologies & Soft Skills"),
    "Negotiation": (["Đàm phán"], "Methodologies & Soft Skills"),
    "Systems Thinking": (["Tư duy hệ thống"], "Methodologies & Soft Skills"),
    "Requirements Analysis": (["phân tích yêu cầu"], "Tools, Architecture & Protocols"),
    "Security Audit": ([], "Tools, Architecture & Protocols"),
    "IT Governance": ([], "Methodologies & Soft Skills"),
    "Collaboration": ([], "Methodologies & Soft Skills"),
}

TO_TOOLS = {"Kafka", "RabbitMQ", "Apache Spark", "Databricks", "DBT", "Firebase", "Power Automate"}
TO_METHODS = {
    "Data Modeling", "Data Management", "Data Governance", "Master Data Management", "Data Quality",
    "Data Integration", "ELT", "ETL", "MLOps", "DevSecOps", "System Administration",
    "Linux System Administration", "IT Operations", "Monitoring", "Incident Response", "Disaster Recovery",
}
# These do not fit the six legacy task buckets without broadening their meaning.
# Empty task group is a transparent metadata gap, not a seventh group or feature.
UNASSIGNED = {
    "Machine Learning", "Large Language Models", "Natural Language Processing", "Computer Vision",
    "Generative AI", "Neural Network", "Pattern Recognition", "Transformer", "CNN", "GNN", "KNN",
    "Reinforcement Learning", "Statistics", "Algorithms", "Data Structures", "Business Intelligence",
    "Data Warehousing", "English", "Japanese", "Data Engineering",
}
