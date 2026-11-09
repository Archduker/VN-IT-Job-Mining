"""Danh mục chuẩn 230 kỹ năng IT (6 nhóm) theo đặc tả SPEC-06 và Task 05 của Phát.

Quy định chuẩn:
- Đúng 230 kỹ năng, cố định thứ tự từ 0 đến 229 để đảm bảo tính tái lập (Reproducibility).
- Bao phủ 6 nhóm IT cốt lõi:
  1. Ngôn ngữ lập trình (Programming Languages - 35)
  2. Framework & Thư viện (Frameworks & Libraries - 55)
  3. Cơ sở dữ liệu & Streaming (Databases & Streaming - 35)
  4. Đám mây, Hạ tầng, An ninh & DevOps (Cloud, DevOps & Security - 45)
  5. Công cụ, Kiến trúc, Giao thức & Kiểm thử (Tools, Architecture & QA - 35)
  6. Phương pháp luận, Kỹ năng mềm & Data/AI (Methodologies, Soft Skills & Data/AI - 25)
"""

from __future__ import annotations

from typing import NamedTuple


def build_skill_lookup(entries):
    """Return unambiguous aliases and explicit conflicts; never silently last-wins."""
    owners = {}
    slugs = set()
    for canonical, slug, _group, aliases in entries:
        if slug in slugs:
            raise ValueError(f"Duplicate skill slug: {slug}")
        slugs.add(slug)
        for alias in [canonical, slug, *aliases]:
            owners.setdefault(alias.lower(), set()).add(slug)
    conflicts = {k: sorted(v) for k, v in owners.items() if len(v) > 1}
    lookup = {k: next(iter(v)) for k, v in owners.items() if len(v) == 1}
    return lookup, conflicts


class SkillEntry(NamedTuple):
    index: int
    canonical: str
    slug: str
    column_name: str
    group: str
    aliases: list[str]


RAW_TAXONOMY_230 = [
    # -------------------------------------------------------------------------
    # Nhóm 1: Ngôn ngữ lập trình (Programming Languages - 35 skills)
    # -------------------------------------------------------------------------
    ("Python", "python", "programming_languages", ["python", "python3", "py"]),
    (
        "Java",
        "java",
        "programming_languages",
        ["java", "core java", "java 8", "java 11", "java 17", "java 21"],
    ),
    (
        "JavaScript",
        "javascript",
        "programming_languages",
        ["javascript", "js", "ecmascript", "es6"],
    ),
    ("TypeScript", "typescript", "programming_languages", ["typescript", "ts"]),
    ("C#", "csharp", "programming_languages", ["c#", "csharp", "c sharp"]),
    ("C++", "cpp", "programming_languages", ["c++", "cpp"]),
    (
        "C",
        "c_lang",
        "programming_languages",
        ["c programming", "ngôn ngữ c", "lập trình c", "embedded c"],
    ),
    (
        "Golang",
        "golang",
        "programming_languages",
        ["golang", "go lang", "go language", "ngôn ngữ go"],
    ),
    ("PHP", "php", "programming_languages", ["php", "php7", "php8"]),
    ("Ruby", "ruby", "programming_languages", ["ruby"]),
    ("Rust", "rust", "programming_languages", ["rust", "rustlang"]),
    ("Kotlin", "kotlin", "programming_languages", ["kotlin"]),
    ("Swift", "swift", "programming_languages", ["swift"]),
    ("Dart", "dart", "programming_languages", ["dart"]),
    ("Scala", "scala", "programming_languages", ["scala"]),
    ("R", "r_lang", "programming_languages", ["r programming", "r language", "ngôn ngữ r"]),
    (
        "Shell/Bash",
        "bash",
        "programming_languages",
        ["bash", "shell", "sh", "shell script", "bash script"],
    ),
    ("PowerShell", "powershell", "programming_languages", ["powershell"]),
    ("Perl", "perl", "programming_languages", ["perl"]),
    ("Lua", "lua", "programming_languages", ["lua"]),
    ("Haskell", "haskell", "programming_languages", ["haskell"]),
    ("Elixir", "elixir", "programming_languages", ["elixir"]),
    ("Clojure", "clojure", "programming_languages", ["clojure"]),
    ("Objective-C", "objective_c", "programming_languages", ["objective-c", "objective c", "objc"]),
    ("Assembly", "assembly", "programming_languages", ["assembly", "asm"]),
    ("Julia", "julia", "programming_languages", ["julia"]),
    ("MATLAB", "matlab", "programming_languages", ["matlab"]),
    ("Groovy", "groovy", "programming_languages", ["groovy"]),
    ("Solidity", "solidity", "programming_languages", ["solidity"]),
    ("Visual Basic", "visual_basic", "programming_languages", ["visual basic", "vb", "vb.net"]),
    ("Fortran", "fortran", "programming_languages", ["fortran"]),
    ("Erlang", "erlang", "programming_languages", ["erlang"]),
    ("F#", "fsharp", "programming_languages", ["f#", "fsharp"]),
    ("Apex", "apex", "programming_languages", ["apex"]),
    ("COBOL", "cobol", "programming_languages", ["cobol"]),
    # -------------------------------------------------------------------------
    # Nhóm 2: Framework & Thư viện (Frameworks & Libraries - 55 skills)
    # -------------------------------------------------------------------------
    ("React", "react", "frameworks_libraries", ["react", "reactjs", "react.js"]),
    ("Vue", "vue", "frameworks_libraries", ["vue", "vuejs", "vue.js", "vue 3"]),
    ("Angular", "angular", "frameworks_libraries", ["angular", "angularjs", "angular 2+"]),
    ("Node.js", "nodejs", "frameworks_libraries", ["node", "nodejs", "node.js"]),
    ("Next.js", "nextjs", "frameworks_libraries", ["next", "nextjs", "next.js"]),
    ("Nuxt.js", "nuxtjs", "frameworks_libraries", ["nuxt", "nuxtjs", "nuxt.js"]),
    ("NestJS", "nestjs", "frameworks_libraries", ["nestjs", "nest.js"]),
    ("Express.js", "express", "frameworks_libraries", ["express", "expressjs", "express.js"]),
    ("Django", "django", "frameworks_libraries", ["django"]),
    ("FastAPI", "fastapi", "frameworks_libraries", ["fastapi"]),
    ("Flask", "flask", "frameworks_libraries", ["flask"]),
    ("Spring Boot", "spring_boot", "frameworks_libraries", ["spring boot", "springboot"]),
    (
        "Spring MVC",
        "spring_mvc",
        "frameworks_libraries",
        ["spring mvc", "spring framework", "spring"],
    ),
    ("Hibernate", "hibernate", "frameworks_libraries", ["hibernate", "jpa"]),
    (
        ".NET",
        "dotnet",
        "frameworks_libraries",
        [".net", "dotnet", ".net core", "asp.net", "asp.net core"],
    ),
    ("Laravel", "laravel", "frameworks_libraries", ["laravel"]),
    ("Symfony", "symfony", "frameworks_libraries", ["symfony"]),
    ("CodeIgniter", "codeigniter", "frameworks_libraries", ["codeigniter"]),
    ("Ruby on Rails", "rails", "frameworks_libraries", ["rails", "ruby on rails"]),
    ("Flutter", "flutter", "frameworks_libraries", ["flutter"]),
    (
        "React Native",
        "react_native",
        "frameworks_libraries",
        ["react native", "react-native", "rn"],
    ),
    ("Android SDK", "android_sdk", "frameworks_libraries", ["android sdk", "android"]),
    ("iOS SDK", "ios_sdk", "frameworks_libraries", ["ios sdk", "ios"]),
    ("SwiftUI", "swiftui", "frameworks_libraries", ["swiftui"]),
    ("Jetpack Compose", "jetpack_compose", "frameworks_libraries", ["jetpack compose", "compose"]),
    ("jQuery", "jquery", "frameworks_libraries", ["jquery"]),
    ("Svelte", "svelte", "frameworks_libraries", ["svelte", "sveltekit"]),
    ("Tailwind CSS", "tailwind", "frameworks_libraries", ["tailwind", "tailwindcss"]),
    ("Bootstrap", "bootstrap", "frameworks_libraries", ["bootstrap"]),
    ("Redux", "redux", "frameworks_libraries", ["redux", "redux toolkit"]),
    ("GraphQL", "graphql", "frameworks_libraries", ["graphql", "apollo"]),
    ("PyTorch", "pytorch", "frameworks_libraries", ["pytorch"]),
    ("TensorFlow", "tensorflow", "frameworks_libraries", ["tensorflow", "tf"]),
    ("Keras", "keras", "frameworks_libraries", ["keras"]),
    ("Scikit-learn", "scikit_learn", "frameworks_libraries", ["scikit-learn", "sklearn"]),
    ("OpenCV", "opencv", "frameworks_libraries", ["opencv"]),
    ("Pandas", "pandas", "frameworks_libraries", ["pandas"]),
    ("NumPy", "numpy", "frameworks_libraries", ["numpy"]),
    (
        "Hugging Face",
        "hugging_face",
        "frameworks_libraries",
        ["hugging face", "huggingface", "transformers"],
    ),
    ("LangChain", "langchain", "frameworks_libraries", ["langchain"]),
    ("Apache Spark", "spark", "frameworks_libraries", ["spark", "pyspark", "apache spark"]),
    ("Apache Hadoop", "hadoop", "frameworks_libraries", ["hadoop", "hdfs"]),
    ("Apache Airflow", "airflow", "frameworks_libraries", ["airflow", "apache airflow"]),
    ("Celery", "celery", "frameworks_libraries", ["celery"]),
    ("Electron", "electron", "frameworks_libraries", ["electron", "electronjs"]),
    ("Ionic", "ionic", "frameworks_libraries", ["ionic"]),
    ("Xamarin", "xamarin", "frameworks_libraries", ["xamarin"]),
    ("Blazor", "blazor", "frameworks_libraries", ["blazor"]),
    ("Gin", "gin", "frameworks_libraries", ["gin", "gin-gonic"]),
    ("Echo", "echo", "frameworks_libraries", ["echo framework", "labstack/echo"]),
    ("Fiber", "fiber", "frameworks_libraries", ["gofiber", "fiber"]),
    ("Fastify", "fastify", "frameworks_libraries", ["fastify"]),
    ("Prisma", "prisma", "frameworks_libraries", ["prisma", "prisma orm"]),
    ("Sequelize", "sequelize", "frameworks_libraries", ["sequelize"]),
    ("TypeORM", "typeorm", "frameworks_libraries", ["typeorm"]),
    # -------------------------------------------------------------------------
    # Nhóm 3: Cơ sở dữ liệu & Streaming (Databases & Streaming - 35 skills)
    # -------------------------------------------------------------------------
    ("SQL", "sql", "databases_streaming", ["sql"]),
    ("PostgreSQL", "postgresql", "databases_streaming", ["postgresql", "postgres", "psql"]),
    ("MySQL", "mysql", "databases_streaming", ["mysql", "mariadb"]),
    ("SQLite", "sqlite", "databases_streaming", ["sqlite", "sqlite3"]),
    ("Oracle DB", "oracle_db", "databases_streaming", ["oracle", "oracle db", "pl/sql"]),
    (
        "Microsoft SQL Server",
        "sql_server",
        "databases_streaming",
        ["sql server", "mssql", "ms sql", "t-sql"],
    ),
    ("MongoDB", "mongodb", "databases_streaming", ["mongodb", "mongo", "nosql mongodb"]),
    ("Redis", "redis", "databases_streaming", ["redis", "redis cache"]),
    (
        "Elasticsearch",
        "elasticsearch",
        "databases_streaming",
        ["elasticsearch", "elastic search", "elk"],
    ),
    ("OpenSearch", "opensearch", "databases_streaming", ["opensearch"]),
    ("Apache Kafka", "kafka", "databases_streaming", ["kafka", "apache kafka"]),
    ("RabbitMQ", "rabbitmq", "databases_streaming", ["rabbitmq"]),
    ("Cassandra", "cassandra", "databases_streaming", ["cassandra", "apache cassandra"]),
    ("DynamoDB", "dynamodb", "databases_streaming", ["dynamodb", "amazon dynamodb"]),
    ("Neo4j", "neo4j", "databases_streaming", ["neo4j", "graph database"]),
    ("Apache HBase", "hbase", "databases_streaming", ["hbase", "apache hbase"]),
    ("ClickHouse", "clickhouse", "databases_streaming", ["clickhouse"]),
    ("Google BigQuery", "bigquery", "databases_streaming", ["bigquery", "google bigquery"]),
    ("Snowflake", "snowflake", "databases_streaming", ["snowflake"]),
    ("Amazon Redshift", "redshift", "databases_streaming", ["redshift", "amazon redshift"]),
    ("Memcached", "memcached", "databases_streaming", ["memcached"]),
    ("Couchbase", "couchbase", "databases_streaming", ["couchbase"]),
    ("Firebase", "firebase", "databases_streaming", ["firebase", "firestore", "realtime database"]),
    ("Supabase", "supabase", "databases_streaming", ["supabase"]),
    ("Apache Hive", "hive", "databases_streaming", ["hive", "apache hive"]),
    ("CockroachDB", "cockroachdb", "databases_streaming", ["cockroachdb"]),
    ("TiDB", "tidb", "databases_streaming", ["tidb"]),
    ("InfluxDB", "influxdb", "databases_streaming", ["influxdb", "time-series database"]),
    ("TimescaleDB", "timescaledb", "databases_streaming", ["timescaledb"]),
    ("Milvus", "milvus", "databases_streaming", ["milvus", "vector database"]),
    ("ChromaDB", "chromadb", "databases_streaming", ["chromadb", "chroma"]),
    ("Qdrant", "qdrant", "databases_streaming", ["qdrant"]),
    ("Pinecone", "pinecone", "databases_streaming", ["pinecone"]),
    ("NoSQL General", "nosql", "databases_streaming", ["nosql"]),
    (
        "Data Warehouse",
        "data_warehouse",
        "databases_streaming",
        ["data warehouse", "dwh", "data warehousing"],
    ),
    # -------------------------------------------------------------------------
    # Nhóm 4: Đám mây, Hạ tầng, An ninh & DevOps (Cloud, DevOps & Security - 45 skills)
    # -------------------------------------------------------------------------
    ("AWS", "aws", "cloud_devops_security", ["aws", "amazon web services"]),
    ("Amazon EC2", "ec2", "cloud_devops_security", ["ec2", "amazon ec2"]),
    ("Amazon S3", "s3", "cloud_devops_security", ["s3", "amazon s3"]),
    ("AWS Lambda", "lambda", "cloud_devops_security", ["lambda", "aws lambda", "serverless"]),
    ("Microsoft Azure", "azure", "cloud_devops_security", ["azure", "microsoft azure"]),
    (
        "Google Cloud Platform",
        "gcp",
        "cloud_devops_security",
        ["gcp", "google cloud", "google cloud platform"],
    ),
    ("Docker", "docker", "cloud_devops_security", ["docker", "container", "containerization"]),
    (
        "Docker Compose",
        "docker_compose",
        "cloud_devops_security",
        ["docker-compose", "docker compose"],
    ),
    ("Kubernetes", "kubernetes", "cloud_devops_security", ["kubernetes", "k8s"]),
    ("Helm", "helm", "cloud_devops_security", ["helm", "helm chart"]),
    (
        "Terraform",
        "terraform",
        "cloud_devops_security",
        ["terraform", "iac", "infrastructure as code"],
    ),
    ("Ansible", "ansible", "cloud_devops_security", ["ansible"]),
    ("CI/CD", "cicd", "cloud_devops_security", ["ci/cd", "cicd", "continuous integration"]),
    ("Jenkins", "jenkins", "cloud_devops_security", ["jenkins"]),
    ("GitLab CI", "gitlab_ci", "cloud_devops_security", ["gitlab-ci", "gitlab ci"]),
    (
        "GitHub Actions",
        "github_actions",
        "cloud_devops_security",
        ["github actions", "github action"],
    ),
    ("ArgoCD", "argocd", "cloud_devops_security", ["argocd", "argo cd"]),
    ("Prometheus", "prometheus", "cloud_devops_security", ["prometheus"]),
    ("Grafana", "grafana", "cloud_devops_security", ["grafana"]),
    ("ELK Stack", "elk_stack", "cloud_devops_security", ["elk stack", "logstash", "kibana"]),
    ("Linux", "linux", "cloud_devops_security", ["linux"]),
    ("Ubuntu", "ubuntu", "cloud_devops_security", ["ubuntu"]),
    ("CentOS", "centos", "cloud_devops_security", ["centos", "rhel", "red hat"]),
    ("Nginx", "nginx", "cloud_devops_security", ["nginx"]),
    ("Apache HTTP Server", "apache_http", "cloud_devops_security", ["apache web server", "httpd"]),
    ("Cloudflare", "cloudflare", "cloud_devops_security", ["cloudflare"]),
    ("OpenShift", "openshift", "cloud_devops_security", ["openshift", "red hat openshift"]),
    ("Pulumi", "pulumi", "cloud_devops_security", ["pulumi"]),
    ("HashiCorp Vault", "vault", "cloud_devops_security", ["vault", "hashicorp vault"]),
    ("SonarQube", "sonarqube", "cloud_devops_security", ["sonarqube", "sonar"]),
    (
        "Cybersecurity",
        "cybersecurity",
        "cloud_devops_security",
        ["cybersecurity", "cyber security", "an ninh mạng"],
    ),
    (
        "Penetration Testing",
        "pentest",
        "cloud_devops_security",
        ["pentest", "penetration testing", "ethical hacking"],
    ),
    (
        "Information Security",
        "infosec",
        "cloud_devops_security",
        ["infosec", "an toàn thông tin", "information security"],
    ),
    (
        "SIEM",
        "siem",
        "cloud_devops_security",
        ["siem", "security information and event management"],
    ),
    ("SOC", "soc", "cloud_devops_security", ["soc", "security operations center"]),
    ("OWASP", "owasp", "cloud_devops_security", ["owasp", "owasp top 10"]),
    ("Firewall", "firewall", "cloud_devops_security", ["firewall", "waf"]),
    ("ISO 27001", "iso_27001", "cloud_devops_security", ["iso 27001", "iso/iec 27001"]),
    ("VPN", "vpn", "cloud_devops_security", ["vpn", "virtual private network"]),
    ("Zero Trust", "zero_trust", "cloud_devops_security", ["zero trust"]),
    ("IAM", "iam", "cloud_devops_security", ["iam", "identity and access management"]),
    ("DevSecOps", "devsecops", "cloud_devops_security", ["devsecops"]),
    ("Incident Response", "incident_response", "cloud_devops_security", ["incident response"]),
    ("Network Security", "network_security", "cloud_devops_security", ["network security"]),
    (
        "Disaster Recovery",
        "disaster_recovery",
        "cloud_devops_security",
        ["disaster recovery", "bcp"],
    ),
    # -------------------------------------------------------------------------
    # Nhóm 5: Công cụ, Kiến trúc, Giao thức & Kiểm thử (Tools, Architecture & QA - 35 skills)
    # -------------------------------------------------------------------------
    ("Git", "git", "tools_architecture_qa", ["git"]),
    ("GitHub", "github", "tools_architecture_qa", ["github"]),
    ("GitLab", "gitlab", "tools_architecture_qa", ["gitlab"]),
    ("Bitbucket", "bitbucket", "tools_architecture_qa", ["bitbucket"]),
    ("Jira", "jira", "tools_architecture_qa", ["jira"]),
    ("Confluence", "confluence", "tools_architecture_qa", ["confluence"]),
    (
        "Microservices",
        "microservices",
        "tools_architecture_qa",
        ["microservices", "microservice", "micro-services"],
    ),
    (
        "RESTful API",
        "rest_api",
        "tools_architecture_qa",
        ["restful api", "rest api", "rest", "restful"],
    ),
    ("gRPC", "grpc", "tools_architecture_qa", ["grpc", "protobuf"]),
    ("SOAP", "soap", "tools_architecture_qa", ["soap"]),
    ("WebSocket", "websocket", "tools_architecture_qa", ["websocket", "socket.io"]),
    (
        "Design Patterns",
        "design_patterns",
        "tools_architecture_qa",
        ["design patterns", "design pattern"],
    ),
    (
        "OOP",
        "oop",
        "tools_architecture_qa",
        ["oop", "object-oriented programming", "hướng đối tượng"],
    ),
    (
        "Clean Architecture",
        "clean_architecture",
        "tools_architecture_qa",
        ["clean architecture", "solid"],
    ),
    ("Domain-Driven Design", "ddd", "tools_architecture_qa", ["ddd", "domain-driven design"]),
    ("MVC Architecture", "mvc", "tools_architecture_qa", ["mvc", "model-view-controller"]),
    (
        "Unit Testing",
        "unit_test",
        "tools_architecture_qa",
        ["unit test", "unit testing", "kiểm thử đơn vị"],
    ),
    ("JUnit", "junit", "tools_architecture_qa", ["junit"]),
    ("PyTest", "pytest", "tools_architecture_qa", ["pytest"]),
    ("Jest", "jest", "tools_architecture_qa", ["jest"]),
    ("Mocha", "mocha", "tools_architecture_qa", ["mocha"]),
    (
        "Automation Testing",
        "automation_test",
        "tools_architecture_qa",
        ["automation test", "automation testing", "kiểm thử tự động"],
    ),
    (
        "Manual Testing",
        "manual_test",
        "tools_architecture_qa",
        ["manual test", "manual testing", "kiểm thử thủ công"],
    ),
    ("Selenium", "selenium", "tools_architecture_qa", ["selenium", "selenium webdriver"]),
    ("Cypress", "cypress", "tools_architecture_qa", ["cypress"]),
    ("Playwright", "playwright", "tools_architecture_qa", ["playwright"]),
    ("Postman", "postman", "tools_architecture_qa", ["postman"]),
    ("JMeter", "jmeter", "tools_architecture_qa", ["jmeter", "apache jmeter"]),
    ("Appium", "appium", "tools_architecture_qa", ["appium"]),
    ("Cucumber", "cucumber", "tools_architecture_qa", ["cucumber", "bdd"]),
    ("TestNG", "testng", "tools_architecture_qa", ["testng"]),
    ("QA/QC General", "qa_qc", "tools_architecture_qa", ["qa", "qc", "qa/qc", "quality assurance"]),
    ("Bug Tracking", "bug_tracking", "tools_architecture_qa", ["bug tracking", "trello"]),
    (
        "Performance Testing",
        "performance_test",
        "tools_architecture_qa",
        ["performance test", "load test", "stress test"],
    ),
    (
        "Security Testing",
        "security_test",
        "tools_architecture_qa",
        ["security test", "security testing"],
    ),
    # -------------------------------------------------------------------------
    # Nhóm 6: Phương pháp luận, Kỹ năng mềm & Data/AI (Methodologies, Soft Skills & Data/AI - 25 skills)
    # -------------------------------------------------------------------------
    (
        "Agile/Scrum",
        "agile_scrum",
        "methodologies_softskills_data",
        ["agile", "scrum", "kanban", "sprint"],
    ),
    ("Waterfall", "waterfall", "methodologies_softskills_data", ["waterfall"]),
    (
        "Problem Solving",
        "problem_solving",
        "methodologies_softskills_data",
        ["problem solving", "giải quyết vấn đề", "critical thinking"],
    ),
    (
        "Teamwork",
        "teamwork",
        "methodologies_softskills_data",
        ["teamwork", "làm việc nhóm", "collaboration"],
    ),
    (
        "Communication",
        "communication",
        "methodologies_softskills_data",
        ["giao tiếp", "communication"],
    ),
    (
        "English Proficiency",
        "english",
        "methodologies_softskills_data",
        ["tiếng anh", "english", "toeic", "ielts"],
    ),
    (
        "Japanese Proficiency",
        "japanese",
        "methodologies_softskills_data",
        ["tiếng nhật", "japanese", "jlpt", "n1", "n2", "n3"],
    ),
    (
        "Critical Thinking",
        "logical_thinking",
        "methodologies_softskills_data",
        ["tư duy logic", "tư duy phản biện", "logical thinking"],
    ),
    (
        "Time Management",
        "time_management",
        "methodologies_softskills_data",
        ["quản lý thời gian", "time management"],
    ),
    (
        "Presentation Skills",
        "presentation",
        "methodologies_softskills_data",
        ["thuyết trình", "presentation"],
    ),
    (
        "Project Management",
        "project_management",
        "methodologies_softskills_data",
        ["project management", "quản lý dự án", "pmp"],
    ),
    (
        "Business Analysis",
        "business_analysis",
        "methodologies_softskills_data",
        ["business analysis", "ba", "phân tích nghiệp vụ"],
    ),
    (
        "Data Analysis",
        "data_analysis",
        "methodologies_softskills_data",
        ["data analysis", "data analytics", "phân tích dữ liệu"],
    ),
    (
        "ETL Pipeline",
        "etl",
        "methodologies_softskills_data",
        ["etl", "extract transform load", "data pipeline"],
    ),
    (
        "Business Intelligence",
        "bi",
        "methodologies_softskills_data",
        ["bi", "business intelligence"],
    ),
    ("Power BI", "power_bi", "methodologies_softskills_data", ["power bi", "powerbi"]),
    ("Tableau", "tableau", "methodologies_softskills_data", ["tableau"]),
    (
        "Large Language Models",
        "llm",
        "methodologies_softskills_data",
        ["llm", "large language model", "gpt"],
    ),
    (
        "Generative AI",
        "genai",
        "methodologies_softskills_data",
        ["generative ai", "genai", "gen ai"],
    ),
    (
        "Computer Vision",
        "computer_vision",
        "methodologies_softskills_data",
        ["computer vision", "thị giác máy tính"],
    ),
    (
        "Natural Language Processing",
        "nlp",
        "methodologies_softskills_data",
        ["nlp", "natural language processing", "xử lý ngôn ngữ tự nhiên"],
    ),
    (
        "Machine Learning General",
        "machine_learning",
        "methodologies_softskills_data",
        ["machine learning", "deep learning", "học máy"],
    ),
    ("FinTech", "fintech", "methodologies_softskills_data", ["fintech", "banking technology"]),
    (
        "E-Commerce",
        "ecommerce",
        "methodologies_softskills_data",
        ["ecommerce", "e-commerce", "thương mại điện tử"],
    ),
    (
        "Blockchain",
        "blockchain",
        "methodologies_softskills_data",
        ["blockchain", "web3", "smart contract"],
    ),
]

assert len(RAW_TAXONOMY_230) == 230, (
    f"Taxonomy must contain exactly 230 skills, got {len(RAW_TAXONOMY_230)}"
)

TAXONOMY_230: list[SkillEntry] = []
ORDERED_SKILL_COLUMNS: list[str] = []

for idx, (canonical, slug, group, aliases) in enumerate(RAW_TAXONOMY_230):
    col_name = f"skill_{slug}"
    entry = SkillEntry(
        index=idx,
        canonical=canonical,
        slug=slug,
        column_name=col_name,
        group=group,
        aliases=aliases,
    )
    TAXONOMY_230.append(entry)
    ORDERED_SKILL_COLUMNS.append(col_name)

EXACT_SKILL_COUNT = 230

# Ambiguous aliases are deliberately unresolved, not assigned a new meaning.
SKILL_LOOKUP_MAP, ALIAS_CONFLICTS = build_skill_lookup(RAW_TAXONOMY_230)
