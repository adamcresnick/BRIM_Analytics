# Production Deployment Roadmap

**Purpose:** Comprehensive plan to transition from single-patient local testing to production batch processing

**Last Updated:** 2025-10-20
**Current System Version:** v1.2.0 (Local Test Mode)
**Target Production Version:** v2.0.0

---

## Table of Contents

1. [Current State Assessment](#current-state-assessment)
2. [Production Requirements](#production-requirements)
3. [Infrastructure Setup](#infrastructure-setup)
4. [Code Modifications](#code-modifications)
5. [Deployment Phases](#deployment-phases)
6. [Testing Strategy](#testing-strategy)
7. [Monitoring & Alerting](#monitoring--alerting)
8. [Cost Estimation](#cost-estimation)
9. [Timeline & Milestones](#timeline--milestones)
10. [Risk Assessment](#risk-assessment)
11. [Rollback Plan](#rollback-plan)

---

## Current State Assessment

### ✅ What's Working (v1.2.0)

**Core Workflow:**
- ✅ Single-patient comprehensive abstraction (all phases functional)
- ✅ Multi-source extraction (imaging text, PDFs, operative reports, progress notes)
- ✅ Document text caching with provenance (~80% cost savings)
- ✅ Progress note prioritization (660 → ~20-40 notes, 96% reduction)
- ✅ Workflow monitoring (multi-level logging, error tracking)
- ✅ Emergency partial data save on errors
- ✅ Timestamped abstractions (no overwrites)

**Components:**
- ✅ Agent 1 (Claude - MasterAgent): Orchestration, validation, adjudication
- ✅ Agent 2 (MedGemma 27B via Ollama): Medical text extraction
- ✅ BinaryFileAgent: PDF/HTML/text extraction from S3
- ✅ DocumentTextCache: Cached text with SHA256 deduplication
- ✅ ProgressNotePrioritizer: Intelligent note selection
- ✅ WorkflowMonitoring: Enhanced logging framework

**Data Sources:**
- ✅ AWS Athena (v_imaging, v_binary_files, v_procedures_tumor)
- ✅ S3 binary storage (Binary FHIR resources)
- ✅ DuckDB (timeline, document cache)

### 🔴 What's Missing for Production

**Batch Processing:**
- ❌ No batch orchestration (currently manual single-patient execution)
- ❌ No patient cohort management
- ❌ No parallel patient processing
- ❌ No job queue system

**Scalability:**
- ❌ Single-machine MedGemma (no distributed inference)
- ❌ No auto-scaling infrastructure
- ❌ No load balancing
- ❌ DuckDB not suitable for concurrent multi-patient writes

**Reliability:**
- ❌ No automatic retry logic for transient failures
- ❌ No dead letter queue for failed extractions
- ❌ No workflow resume from arbitrary checkpoint
- ❌ No distributed locking (prevent duplicate processing)

**Monitoring:**
- ❌ No centralized monitoring dashboard
- ❌ No real-time alerting (email/Slack configured but not production-ready)
- ❌ No SLA tracking
- ❌ No cost monitoring per patient/cohort

**Data Management:**
- ❌ No automated QA review workflow
- ❌ No version control for extractions (Git-like for data)
- ❌ No data validation pipeline
- ❌ No automated backup/recovery

**Security & Compliance:**
- ❌ No HIPAA compliance audit trail
- ❌ No encryption at rest for local databases
- ❌ No role-based access control
- ❌ No PHI de-identification for development/testing

---

## Production Requirements

### Functional Requirements

**FR-1: Batch Processing**
- Process 100+ patients per run
- Support cohort-based execution (e.g., "all patients with diagnosis X")
- Parallel processing with configurable concurrency
- Automatic patient queue management

**FR-2: Reliability & Recovery**
- Automatic retry with exponential backoff (3 attempts max)
- Resume from last successful checkpoint on failure
- Dead letter queue for persistently failing patients
- Distributed locking to prevent duplicate processing

**FR-3: Scalability**
- Support 1000+ patient cohorts
- Horizontal scaling for MedGemma inference
- Handle concurrent extractions (10-50 patients in parallel)
- Database suitable for concurrent writes

**FR-4: Monitoring & Observability**
- Real-time dashboard showing extraction progress
- Automated alerts for failures, performance degradation, cost overruns
- Per-patient and per-cohort metrics
- SLA tracking (e.g., 95% of patients complete within 2 hours)

**FR-5: Data Quality**
- Automated QA validation rules
- Confidence threshold filtering (flag low-confidence extractions)
- Temporal inconsistency detection (already implemented, needs production integration)
- Human-in-the-loop review queue for flagged extractions

**FR-6: Cost Management**
- Per-patient cost tracking (Athena queries, S3 requests, compute time)
- Budget alerts and limits
- Cost optimization recommendations
- Cache hit rate monitoring

### Non-Functional Requirements

**NFR-1: Performance**
- Single patient extraction: < 10 minutes (current: ~26 minutes for 82 imaging reports)
- 100-patient cohort: < 4 hours
- Cache hit rate: > 70% for repeat abstractions

**NFR-2: Availability**
- System uptime: 99% (excluding planned maintenance)
- Automatic recovery from transient failures
- No data loss on system failures

**NFR-3: Security & Compliance**
- HIPAA-compliant logging (no PHI in logs)
- Encryption at rest for all databases
- Audit trail for all extractions
- Role-based access control

**NFR-4: Maintainability**
- Automated testing (unit, integration, end-to-end)
- CI/CD pipeline for deployments
- Comprehensive documentation
- Version control for all components

---

## Infrastructure Setup

### Phase 1: Cloud Infrastructure (AWS)

#### 1.1 Compute Resources

**Option A: EC2 + Auto Scaling**
- **Master Orchestrator**: `t3.xlarge` (4 vCPU, 16 GB RAM)
  - Runs Agent 1 (Claude API calls)
  - Manages job queue
  - Coordinates batch processing

- **MedGemma Inference Cluster**: `g5.2xlarge` (8 vCPU, 32 GB RAM, 1x NVIDIA A10G GPU)
  - Auto-scaling group: 1-10 instances
  - Each instance runs Ollama with gemma2:27b
  - Load balanced via AWS ELB
  - Scale up based on queue depth

**Option B: ECS Fargate (Containerized)**
- Master orchestrator: Fargate task (4 vCPU, 16 GB)
- MedGemma workers: Fargate GPU tasks
- Easier deployment, higher cost per hour

**Recommendation:** Start with Option A (EC2) for better GPU support and lower cost

#### 1.2 Storage

**S3 Buckets:**
- `radiant-extractions-prd/` - Timestamped abstraction outputs
  - Lifecycle policy: Archive to Glacier after 90 days
  - Versioning enabled

- `radiant-cache-prd/` - Document text cache backups
  - Daily snapshots

**RDS PostgreSQL (Replace DuckDB):**
- Instance: `db.r6g.xlarge` (4 vCPU, 32 GB RAM)
- Multi-AZ deployment for high availability
- Automated backups (7-day retention)
- Schemas:
  - `timeline` - Patient timeline events
  - `document_cache` - Cached extracted text
  - `workflow_metadata` - Job tracking, metrics
  - `qa_review` - Flagged extractions for human review

#### 1.3 Queue System

**AWS SQS:**
- `radiant-patient-extraction-queue` - Main job queue
  - Visibility timeout: 2 hours
  - Message retention: 14 days
  - DLQ: `radiant-patient-extraction-dlq` (failed jobs)

- `radiant-qa-review-queue` - Low-confidence extractions for review
  - Triggers human-in-the-loop workflow

#### 1.4 Monitoring

**CloudWatch:**
- Custom metrics: patients processed, extraction duration, cache hit rate, cost per patient
- Alarms: queue depth > 1000, extraction failure rate > 5%, cost > budget
- Log groups for each component

**Grafana Dashboard:**
- Real-time extraction progress
- Per-cohort metrics
- Cost tracking
- SLA compliance

### Phase 2: Application Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR (Master EC2)                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Batch Controller                                          │ │
│  │  • Reads patient cohort from S3/database                  │ │
│  │  • Sends patient IDs to SQS queue                         │ │
│  │  • Monitors progress, handles retries                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Agent 1 (MasterAgent - Claude)                           │ │
│  │  • Orchestrates extraction workflow                        │ │
│  │  • Queries Agent 2 workers via load balancer              │ │
│  │  • Performs adjudication and QA                            │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
                 ┌─────────────────────┐
                 │   SQS Patient Queue  │
                 │   (1000s of patients)│
                 └─────────┬───────────┘
                           │
              ┌────────────┴───────────────┐
              │                             │
              ▼                             ▼
    ┌──────────────────┐         ┌──────────────────┐
    │  Worker EC2 #1   │  ...    │  Worker EC2 #N   │
    │                  │         │                  │
    │  ┌────────────┐  │         │  ┌────────────┐  │
    │  │ Agent 2    │  │         │  │ Agent 2    │  │
    │  │ MedGemma   │  │         │  │ MedGemma   │  │
    │  │ (Ollama)   │  │         │  │ (Ollama)   │  │
    │  └────────────┘  │         │  └────────────┘  │
    │                  │         │                  │
    │  ┌────────────┐  │         │  ┌────────────┐  │
    │  │ Binary     │  │         │  │ Binary     │  │
    │  │ File Agent │  │         │  │ File Agent │  │
    │  └────────────┘  │         │  └────────────┘  │
    └──────────────────┘         └──────────────────┘
              │                             │
              └────────────┬───────────────┘
                           ▼
                 ┌─────────────────────┐
                 │  RDS PostgreSQL     │
                 │  • Timeline         │
                 │  • Document Cache   │
                 │  • Workflow Metadata│
                 └─────────────────────┘
```

---

## Code Modifications

### 1. Database Migration (DuckDB → PostgreSQL)

**Timeline Database:**

```python
# OLD: utils/timeline_database.py (DuckDB)
import duckdb
conn = duckdb.connect('data/timeline.duckdb')

# NEW: utils/timeline_database.py (PostgreSQL)
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

class TimelineDatabase:
    def __init__(self, connection_string):
        self.pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            dsn=connection_string
        )

    def get_connection(self):
        return self.pool.getconn()

    def release_connection(self, conn):
        self.pool.putconn(conn)
```

**Document Text Cache:**

```python
# OLD: utils/document_text_cache.py (DuckDB)
self.conn = duckdb.connect(db_path)

# NEW: utils/document_text_cache.py (PostgreSQL)
class DocumentTextCache:
    def __init__(self, connection_string):
        self.conn_string = connection_string
        self._ensure_schema()

    def cache_document(self, doc: CachedDocument):
        with psycopg2.connect(self.conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO document_cache.extracted_document_text
                    VALUES (%s, %s, %s, ...)
                    ON CONFLICT (document_id) DO UPDATE SET ...
                """, (doc.document_id, doc.extracted_text, ...))
                conn.commit()
```

**Migration Steps:**
1. Create PostgreSQL schema migration script
2. Export existing DuckDB data to CSV
3. Import CSV to PostgreSQL
4. Update all database connection code
5. Test with single patient
6. Deploy

### 2. Batch Processing Controller

**New File:** `scripts/batch_orchestrator.py`

```python
"""
Batch Orchestrator for Production Multi-Patient Extraction

Responsibilities:
- Read patient cohort from S3 or database
- Send patient IDs to SQS queue
- Monitor extraction progress
- Handle failures and retries
- Generate batch summary reports
"""

import boto3
import json
from typing import List, Dict
from datetime import datetime
from pathlib import Path

class BatchOrchestrator:
    def __init__(
        self,
        queue_url: str,
        s3_bucket: str,
        max_concurrent: int = 10,
        enable_monitoring: bool = True
    ):
        self.sqs = boto3.client('sqs')
        self.s3 = boto3.client('s3')
        self.queue_url = queue_url
        self.s3_bucket = s3_bucket
        self.max_concurrent = max_concurrent

    def submit_batch(self, patient_ids: List[str], batch_name: str):
        """Submit batch of patients to extraction queue"""
        batch_id = f"{batch_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Send messages to SQS in batches of 10
        for i in range(0, len(patient_ids), 10):
            batch = patient_ids[i:i+10]
            entries = [
                {
                    'Id': str(j),
                    'MessageBody': json.dumps({
                        'patient_id': patient_id,
                        'batch_id': batch_id,
                        'submitted_at': datetime.now().isoformat()
                    })
                }
                for j, patient_id in enumerate(batch)
            ]
            self.sqs.send_message_batch(
                QueueUrl=self.queue_url,
                Entries=entries
            )

        print(f"✅ Submitted {len(patient_ids)} patients to queue")
        print(f"📊 Batch ID: {batch_id}")
        return batch_id

    def monitor_batch(self, batch_id: str):
        """Monitor batch extraction progress"""
        # Query PostgreSQL for batch status
        # Return metrics: completed, failed, in_progress
        pass

    def get_failed_patients(self, batch_id: str) -> List[str]:
        """Retrieve list of failed patient IDs for reprocessing"""
        # Query DLQ for failed messages
        pass
```

### 3. Worker Process

**New File:** `scripts/extraction_worker.py`

```python
"""
Extraction Worker - Processes patients from SQS queue

Runs on each worker EC2 instance. Polls SQS queue, processes patients,
reports results to PostgreSQL.
"""

import boto3
import json
from scripts.run_full_multi_source_abstraction import run_extraction

class ExtractionWorker:
    def __init__(self, queue_url: str, visibility_timeout: int = 7200):
        self.sqs = boto3.client('sqs')
        self.queue_url = queue_url
        self.visibility_timeout = visibility_timeout

    def poll_and_process(self):
        """Poll SQS queue and process patients"""
        while True:
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                VisibilityTimeout=self.visibility_timeout,
                WaitTimeSeconds=20  # Long polling
            )

            if 'Messages' not in response:
                continue

            for message in response['Messages']:
                try:
                    body = json.loads(message['Body'])
                    patient_id = body['patient_id']
                    batch_id = body['batch_id']

                    # Process patient
                    result = run_extraction(
                        patient_id=patient_id,
                        batch_id=batch_id
                    )

                    # Delete message from queue on success
                    self.sqs.delete_message(
                        QueueUrl=self.queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )

                    print(f"✅ Completed {patient_id}")

                except Exception as e:
                    print(f"❌ Failed {patient_id}: {e}")
                    # Message visibility timeout expires, returns to queue
                    # After 3 failed attempts, moves to DLQ

if __name__ == "__main__":
    worker = ExtractionWorker(queue_url=os.environ['QUEUE_URL'])
    worker.poll_and_process()
```

### 4. Retry Logic & Distributed Locking

**Add to workflow script:**

```python
import redis
from contextlib import contextmanager

class DistributedLock:
    def __init__(self, redis_client, key, timeout=7200):
        self.redis = redis_client
        self.key = key
        self.timeout = timeout

    @contextmanager
    def acquire(self):
        """Acquire distributed lock to prevent duplicate processing"""
        lock_acquired = self.redis.set(
            self.key,
            "locked",
            nx=True,  # Only set if not exists
            ex=self.timeout  # Expire after timeout
        )

        if not lock_acquired:
            raise Exception(f"Patient {self.key} is already being processed")

        try:
            yield
        finally:
            self.redis.delete(self.key)

# Usage in workflow:
redis_client = redis.Redis(host='redis-cluster', port=6379)
lock = DistributedLock(redis_client, f"patient:{patient_id}")

with lock.acquire():
    # Run extraction
    run_full_multi_source_abstraction(patient_id)
```

### 5. Monitoring Integration

**Add CloudWatch metrics:**

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def publish_metric(metric_name: str, value: float, unit: str = 'Count'):
    """Publish custom metric to CloudWatch"""
    cloudwatch.put_metric_data(
        Namespace='RadiantExtraction',
        MetricData=[
            {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.now()
            }
        ]
    )

# In workflow:
publish_metric('PatientsProcessed', 1)
publish_metric('ExtractionDuration', duration_seconds, 'Seconds')
publish_metric('CacheHitRate', cache_hits / total_docs, 'Percent')
```

---

## Deployment Phases

### Phase 1: Infrastructure Setup (2 weeks)

**Week 1:**
- [ ] Create AWS account/VPC setup (if not exists)
- [ ] Set up RDS PostgreSQL instance
- [ ] Create S3 buckets with lifecycle policies
- [ ] Set up SQS queues (main + DLQ)
- [ ] Configure CloudWatch logging
- [ ] Set up IAM roles and security groups

**Week 2:**
- [ ] Launch master orchestrator EC2 instance
- [ ] Create MedGemma worker AMI (with Ollama + gemma2:27b)
- [ ] Set up auto-scaling group for workers
- [ ] Configure load balancer
- [ ] Set up Redis cluster (for distributed locking)
- [ ] Deploy Grafana dashboard

**Deliverables:**
- Infrastructure-as-Code (Terraform/CloudFormation)
- Network diagram
- Security audit report

### Phase 2: Database Migration (1 week)

- [ ] Create PostgreSQL schema migration scripts
- [ ] Export existing DuckDB data
- [ ] Import to PostgreSQL
- [ ] Update all database connection code
- [ ] Test single-patient extraction with PostgreSQL
- [ ] Performance benchmark (compare DuckDB vs PostgreSQL)

**Deliverables:**
- Migration scripts
- Rollback procedure
- Performance comparison report

### Phase 3: Batch Processing Development (2 weeks)

**Week 1:**
- [ ] Implement `BatchOrchestrator` class
- [ ] Implement `ExtractionWorker` class
- [ ] Add distributed locking
- [ ] Add retry logic (exponential backoff)
- [ ] Add DLQ handling

**Week 2:**
- [ ] Integrate CloudWatch metrics
- [ ] Add notification system (Slack/email)
- [ ] Implement batch status dashboard
- [ ] Add cost tracking per patient
- [ ] Write unit tests

**Deliverables:**
- Batch orchestration code
- Worker deployment scripts
- Unit test suite

### Phase 4: Testing (2 weeks)

**Week 1: Functional Testing**
- [ ] Single patient extraction (end-to-end)
- [ ] 10-patient batch
- [ ] 100-patient batch
- [ ] Failure scenarios (simulate Athena timeout, S3 error, etc.)
- [ ] Retry logic verification
- [ ] DLQ handling

**Week 2: Performance & Load Testing**
- [ ] Benchmark extraction time per patient
- [ ] Load test: 1000 patients
- [ ] Cache hit rate analysis
- [ ] Cost per patient analysis
- [ ] Auto-scaling verification

**Deliverables:**
- Test report with metrics
- Performance benchmarks
- Cost analysis

### Phase 5: Pilot Deployment (2 weeks)

**Week 1:**
- [ ] Deploy to production environment
- [ ] Run pilot cohort (50 patients)
- [ ] Monitor for 1 week
- [ ] QA review of extractions
- [ ] Fix any issues

**Week 2:**
- [ ] Run larger cohort (200 patients)
- [ ] Validate data quality
- [ ] Compare with manual abstractions (if available)
- [ ] Collect stakeholder feedback
- [ ] Final adjustments

**Deliverables:**
- Pilot report
- Data quality metrics
- Stakeholder sign-off

### Phase 6: Full Production Rollout (Ongoing)

- [ ] Process full patient cohort (1000+ patients)
- [ ] Establish SLA monitoring
- [ ] Set up on-call rotation
- [ ] Create runbooks for common issues
- [ ] Ongoing optimization

---

## Testing Strategy

### Unit Tests

**Coverage Target:** 80%+

**Key Areas:**
- Document text caching (cache hit/miss, deduplication)
- Progress note prioritization (edge cases)
- Workflow orchestration (phase transitions)
- Database operations (CRUD, transactions)
- Binary file extraction (PDF, HTML, error handling)

**Tool:** `pytest`

### Integration Tests

**Scenarios:**
1. Full single-patient extraction (all phases)
2. Multi-patient batch (10 patients)
3. Cache reuse (run same patient twice, verify cache hit)
4. Failure recovery (simulate S3 error, verify retry)
5. DLQ handling (3 failed attempts → DLQ)

**Tool:** `pytest` with `moto` (AWS mocking)

### Load Tests

**Scenarios:**
1. 100 concurrent patients
2. 1000-patient batch
3. Worker auto-scaling under load

**Metrics:**
- Throughput (patients/hour)
- P50, P95, P99 extraction duration
- Cache hit rate
- Error rate
- Cost per patient

**Tool:** `locust` or custom load generator

### Data Quality Tests

**Validation Rules:**
1. All required fields populated
2. Confidence scores > threshold (0.7)
3. Temporal consistency (dates logical)
4. EOR matches operative report (if available)
5. No duplicate extractions for same patient+timestamp

**Tool:** Custom validation scripts

---

## Monitoring & Alerting

### Key Metrics

**Throughput:**
- Patients processed per hour
- Queue depth over time
- Worker utilization

**Performance:**
- P50/P95/P99 extraction duration
- Cache hit rate
- Database query latency

**Quality:**
- Extraction success rate
- Low-confidence extraction rate
- Temporal inconsistency detection rate

**Cost:**
- Athena query cost per patient
- S3 request cost
- EC2 compute cost
- Total cost per patient

### Alerts

**Critical (PagerDuty):**
- Extraction failure rate > 10%
- Queue depth > 5000 (backlog building up)
- Worker auto-scaling failed
- Database connection pool exhausted

**Warning (Slack):**
- Cache hit rate < 60%
- Average extraction time > 15 minutes
- Cost per patient > $2
- Low-confidence extractions > 20%

**Info (Email):**
- Batch completed
- Daily summary report

### Dashboard (Grafana)

**Panels:**
1. Real-time extraction progress (patients completed vs total)
2. Queue depth over time
3. Worker count and utilization
4. Extraction duration histogram
5. Cache hit rate
6. Cost tracking (cumulative)
7. Error rate by type

---

## Cost Estimation

### Current (Local Test - Single Patient)

| Component | Cost | Notes |
|-----------|------|-------|
| Athena queries | $0.50 | ~100 MB scanned per patient |
| S3 GET requests | $0.10 | ~200 binary fetches |
| Claude API (Agent 1) | $1.00 | ~500K tokens |
| MedGemma (Agent 2) | $0.00 | Local Ollama (free) |
| **TOTAL** | **$1.60** | Per patient |

### Production (AWS - 1000 Patients/Month)

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| **Compute** |  |  |
| Master orchestrator (t3.xlarge) | $120 | 24/7 |
| MedGemma workers (g5.2xlarge × 5 avg) | $1,500 | $1.21/hr × 5 instances × 248 hrs |
| **Storage** |  |  |
| RDS PostgreSQL (db.r6g.xlarge) | $290 | Multi-AZ |
| S3 (extractions + cache) | $50 | 1 TB storage |
| **Data Transfer** |  |  |
| Athena queries (1000 patients) | $500 | 100 MB per patient |
| S3 GET requests | $100 | 200 requests per patient |
| **APIs** |  |  |
| Claude API (Agent 1) | $1,000 | $1/patient |
| **Monitoring** |  |  |
| CloudWatch | $30 | Logs, metrics |
| Grafana Cloud | $50 | Dashboard |
| **TOTAL** | **$3,640** | **$3.64 per patient** |

### Cost Optimization Opportunities

1. **Spot Instances for Workers:** 70% cost reduction → Save $1,050/month
2. **Reserved Instances:** 40% discount on RDS → Save $116/month
3. **S3 Intelligent Tiering:** Auto-archive old extractions → Save $20/month
4. **Increase Cache Hit Rate:** 80% → 95% → Save $100/month in redundant processing

**Optimized Monthly Cost:** ~$2,350 ($2.35/patient)

---

## Timeline & Milestones

### Target: 9 Weeks to Production

| Phase | Duration | Start Date | End Date | Key Deliverables |
|-------|----------|------------|----------|------------------|
| **Phase 1: Infrastructure** | 2 weeks | Week 1 | Week 2 | AWS infrastructure operational |
| **Phase 2: DB Migration** | 1 week | Week 3 | Week 3 | PostgreSQL deployed |
| **Phase 3: Batch Processing** | 2 weeks | Week 4 | Week 5 | Batch orchestration code complete |
| **Phase 4: Testing** | 2 weeks | Week 6 | Week 7 | Test report, benchmarks |
| **Phase 5: Pilot** | 2 weeks | Week 8 | Week 9 | 200-patient pilot successful |
| **Phase 6: Production** | Ongoing | Week 10+ | - | Full cohort processing |

### Go/No-Go Decision Points

**After Phase 2 (Week 3):**
- ✅ PostgreSQL migration successful
- ✅ Single-patient extraction working with PostgreSQL
- ✅ Performance acceptable (< 15 min per patient)

**After Phase 4 (Week 7):**
- ✅ 100-patient batch completes successfully
- ✅ Error rate < 5%
- ✅ Cost per patient < $4
- ✅ Cache hit rate > 70%

**After Phase 5 (Week 9):**
- ✅ 200-patient pilot completes successfully
- ✅ QA review passes
- ✅ Stakeholder approval
- ✅ SLAs defined and achievable

---

## Risk Assessment

### High-Risk Items

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| MedGemma scaling issues | High | Medium | Load test early; consider alternative (AWS SageMaker endpoint) |
| PostgreSQL migration data loss | Critical | Low | Extensive testing, backup strategy, rollback plan |
| Cost overruns (Athena) | High | Medium | Implement cost limits, optimize queries, caching |
| Claude API rate limits | High | Low | Implement rate limiting, request batching |
| Data quality degradation | High | Medium | Extensive QA, confidence thresholds, human review |

### Medium-Risk Items

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Worker auto-scaling delays | Medium | Medium | Pre-warm instances, adjust scaling policies |
| Cache invalidation issues | Medium | Low | Versioning, SHA256 hashing, manual invalidation tool |
| Temporal inconsistency false positives | Medium | Medium | Tune thresholds, human review queue |
| Batch job monitoring gaps | Low | Medium | Comprehensive CloudWatch metrics, dashboard |

---

## Rollback Plan

### Scenario 1: PostgreSQL Migration Fails

**Symptoms:** Data corruption, unacceptable performance, connection issues

**Rollback Steps:**
1. Stop all workers
2. Restore DuckDB databases from backup
3. Revert code to pre-migration version (Git tag: `v1.2.0`)
4. Resume single-patient processing with DuckDB
5. Post-mortem to identify root cause

**Recovery Time:** 1 hour

### Scenario 2: Production Batch Processing Issues

**Symptoms:** High error rate, unacceptable cost, data quality issues

**Rollback Steps:**
1. Pause batch orchestrator (stop sending to queue)
2. Drain existing queue
3. Review errors in CloudWatch/Grafana
4. Fix issues in staging environment
5. Re-test with small cohort
6. Resume production

**Recovery Time:** 1-2 days

### Scenario 3: Critical AWS Service Outage

**Symptoms:** Athena unavailable, S3 errors, RDS down

**Actions:**
1. Monitor AWS status page
2. Implement exponential backoff retries
3. Workers automatically pause on repeated failures
4. Resume when service restored
5. No data loss (SQS queue persists)

**Recovery Time:** Depends on AWS

---

## Next Steps

### Immediate Actions (This Week)

1. [ ] Review and approve this roadmap
2. [ ] Secure AWS budget approval ($3,640/month)
3. [ ] Assign team members to phases
4. [ ] Set up project tracking (Jira/GitHub Projects)
5. [ ] Schedule kickoff meeting

### Phase 1 Preparation (Next Week)

1. [ ] Provision AWS account access for team
2. [ ] Create Terraform/CloudFormation templates
3. [ ] Set up development environment
4. [ ] Create RDS PostgreSQL schema design
5. [ ] Draft migration scripts

### Questions to Resolve

1. **Cohort Definition:** How do we define patient cohorts? (SQL query, CSV upload, UI?)
2. **QA Workflow:** Who reviews low-confidence extractions? What's the SLA?
3. **Data Retention:** How long do we keep extractions? (1 year, 5 years, indefinitely?)
4. **Access Control:** Who has access to production system? (Roles: admin, analyst, viewer?)
5. **Compliance:** Do we need HIPAA BAA with AWS? PHI handling policies?

---

## Appendix

### A. Alternative Architectures Considered

**Option 1: AWS Step Functions (Serverless)**
- **Pros:** Fully managed, auto-scaling, pay-per-use
- **Cons:** Limited execution time (1 hour max), cold starts, harder to debug
- **Decision:** Rejected due to extraction duration uncertainty

**Option 2: Kubernetes (EKS)**
- **Pros:** Better orchestration, easier scaling, portable
- **Cons:** Higher complexity, operational overhead, learning curve
- **Decision:** Deferred to v2.1 after validating EC2 approach

**Option 3: AWS Batch**
- **Pros:** Designed for batch workloads, auto-scaling
- **Cons:** Less flexible than raw EC2, GPU support limitations
- **Decision:** Consider for future if EC2 management becomes burdensome

### B. Technology Stack Summary

| Component | Technology | Justification |
|-----------|-----------|---------------|
| Orchestrator | Python 3.12 | Existing codebase |
| Agent 1 | Claude Sonnet 4.5 API | Best-in-class reasoning |
| Agent 2 | MedGemma 27B (Ollama) | Medical domain expertise, local control |
| Database | PostgreSQL (RDS) | Production-grade, concurrent writes |
| Queue | AWS SQS | Reliable, scalable, managed |
| Compute | EC2 (g5.2xlarge for GPU) | Cost-effective, GPU support |
| Storage | S3 | Durable, scalable, lifecycle policies |
| Monitoring | CloudWatch + Grafana | AWS native + rich dashboards |
| Logging | CloudWatch Logs | Centralized, searchable |
| Orchestration | Custom Python | Flexibility, full control |

### C. Glossary

- **Agent 1:** Claude-powered master orchestrator
- **Agent 2:** MedGemma-powered medical text extractor
- **Batch:** Group of patients processed together
- **Cohort:** Set of patients meeting specific criteria
- **DLQ:** Dead Letter Queue (failed jobs)
- **EOR:** Extent of Resection
- **PHI:** Protected Health Information
- **QA:** Quality Assurance
- **SLA:** Service Level Agreement

---

**Document Version:** 1.0
**Last Updated:** 2025-10-20
**Author:** Claude (Agent 1) with guidance from Adam Cresnick, MD
**Status:** Draft - Awaiting Review
