# Architecture - System Design & Organization

**Version:** 2.1 (Restructured - Team-Based)  
**Last Updated:** 2026-02-01  
**Purpose:** Explain design decisions and system architecture  
**Audience:** Engineers, architects, operators

---

## Table of Contents

1. **[System Overview](#system-overview)** - High-level architecture
2. **[Argo Projects](#argo-projects)** - Team organization with RBAC
3. **[Directory Structure](#directory-structure)** - How code is organized
4. **[Application Hierarchy](#application-hierarchy)** - App-of-Apps pattern
5. **[Namespace Design](#namespace-design)** - Isolation and organization
6. **[Secret Management](#secret-management)** - Vault integration
7. **[Component Details](#component-details)** - Each major system
8. **[Data Flow](#data-flow)** - How information moves
9. **[GitOps Workflow](#gitops-workflow)** - How deployments work
10. **[Disaster Recovery](#disaster-recovery)** - Recovery architecture

---

## System Overview

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER (K3s)                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  PLATFORM-ROOT (GitOps Controller)                       │   │
│  │  - Root Argo Application                                 │   │
│  │  - Uses: platform-tools project                          │   │
│  │  - Watches: infrastructure/ directory                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│         │                                                         │
│         ├─→ platform-tools-app (platform-tools project)          │
│         │   ├─ Vault                                             │
│         │   ├─ External Secrets Operator                         │
│         │   └─ Argo CD (self-manages)                            │
│         │                                                         │
│         ├─→ observability-app (platform-observability project)   │
│         │   ├─ Prometheus (scrapes + evaluates rules)            │
│         │   ├─ Alertmanager (routes alerts)                      │
│         │   └─ Grafana (dashboards)                              │
│         │                                                         │
│         ├─→ security-app (platform-security project)             │
│         │   └─ RBAC + Network Policies                           │
│         │                                                         │
│         └─→ workloads-app (workloads project)                    │
│             └─ User applications (your apps)                     │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
         ↓
    GitHub (main branch)
    ↓
    infrastructure/ (source of truth)
```

### Key Architectural Decisions

| Decision | Why | Trade-off |
|----------|-----|-----------|
| **App-of-Apps pattern** | Modular, scalable | Slightly complex |
| **Team-based projects** | RBAC isolation | Need planning |
| **Git as truth** | Auditable, reproducible | Manual edits not allowed |
| **Namespace per function** | Clear separation | More namespaces |
| **Argo for self-manage** | No bootstrap needed | Circular dependency managed |

---

## Argo Projects

### Project Hierarchy

```
PROJECTS (Team/Function-Based)
├── platform-tools (Admin only)
│   ├── Namespaces: vault, vault-admin, external-secrets, argocd
│   ├── Purpose: Core infrastructure
│   ├── Repos: github.com/temitayocharles/platform-gitops.git
│   └── Resources: Helm charts for core components
│
├── platform-observability (DevOps Team)
│   ├── Namespaces: observability
│   ├── Purpose: Monitoring & visualization
│   ├── Repos: github.com/temitayocharles/platform-gitops.git
│   └── Resources: Prometheus, Alertmanager, Grafana
│
├── platform-security (Security Team)
│   ├── Namespaces: security
│   ├── Purpose: RBAC & policies
│   ├── Repos: github.com/temitayocharles/platform-gitops.git
│   └── Resources: Roles, RoleBindings, NetworkPolicies
│
└── workloads (Developers)
    ├── Namespaces: workloads, applications, services
    ├── Purpose: User applications
    ├── Repos: Any repos configured for workloads
    └── Resources: User applications only
```

### RBAC Enforcement

Each project is restricted by:
1. **Source repositories** - Which Git repos can be deployed
2. **Destination namespaces** - Which namespaces can be written to
3. **Resource types** - Which K8s resources can be deployed

**Example: workloads project**
```yaml
spec:
  sourceRepos:
  - 'https://github.com/...'  # Only user apps repo
  destinations:
  - namespace: 'workloads'    # Only this namespace
    server: https://kubernetes.default.svc
  clusterResourceWhitelist:
  - group: ''
    kind: Namespace           # Can create namespaces
```

---

## Directory Structure

### Organization Principle

**By Function + Team**, not by tool type:

```
BAD (tool-focused):
├── prometheus/
├── grafana/
├── alertmanager/
├── vault/
├── external-secrets/
└── argo-cd/

GOOD (function + team-focused):
├── platform/           (core - platform-tools project)
├── observability/      (monitoring - platform-observability project)
├── security/           (access - platform-security project)
└── workloads/          (apps - workloads project)
```

### Actual Structure

```
infrastructure/
│
├── argo-projects.yaml
│   └─ Defines all 4 projects with RBAC
│
├── platform-tools-app.yaml
│   └─ Orchestrates: platform/ directory
│
├── observability-app.yaml
│   └─ Orchestrates: observability/ directory
│
├── security-app.yaml
│   └─ Orchestrates: security/ directory
│
├── workloads-app.yaml
│   └─ Orchestrates: workloads/ directory
│
├── kustomization.yaml
│   └─ Root kustomization - includes all above
│
├── platform/
│   ├── kustomization.yaml
│   │   └─ Includes: vault/, external-secrets/, argo-cd/
│   │
│   ├── vault/
│   │   ├── kustomization.yaml
│   │   └── app.yaml (Argo Application for Vault)
│   │
│   ├── external-secrets/
│   │   ├── kustomization.yaml
│   │   ├── app.yaml (Argo Application for ESO)
│   │   └── secretstore.yaml (ClusterSecretStore pointing to Vault)
│   │
│   └── argo-cd/
│       ├── kustomization.yaml
│       └── app.yaml (Argo Application for Argo CD)
│
├── observability/
│   ├── kustomization.yaml
│   │   └─ Includes: prometheus/, alertmanager/, grafana/
│   │
│   ├── prometheus/
│   │   ├── kustomization.yaml
│   │   └── app.yaml (kube-prometheus-stack Helm chart)
│   │
│   ├── alertmanager/
│   │   ├── kustomization.yaml
│   │   └── alertmanager-config.yaml (Discord routing via ESO)
│   │
│   └── grafana/
│       └── kustomization.yaml
│           └─ Grafana deployed via kube-prometheus-stack
│
├── security/
│   ├── kustomization.yaml
│   │   └─ Includes: rbac/
│   │
│   └── rbac/
│       └── default-rbac.yaml (default ServiceAccount + Roles)
│
└── workloads/
    └── kustomization.yaml
        └─ Empty - for user applications
```

---

## Application Hierarchy (App-of-Apps)

### Deployment Flow

```
root-app.yaml (platform-root)
    ↓
infrastructure/kustomization.yaml
    ↓
    ├── argo-projects.yaml (creates projects)
    │
    ├── platform-tools-app.yaml
    │   ↓
    │   infrastructure/platform/kustomization.yaml
    │       ├── vault/app.yaml
    │       ├── external-secrets/app.yaml
    │       └── argo-cd/app.yaml
    │
    ├── observability-app.yaml
    │   ↓
    │   infrastructure/observability/kustomization.yaml
    │       ├── prometheus/app.yaml
    │       ├── alertmanager/alertmanager-config.yaml
    │       └── grafana/kustomization.yaml
    │
    ├── security-app.yaml
    │   ↓
    │   infrastructure/security/kustomization.yaml
    │       └── rbac/default-rbac.yaml
    │
    └── workloads-app.yaml
        ↓
        infrastructure/workloads/kustomization.yaml
            └── (user apps added here)
```

### Why App-of-Apps?

| Benefit | Example |
|---------|---------|
| **Modularity** | Each team controls their apps |
| **Scalability** | Easy to add new projects |
| **Isolation** | Failed app doesn't affect others |
| **Organization** | Clear directory structure |
| **RBAC** | Teams can't deploy to other namespaces |

---

## Namespace Design

### Namespace Organization

```
System Namespaces (core - platform-tools project)
├── vault              (Secrets storage + HA)
├── vault-admin        (Vault admin tools)
├── external-secrets   (Secret syncing)
└── argocd             (GitOps controller)

Observability (platform-observability project)
└── observability      (Prometheus, Grafana, Alertmanager)

Security (platform-security project)
└── security           (RBAC, policies)

User Apps (workloads project)
├── workloads          (Main app namespace)
├── applications       (Alternative namespace)
└── services           (Alternative namespace)
```

### Isolation Strategy

Each namespace:
- ✅ Has ResourceQuota (prevents runaway)
- ✅ Has LimitRange (prevents tiny/huge pods)
- ✅ Has ServiceAccount isolation
- ✅ Can have NetworkPolicies
- ✅ Appears in one project only

---

## Secret Management

### Vault → Kubernetes Flow

```
Vault (encrypted secrets)
    ↓
Kubernetes ClusterSecretStore
    (external-secrets.io)
    ↓
ExternalSecret (observability namespace)
    ↓
Kubernetes Secret (alertmanager-discord-secret)
    ↓
Alertmanager (reads secret)
    ↓
Discord (webhook notified)
```

### Security Measures

| Layer | Mechanism |
|-------|-----------|
| **Encryption** | Vault at rest + in-flight TLS |
| **Access** | Vault auth via Kubernetes ServiceAccount |
| **Isolation** | ExternalSecret only in observability namespace |
| **Audit** | Vault audit logs all secret access |
| **Rotation** | ESO reconciles continuously |

---

## Component Details

### Vault (Platform-Tools)

**What it does:**
- Stores sensitive data (Discord webhook)
- Provides auth to ESO
- Maintains audit logs

**Architecture:**
```
Helm Chart (vault) → Stateful Pod
├── Data: /vault/data (10Gi PVC)
├── Audit: /vault/audit (5Gi PVC)
└── Storage: Raft-based HA
```

**Connection:**
- Service: `vault.vault.svc:8200`
- ESO connects via Kubernetes auth
- Never exposed to internet (port-forward only)

### External Secrets Operator (Platform-Tools)

**What it does:**
- Watches ExternalSecret resources
- Fetches secrets from Vault
- Creates Kubernetes Secrets
- Continuously reconciles

**Architecture:**
```
3 pods:
├── external-secrets (controller - reconciles ES)
├── cert-controller (manages certificates)
└── webhook (validates ES resources)

Watches: ExternalSecret resources
Acts on: ClusterSecretStore (vault-backend)
Outputs: Kubernetes Secrets
```

### Argo CD (Platform-Tools - Self-Manages)

**What it does:**
- Watches Git (main branch)
- Reconciles cluster with Git
- Never runs manual commands
- Self-manages its own deployment

**Architecture:**
```
7 pods:
├── application-controller (reconciles apps)
├── applicationset-controller (manages app sets)
├── dex-server (OIDC provider)
├── notifications-controller (sends updates)
├── redis (caching)
├── repo-server (Git cloning)
└── server (API + UI)

Watches: Git (https://github.com/...)
Reconciles: All Argo Applications
Self-manages: infrastructure/platform/argo-cd/app.yaml
```

### Prometheus (Observability)

**What it does:**
- Scrapes pod/node metrics
- Evaluates alert rules
- Stores time-series data
- Triggers alerts

**Configuration:**
```
Helm Chart: kube-prometheus-stack
Includes:
├── Prometheus (scraper + ruler)
├── Node exporter (node metrics)
├── Kube-state-metrics (API metrics)
└── Operator (CRD management)

Storage: 5Gi PVC (15 days retention)
Alert rules: 50+ built-in rules
```

### Alertmanager (Observability)

**What it does:**
- Receives alerts from Prometheus
- Groups + deduplicates
- Routes to Discord
- Manages silences/inhibitions

**Configuration:**
```
Helm Chart: kube-prometheus-stack
AlertmanagerConfig:
├── route: root notification path
├── receivers: Discord webhook
└── inhibit_rules: suppress duplicates

Webhook: From Vault via ESO
Routing: Based on alert labels
```

### Grafana (Observability)

**What it does:**
- Visualizes Prometheus metrics
- Provides dashboards
- Alerts on anomalies
- Shares insights

**Configuration:**
```
Helm Chart: kube-prometheus-stack
Defaults:
├── Admin user: admin
├── Admin password: admin (change in prod!)
├── Data source: Prometheus
└── Default dashboards: Enabled

Port: 3000 (port-forwarded)
```

---

## Data Flow

### Alert Pipeline

```
1. METRIC COLLECTION
   Prometheus scrapes:
   ├── kubelet (nodes)
   ├── API server (requests)
   └── App pods (custom metrics)

2. RULE EVALUATION
   Prometheus evaluates rules every 30s:
   ├── "up{job='prometheus'}" (Watchdog)
   ├── "node_memory_MemAvailable_bytes < 1Gi" (Low memory)
   └── Custom rules

3. ALERT TRIGGERING
   If rule matches → Create Alert
   Example: Watchdog (always fires - test alert)

4. ALERTMANAGER RECEIVES
   Prometheus sends alert to Alertmanager
   Alertmanager receives at:
   http://alertmanager-kube-prometheus-stack-alertmanager:9093/api/v2/alerts

5. ALERT ROUTING
   AlertmanagerConfig routes based on labels:
   route:
     receiver: 'discord'
   receivers:
   - name: 'discord'
     webhookConfigs:
       - url: 'https://discord.com/api/webhooks/...'

6. WEBHOOK DELIVERY
   Alertmanager sends POST to Discord webhook
   Discord displays in channel

7. SUPPRESSION (Optional)
   inhibit_rules suppress duplicate alerts
   Example: Don't alert on low memory if CPU is maxed
```

### Secret Sync Pipeline

```
1. VAULT STORES SECRET
   kv/alerts/discord:
   webhook_url = "https://discord.com/api/webhooks/..."

2. ESO WATCHES
   ExternalSecret in observability namespace:
   spec:
     secretStoreRef: vault-backend
     data:
     - secretKey: webhook_url
       remoteRef: alerts/discord

3. ESO FETCHES
   ExternalSecret → ClusterSecretStore (vault)
   ClusterSecretStore → Vault (Kubernetes auth)
   Vault → Returns secret

4. KUBERNETES SECRET CREATED
   Secret: alertmanager-discord-secret
   Data: webhook_url = "https://..."

5. ALERTMANAGER USES
   AlertmanagerConfig references secret:
   webhookConfigs:
   - url: 'from secret: alertmanager-discord-secret/webhook_url'
   
   (Handled by Kustomize/Helm variable substitution)
```

---

## GitOps Workflow

### How Deployments Work

```
Developer
   ↓
Edit infrastructure/workloads/my-app/app.yaml
   ↓
git add infrastructure/workloads/my-app/app.yaml
git commit -m "Add my-app"
git push origin main
   ↓
GitHub (main branch updated)
   ↓
Argo CD detects change
   ↓
Argo CD fetches latest from Git
   ↓
Argo CD compares Git ↔ Cluster
   ↓
Argo CD applies differences
   ↓
Kubectl deploys to workloads namespace
   ↓
Pod starts running
   ↓
✅ Deployment complete
```

### Sync Statuses

| Status | Meaning | Action |
|--------|---------|--------|
| **Synced** | Git = Cluster | Nothing to do |
| **OutOfSync** | Git ≠ Cluster | Argo will sync soon |
| **Unknown** | Can't determine | Check conditions |
| **SyncFailed** | Sync had error | Check error message |

---

## Disaster Recovery

### Recovery Capability

Complete recovery from Git + Vault backups:

```
Step 1: Fresh K3s cluster
Step 2: kubectl apply root-app.yaml
Step 3: Argo CD deploys infrastructure/
Step 4: Vault unseals (3 keys)
Step 5: ESO syncs secrets
Step 6: All apps auto-deploy
Step 7: Backups restore data

Time: ~15 minutes
Data: Complete from backups
```

### Backup Strategy

| Component | Frequency | Storage | Recovery |
|-----------|-----------|---------|----------|
| **Git repo** | Continuous | GitHub | Push latest to new cluster |
| **Vault data** | Manual | Local file | `vault operator raft snapshot restore` |
| **Prometheus data** | Rolling window | PVC | 15 days in-cluster |
| **Grafana config** | In Git | infrastructure/observability | Deployed with app |

---

## Consistency & Safety

### Idempotency

All operations are idempotent:
- **Applying same app twice** = No change second time
- **Syncing same revision** = No change if identical
- **Restarting pod** = Same configuration applied

### Immutability

Core files are write-protected:
- ✅ Git prevents direct modification
- ✅ RBAC limits who can edit
- ✅ Projects restrict namespace access
- ✅ Argo prevents manual kubectl edits

### Rollback Strategy

```
Bad deployment?

git log infrastructure/workloads/my-app/app.yaml
git revert <commit-hash>
git push origin main

↓
Argo sees revert in Git
↓
Argo applies old version
↓
✅ Rollback complete
```

---

## Evolution Path

### Starting (Current)

```
1 cluster
├── 4 projects
├── 7 applications
├── 25+ pods
└── Fully functional
```

### Growing

```
2 clusters (prod + staging)
├── Same projects on both
├── Dev + prod namespaces
├── Cross-cluster sync
└── Blue-green deployments
```

### Scaling

```
3 teams
├── Team A (database)
├── Team B (api)
├── Team C (frontend)
├── 3 new projects
├── 3 new repositories
└── Central platform team manages core
```

---

## Design Patterns Used

| Pattern | Where | Why |
|---------|-------|-----|
| **App-of-Apps** | Root → Projects | Modularity |
| **Kustomize overlays** | infrastructure/* | DRY configurations |
| **GitOps** | Everything in Git | Single source of truth |
| **Project isolation** | RBAC per team | Safety |
| **Helm for 3rd party** | Prometheus, Vault | Industry standard |
| **Secrets from Vault** | ESO integration | Security |
| **Persistent backups** | Vault snapshots | Disaster recovery |

---

## Next: Operations & Troubleshooting

See [OPERATIONS.md](./OPERATIONS.md) for:
- How to operate the system
- Common troubleshooting
- Day-2 operations
- Performance tuning
