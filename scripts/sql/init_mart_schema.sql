-- =============================================================================
-- VN-IT-Job-Mining: PostgreSQL Analytics Mart Initial Schema
-- Target Database: vn_it_jobs
-- Container: vn_it_jobs_postgres (Docker Compose)
-- Purpose: Serving curated IT jobs, skill rules, clusters, and anomaly insights
-- =============================================================================

-- 1. Create database vn_it_jobs if running on default postgres init
SELECT 'CREATE DATABASE vn_it_jobs'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'vn_it_jobs')\gexec

\c vn_it_jobs;

-- Enable extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Table 1: curated_jobs
-- Storage of cleaned & normalized IT jobs from Golden Master dataset
-- =============================================================================
CREATE TABLE IF NOT EXISTS curated_jobs (
    job_id VARCHAR(128) PRIMARY KEY,
    job_title TEXT NOT NULL,
    company_name TEXT,
    source_platform VARCHAR(32) NOT NULL,
    job_url TEXT,
    job_family VARCHAR(64) NOT NULL,
    seniority_level VARCHAR(64),
    province_norm VARCHAR(64),
    salary_min_vnd BIGINT,
    salary_max_vnd BIGINT,
    salary_avg_vnd BIGINT,
    is_salary_negotiable BOOLEAN DEFAULT FALSE,
    skills_array TEXT[] DEFAULT '{}',
    crawled_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_curated_jobs_family ON curated_jobs (job_family);
CREATE INDEX IF NOT EXISTS idx_curated_jobs_seniority ON curated_jobs (seniority_level);
CREATE INDEX IF NOT EXISTS idx_curated_jobs_province ON curated_jobs (province_norm);
CREATE INDEX IF NOT EXISTS idx_curated_jobs_salary_avg ON curated_jobs (salary_avg_vnd);
CREATE INDEX IF NOT EXISTS idx_curated_jobs_skills_gin ON curated_jobs USING GIN (skills_array);

-- =============================================================================
-- Table 2: skill_rules
-- Storage of FP-Growth association rules (Macro & Micro Job Family level)
-- =============================================================================
CREATE TABLE IF NOT EXISTS skill_rules (
    id SERIAL PRIMARY KEY,
    antecedents TEXT[] NOT NULL,
    consequents TEXT[] NOT NULL,
    support DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    lift DOUBLE PRECISION NOT NULL,
    conviction DOUBLE PRECISION,
    job_family_scope VARCHAR(64) DEFAULT 'ALL',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skill_rules_antecedents_gin ON skill_rules USING GIN (antecedents);
CREATE INDEX IF NOT EXISTS idx_skill_rules_consequents_gin ON skill_rules USING GIN (consequents);
CREATE INDEX IF NOT EXISTS idx_skill_rules_lift ON skill_rules (lift DESC);
CREATE INDEX IF NOT EXISTS idx_skill_rules_confidence ON skill_rules (confidence DESC);
CREATE INDEX IF NOT EXISTS idx_skill_rules_scope ON skill_rules (job_family_scope);

-- =============================================================================
-- Table 3: job_clusters
-- Storage of K-Means / HDBSCAN clusters and PCA 2D & 3D projection coordinates
-- =============================================================================
CREATE TABLE IF NOT EXISTS job_clusters (
    job_id VARCHAR(128) PRIMARY KEY,
    job_title TEXT,
    job_family VARCHAR(64),
    cluster_id INT NOT NULL,
    cluster_name VARCHAR(128),
    pca_x DOUBLE PRECISION NOT NULL,
    pca_y DOUBLE PRECISION NOT NULL,
    pca_z DOUBLE PRECISION,
    is_outlier BOOLEAN DEFAULT FALSE,
    glosh_outlier_score DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_job_clusters_cluster_id ON job_clusters (cluster_id);
CREATE INDEX IF NOT EXISTS idx_job_clusters_job_family ON job_clusters (job_family);
CREATE INDEX IF NOT EXISTS idx_job_clusters_outlier ON job_clusters (is_outlier);

-- =============================================================================
-- Table 4: job_anomalies
-- Storage of flagged suspicious jobs (Ghost jobs, unrealistic requirements)
-- =============================================================================
CREATE TABLE IF NOT EXISTS job_anomalies (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(128) NOT NULL,
    job_title TEXT,
    company_name TEXT,
    anomaly_score DOUBLE PRECISION NOT NULL,
    reason_code VARCHAR(64),
    detected_by VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_job_anomalies_score ON job_anomalies (anomaly_score DESC);
CREATE INDEX IF NOT EXISTS idx_job_anomalies_detected_by ON job_anomalies (detected_by);
