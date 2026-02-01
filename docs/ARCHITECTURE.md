# Architecture - System Design & Decisions

**Version:** 2.0 (Fresh)  
**Last Updated:** 2026-02-01  
**Purpose:** Explain design decisions and system architecture  
**Audience:** Engineers, architects, operators

---

## Table of Contents

1. **[System Overview](#system-overview)** - High-level architecture
2. **[Core Principles](#core-principles)** - Design philosophy
3. **[Component Architecture](#component-architecture)** - Each major system
4. **[Argo CD Structure](#argo-cd-structure)** - GitOps organization
5. **[Namespace Design](#namespace-design)** - Isolation and quotas
6. **[Secret Management](#secret-management)** - Vault integration
7. **[Observability Stack](#observability-stack)** - Prometheus/Grafana/Alertmanager
8. **[Data Flow](#data-flow)** - How data moves through system
9. **[Disaster Recovery](#disaster-recovery)** - Recovery capabilities
10. **[Trade-offs](#trade-offs)** - Why we chose this way

---

## System Overview

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      KUBERNETES CLUSTER (K3s)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              ARGO CD (GitOps Controller)                   │  │
│  │  - Watches Git repository for changes                      │  │
│  │  - Reconciles cluster state with Git                       │  │
│  │  - Never runs manually, always source = Git                │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────┬──────────────────┬──────────────────┐       │
│  │ OBSERVABILITY  │ SECURITY         │ WORKLOADS        │       │
│  │ (6Gi quota)    │ (1.5Gi quota)    │ (4Gi quota)      │       │
│  │                │                  │                  │       │
│  │ Prometheus     │ Vault            │ User apps        │       │
│  │ Grafana        │ External Secrets │                  │       │
│  │ Alertmanager   │                  │ (future)         │       │
│  │                │                  │                  │       │
│  └────────────────┴──────────────────┴──────────────────┘       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────────┐
                    │  VAULT (Secrets)    │
                    │                     │
                    │ kv/alerting/discord │
                    │ (webhook URL)       │
                    └─────────────────────┘
                              ↓
                    ┌─────────────────────┐
                    │ DISCORD CHANNEL     │
                    │ (Alert Notifications)
                    └─────────────────────┘
```

### Key Facts

- **Single source of truth:** Git repository
- **Deployment trigger:** Push to main branch
- **Recovery mechanism:** Git + Vault backups
- **Automation level:** Fully declarative (no manual edits)
- **Safety first:** Argo CD configured to never delete resources

---

## Core Principles

### 1. Git as Source of Truth

```
Real World State ←→ Git Repository ←→ Developers
       ↓                              ↓
   Kubernetes              Edit YAML files
   Cluster                 Push to main
                           Argo syncs
```

**Why?**
- All changes are auditable (git history)
- Easy rollback (git revert)
- Reproducible deployments
- Team awareness (PR reviews)
- No "I don't know who changed that"

**Implementation:**
```bash
# Change infrastructure
vim infrastructure/observability/prometheus/values.yaml

# Push to Git
git add -A && git commit -m "reason" && git push origin main

# Argo CD automatically deploys within 3 minutes
```

### 2. Argo CD for Orchestration

```
Argo CD (Running in cluster) 
  ↓
Watches Git repository
  ↓
Detects changes
  ↓
Syncs to Kubernetes
  ↓
Cluster state = Git state
```

**Why not Helm directly?**
- Helm is imperative ("do this")
- Argo CD is declarative ("this is the state")
- Argo knows when drift occurs
- Can sync automatically
- Can show diffs before applying
- Supports rollback via Git

**Safety Features:**
- `prune: false` - Never deletes resources
- `selfHeal: true` - Auto-fixes drift
- Explicit sync policies per project
- Namespace boundaries enforced

### 3. Vault for Secrets

```
Vault (Initialized, Raft backend)
  ↓
Stores: kv/alerting/discord (webhook URL)
  ↓
ExternalSecrets Operator (watches Vault)
  ↓
Creates: alertmanager-discord-secret (Kubernetes Secret)
  ↓
Alertmanager uses secret
  ↓
Discord webhook routing works
```

**Why not store secrets in Git?**
- Never commit sensitive data
- Vault is encrypted at rest
- Audit trail of secret access
- Easy rotation (update once, sync everywhere)
- Compliance requirement

**Current Secrets:**
- `kv/alerting/discord` - Discord webhook URL
- (More can be added as platform grows)

### 4. Namespace Isolation

```
Three isolated namespaces, each with:
- ResourceQuota (max memory/CPU)
- LimitRange (per-pod defaults)
- Network policies (future)
- RBAC (future multi-team)

observability (6Gi)  → Prometheus, Grafana, Alertmanager
    ↓
security (1.5Gi)     → Vault, ExternalSecrets
    ↓
workloads (4Gi)      → User applications
```

**Why this split?**
- **Observability:** High memory (Prometheus retention)
- **Security:** Medium memory (Vault, ExternalSecrets)
- **Workloads:** Growing capacity (user apps)

**Total:** 11.5Gi used, cluster has 10Gi = Safe headroom

### 5. Declarative Over Imperative

```
❌ IMPERATIVE (Don't do this)
  - kubectl edit pod
  - kubectl scale deployment --replicas=3
  - Manual operator changes
  - Scripts that change state

✅ DECLARATIVE (Do this)
  - Edit YAML in Git
  - Push to main
  - Argo applies it
  - Git history = audit trail
```

---

## Component Architecture

### Argo CD

```
Purpose: GitOps automation engine
Location: argocd namespace (bootstrap-only)

Structure:
├── Argo Server (UI + API)
├── Argo Controller (reconciliation)
└── Repo Server (Git watcher)

Not managed by Argo CD itself:
- Manual kubectl apply (bootstrap only)
- Never self-managing (prevents loops)
```

### Prometheus

```
Purpose: Metrics collection and alerting
Location: observability namespace

Stack:
├── Prometheus StatefulSet (storage: 5Gi, memory: 2Gi)
├── Prometheus Operator (manages Prometheus CRD)
├── ServiceMonitors (define scrape targets)
└── PrometheusRules (define alert rules)

Data:
├── Scrapes targets every 30 seconds
├── Stores metrics in 5Gi volume
├── Retention: 15 days (configurable)
└── No metrics exported outside cluster (local only)

Alerts:
├── Defined in PrometheusRule CRDs (Git-managed)
├── Evaluated every 30 seconds
├── Sent to Alertmanager when condition met
└── Example: "Pod memory > 90% for 5 minutes"
```

### Grafana

```
Purpose: Visualization and dashboards
Location: observability namespace

Features:
├── Data source: Prometheus (auto-configured)
├── Dashboards: Provisioned from ConfigMaps
├── Users: Admin (Argo-deployed), others (future)
└── Alerts: Display only (not created here)

Admin Credentials:
- Username: admin
- Password: admin (set in Helm values)

Dashboards:
- Stored as JSON in Git
- Loaded via ConfigMaps
- Auto-refresh every 30s
- No UI-only changes (everything in Git)
```

### Alertmanager

```
Purpose: Alert routing and deduplication
Location: observability namespace

Flow:
1. Prometheus fires alert
2. Alertmanager deduplicates
3. Routes to receivers (Discord)
4. Sends via Discord webhook
5. Discord channel gets notification

Config:
├── Routing rules (match alerts)
├── Receivers (Discord webhook)
├── Grouping (batch related alerts)
└── Silencing (temporary quiet periods)

Status:
- StatefulSet (1 replica, 512Mi memory)
- Web UI at localhost:9093
- Webhook synced from Vault via ExternalSecrets
```

### Vault

```
Purpose: Secrets storage and management
Location: vault namespace

Backend:
├── Raft (integrated storage, 10Gi + 5Gi audit logs)
├── Initialized and unsealed
├── High-availability capable (no HA currently)
└── Backed up regularly

Secrets:
├── kv/ (versioned key-value)
│   └── alerting/
│       └── discord (webhook URL)
└── (More added as platform grows)

Auth:
- Kubernetes auth (mounted SA tokens)
- Accessible within cluster
- Access logged in audit trail
```

### External Secrets Operator

```
Purpose: Sync secrets from Vault to Kubernetes
Location: external-secrets namespace

Flow:
Vault Secret
    ↓
ExternalSecret CRD (Git-managed)
    ↓
SecretStore (auth config)
    ↓
Kubernetes Secret
    ↓
Application mounts/uses

Example:
ExternalSecret: alertmanager-discord
  ↓
References: kv/alerting/discord (Vault)
  ↓
Creates: alertmanager-discord-secret (K8s)
  ↓
Syncs: Every 1 hour (or on-demand)
```

---

## Argo CD Structure

### Projects (Organization Layer)

```
┌─────────────────────────────┐
│  Argo CD                    │
├─────────────────────────────┤
│                             │
│  platform-observability     │ → observability namespace
│  platform-security          │ → security namespace
│  workloads                   │ → workloads namespace
│                             │
└─────────────────────────────┘
```

Each project has:
- **Source Repos:** Which Git repos allowed
- **Destinations:** Which namespaces allowed
- **Resources:** Which Kubernetes kinds allowed
- **Roles:** RBAC rules (future: per team)

### Applications (Deployment Layer)

```
root-app (App-of-Apps pattern)
├── observability-stack
│   ├── prometheus
│   ├── grafana
│   └── alertmanager
├── vault
└── external-secrets
```

Benefits of App-of-Apps:
- Single point of control (root-app.yaml)
- Auto-discovers sub-applications
- Syncs in proper order (dependencies)
- Easy to see full platform state
- One command deploys everything

### Sync Policies

```
Current Configuration:
├── automated: true (auto-sync when Git changes)
├── prune: false (never delete resources)
└── selfHeal: true (auto-fix if drifts)

Why prune: false?
- Safety first for production systems
- Prevents accidental mass deletes
- Manual deletion requires explicit action
- Can be enabled per-app if safe

Why selfHeal: true?
- Detect and fix configuration drift
- Someone kubectl edit? → Argo fixes it
- Config corrupted? → Argo restores from Git
- Ensures Git always wins
```

---

## Namespace Design

### observability Namespace

```
Resources:
├── Prometheus StatefulSet (5Gi storage, 2Gi memory)
├── Alertmanager StatefulSet (512Mi memory)
├── Grafana Deployment (512Mi memory)
├── Prometheus Operator Deployment
└── Support services

Quota: 6Gi memory, 3 CPU cores
Typical Usage: 4-5Gi (75-80%)

Why this size?
- Prometheus: 5Gi storage + 2Gi memory
- Grafana: 512Mi
- Alertmanager: 512Mi
- Operator: 256Mi
- Total comfortable: ~6Gi
```

### security Namespace

```
Resources:
├── Vault StatefulSet (Raft storage 10Gi + 5Gi audit)
├── ExternalSecrets Operator Deployment
├── ExternalSecrets resources (ExternalSecret, SecretStore)
└── Support services

Quota: 1.5Gi memory, 1 CPU core
Typical Usage: 800Mi (50%)

Why this size?
- Vault: 512Mi
- ExternalSecrets: 256Mi
- Support: 256Mi
- Total comfortable: ~1.5Gi
```

### workloads Namespace

```
Resources:
├── User applications (future)
├── Ingress (future)
├── Services (future)
└── Support services

Quota: 4Gi memory, 2 CPU cores
Typical Usage: 0Gi (empty, ready for growth)

Why this size?
- Reserve for growing applications
- Doubled from observability to allow scaling
- No resource contention with platform
```

### argocd Namespace

```
Resources:
├── Argo CD Server
├── Argo CD Controller
├── Argo Repo Server
└── Support services

Status: Bootstrap-only (not managed by Argo CD)
Quota: Unlimited (not in Git-managed loop)
```

---

## Secret Management

### Current Flow

```
Step 1: Initialize Vault (once)
├── Create raft storage
├── Initialize secret engine
└── Unseal (3/5 keys required)

Step 2: Store Secret
├── kubectl exec vault-0 -- vault kv put kv/alerting/discord webhook_url="https://..."
└── Secret stored in Raft encrypted

Step 3: ExternalSecrets Watches
├── ExternalSecret CR exists in Git
├── References: kv/alerting/discord
├── Polls Vault every hour (or on-demand)
└── Creates/updates Kubernetes Secret

Step 4: Application Uses
├── Alertmanager mounts alertmanager-discord-secret
├── Extracts webhook_url
├── Sends alerts to Discord
└── All via webhook URL from Vault
```

### Secret Rotation

```
Old webhook URL expires:
├── Get new Discord webhook URL
├── Update Vault: vault kv put kv/alerting/discord webhook_url="new..."
├── Force sync: kubectl patch externalsecret ... 
├── Wait 30 seconds
├── Alertmanager automatically uses new URL

Zero downtime because:
- Kubernetes Secret updated
- Alertmanager reloads config automatically
- No application restart needed
```

### Adding New Secrets

When you need a new secret:

```bash
# 1. Store in Vault
kubectl exec -n vault vault-0 -- \
  vault kv put kv/myapp/api-key \
  token="secret-value"

# 2. Create ExternalSecret in Git
cat > infrastructure/security/external-secrets/myapp.yaml <<'EOF'
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: myapp-secret
  namespace: workloads
spec:
  secretStoreRef:
    name: vault
    kind: SecretStore
  target:
    name: myapp-secret
  data:
    - secretKey: API_TOKEN
      remoteRef:
        key: myapp/api-key
        property: token
EOF

# 3. Commit and push
git add infrastructure/security/external-secrets/myapp.yaml
git commit -m "Add myapp API key secret"
git push origin main

# 4. Argo applies ExternalSecret
# 5. Kubernetes Secret created
# 6. App mounts and uses it
```

---

## Observability Stack

### Data Flow

```
┌──────────────────┐
│  Scrape Targets  │ (kubelet, node-exporter, etc.)
│  (every 30s)     │
└────────┬─────────┘
         │
┌────────▼────────────────────┐
│  Prometheus                 │
│  - Scrapes metrics          │
│  - Evaluates alert rules    │
│  - Stores in TSDB (5Gi)     │
│  - Retention: 15 days       │
└────────┬────────────────────┘
         │
    ┌────┴───────────┬────────────────┐
    │                │                │
┌───▼────┐  ┌───────▼────┐  ┌────────▼──────┐
│Grafana │  │Alertmanager│  │Query API      │
│(Graph) │  │(Route)     │  │(Dashboards)   │
└────────┘  │            │  └───────────────┘
            │Discord     │
            │Webhook     │
            └───────┬────┘
                    │
            ┌───────▼──────────┐
            │  Discord Channel │
            │  (Notifications) │
            └──────────────────┘
```

### Alert Rule Evaluation

```
Every 30 seconds:
┌────────────────────────────┐
│ Prometheus evaluates rules │
└────────┬───────────────────┘
         │
    Has condition been true for "for" duration?
         │
         ├─ NO  → Wait, check again in 30s
         │
         └─ YES → Fire alert
              │
              ├─ Create alert object
              ├─ Send to Alertmanager
              └─ Alertmanager routes to Discord
```

### Example: Pod Memory Alert

```yaml
# Rule definition (Git-managed)
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: pod-memory
  namespace: observability
spec:
  groups:
  - name: pod
    interval: 30s
    rules:
    - alert: PodHighMemory
      expr: memory_usage / memory_limit > 0.9
      for: 5m  # Must be true for 5 minutes
      annotations:
        summary: "Pod memory at {{ $value | humanizePercentage }}"
```

Execution:

```
T=0:00   → metric = 85% (no alert)
T=0:30   → metric = 92% (true, but only 30s)
T=1:00   → metric = 95% (true, now 1m)
T=2:00   → metric = 94% (true, now 2m)
T=3:00   → metric = 96% (true, now 3m)
T=4:00   → metric = 97% (true, now 4m)
T=4:30   → metric = 98% (true, now 4m 30s)
T=5:00   → metric = 99% (true, now 5m ← ALERT FIRES!)
           └─ Send to Alertmanager
           └─ Alertmanager routes to Discord
           └─ Discord message: "Pod memory at 99%"

T=5:30   → metric = 85% (false, alert clears)
           └─ Send "resolved" to Alertmanager
           └─ Discord shows "resolved"
```

---

## Data Flow

### Configuration Change Flow

```
Developer
└─ git add infrastructure/observability/prometheus/values.yaml
└─ git commit -m "Increase retention"
└─ git push origin main
   │
   └─→ GitHub receives push
       │
       └─→ Argo CD webhook triggered (optional)
           OR polls Git every 3 minutes
           │
           └─→ Argo detects changes
               │
               └─→ Compares Git vs cluster
                   │
                   └─→ Shows diff
                       │
                       └─→ Applies (if automated: true)
                           │
                           └─→ Helm renders values.yaml
                               │
                               └─→ Kubectl apply manifests
                                   │
                                   └─→ Kubernetes updates StatefulSet
                                       │
                                       └─→ Prometheus pod restarted
                                           │
                                           └─→ New config loaded
```

### Alert Flow

```
Application Event
└─ High memory usage detected
   │
   └─→ Prometheus scrapes metric
       │
       └─→ Metric stored in TSDB
           │
           └─→ Alert rule evaluated (every 30s)
               │
               └─→ Condition true for "for" duration
                   │
                   └─→ Alert object created
                       │
                       └─→ Sent to Alertmanager
                           │
                           └─→ Alertmanager deduplicates
                               │
                               └─→ Matches routing rules
                                   │
                                   └─→ Routes to Discord receiver
                                       │
                                       └─→ Sends webhook
                                           │
                                           └─→ Discord receives
                                               │
                                               └─→ Message appears in channel
```

---

## Disaster Recovery

### Recovery Capability

```
Full Cluster Down?
├─ K3s is gone
├─ Vault is gone
├─ Argo CD is gone
└─ Everything is gone

Recovery Time: ~15 minutes (fully automated)

Steps:
1. Bootstrap Argo CD (kubectl apply)
2. Create namespaces (kubectl apply)
3. Create Argo Projects (kubectl apply)
4. Deploy root app (kubectl apply)
   ├─ Argo auto-syncs everything from Git
   ├─ Prometheus deployed
   ├─ Grafana deployed
   ├─ Alertmanager deployed
   ├─ Vault initialized
   └─ ExternalSecrets deployed
5. Restore Vault (kubectl cp + vault restore)
6. ExternalSecrets re-syncs secrets
```

### Why This Works

**Everything is in Git:**
- Cluster configuration (namespaces, quotas)
- Applications (Prometheus, Grafana)
- Argo configuration (projects, apps)
- Secrets are NOT in Git, they're in Vault

**Vault is Backed Up:**
- Snapshot taken regularly
- Can restore from backup
- Secrets recovered without loss

**Argo Is Smart:**
- Knows what to deploy
- Knows the order (dependencies)
- Knows the desired state
- Auto-applies when bootstrap completes

---

## Trade-offs

### Chosen: Git as Source of Truth

**Pros:**
- All changes auditable ✓
- Easy rollback ✓
- Reproducible ✓
- Team-friendly ✓

**Cons:**
- Can't manually patch (only for testing) ✗
- Must commit even small changes ✗
- Requires discipline ✓

### Chosen: Argo CD prune: false

**Pros:**
- Safe, no accidental deletes ✓
- Production-appropriate ✓
- Prevents mistakes ✓

**Cons:**
- Manual cleanup sometimes needed ✗
- Drift not auto-fixed if prune true ✗

### Chosen: Single Cluster (No HA)

**Pros:**
- Simple to manage ✓
- Lower resource usage ✓
- Fits 16GB Mac ✓

**Cons:**
- Single point of failure ✗
- No live failover ✗

**Mitigation:**
- Regular backups
- Fast recovery (15 min)
- Acceptable for personal/team platform

### Chosen: 15-day Prometheus Retention

**Pros:**
- Fits 5Gi storage ✓
- Good for recent analysis ✓
- Configurable if needed ✓

**Cons:**
- No long-term trend data ✗

**If needed:**
- Extend retention: `vim infrastructure/observability/prometheus/values.yaml`
- Or add external storage (thanos, S3)

### Not Chosen: Vault HA

**Why not?**
- Single node sufficient for platform
- Raft backend supports future HA
- Complex to run on Mac

**If needed future:**
- Add Vault replicas
- Configure raft with multiple peers
- All via Git-managed configs

---

## Philosophy

### Why This Design?

This architecture reflects **production engineering principles** even for a personal/team platform:

1. **Reliability over convenience**
   - Declarative > imperative
   - GitOps > manual changes
   - Backups > hoping nothing breaks

2. **Auditability over secrecy**
   - All changes in Git
   - Secrets not in code
   - Access logged in Vault

3. **Repeatability over magic**
   - Disaster recovery documented and tested
   - No special knowledge required
   - Anyone can restore from scratch

4. **Future-proof over quick wins**
   - Argo Projects for multi-team
   - RBAC structure ready
   - Storage abstraction (easy to swap)

### Growth Path

```
Today (Personal Platform):
- Single owner
- Simple quotas
- No multi-tenancy

Tomorrow (Team Platform):
- Multiple owners
- Per-team RBAC
- Per-team quotas
- Per-team applications
  
(All possible without architecture changes)
```

---

## Summary

**This platform is:**
- ✅ Fully declarative (Git-driven)
- ✅ Automatically deployed (Argo CD)
- ✅ Securely configured (Vault)
- ✅ Highly observable (Prometheus/Grafana)
- ✅ Fast to recover (~15 min)
- ✅ Ready to scale (Argo Projects, RBAC)

**Key principle:**
"If you can't restore it from a git clone + a backup, it's not production-ready."

This platform can.

---

**Version:** 2.0 (Fresh Architecture)  
**Last Updated:** 2026-02-01  
**Status:** Production Design, No Legacy References
