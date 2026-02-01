# Platform GitOps - Production Kubernetes Platform

**Version:** 2.0 (Production Ready)  
**Last Updated:** 2026-02-01  
**Status:** ✅ Operational  
**Cluster:** K3s Single Node (16GB Mac, 10GB K3s, 6GB macOS)

---

## What Is This?

A **complete, self-owned Kubernetes platform** with:
- **GitOps automation** via Argo CD
- **Full observability** (Prometheus, Grafana, Alertmanager)
- **Secure secrets management** via Vault
- **Multi-team namespace isolation**
- **Discord alert notifications**
- **Automated disaster recovery** (~15 minutes)

Everything is **declarative**, **auditable**, and **reproducible from Git**.

---

## Quick Start

### 1. Start Services (30 seconds)

```bash
# Port forward all services
~/.local/bin/k8s-port-forward.sh start

# Or start them manually
kubectl port-forward -n observability svc/kube-prometheus-stack-grafana 3000:80 &
kubectl port-forward -n observability svc/kube-prometheus-stack-prometheus 9090:9090 &
kubectl port-forward -n observability svc/kube-prometheus-stack-alertmanager 9093:9093 &
kubectl port-forward -n argocd svc/argocd-server 8080:443 &
kubectl port-forward -n vault svc/vault 8200:8200 &
```

### 2. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9090 | - |
| **Alertmanager** | http://localhost:9093 | - |
| **Argo CD** | http://localhost:8080 | See: `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' \| base64 -d` |
| **Vault** | http://localhost:8200 | Already initialized |

### 3. Check Cluster Health

```bash
# Everything running?
kubectl get all -A

# Resource usage
kubectl describe quota -A

# Argo applications
kubectl get app -n argocd
```

---

## Repository Structure

```
platform-gitops/
├── README.md                          ← You are here
│
├── bootstrap/
│   └── argocd-bootstrap.yaml          One-time cluster bootstrap
│
├── infrastructure/
│   ├── argocd/
│   │   └── projects/                  Argo CD project definitions
│   │       ├── platform-observability.yaml
│   │       ├── platform-security.yaml
│   │       └── workloads.yaml
│   │
│   ├── observability/
│   │   ├── app.yaml                   Prometheus/Grafana/Alertmanager
│   │   ├── prometheus/
│   │   │   └── values.yaml
│   │   ├── alertmanager/
│   │   │   ├── values.yaml
│   │   │   └── external-secret.yaml   Discord webhook from Vault
│   │   └── grafana/
│   │       └── values.yaml
│   │
│   ├── security/
│   │   ├── vault/
│   │   │   └── app.yaml               Vault initialization
│   │   └── external-secrets/
│   │       └── app.yaml               External Secrets Operator
│   │
│   └── argocd/
│       └── root-app.yaml              App-of-Apps (triggers all)
│
├── clusters/
│   └── local/
│       ├── namespaces.yaml            6 namespaces
│       ├── resourcequotas.yaml        Resource allocation
│       └── limitranges.yaml           Pod defaults & limits
│
├── docs/
│   ├── OPERATIONS.md                  Daily operations guide
│   ├── DISASTER_RECOVERY.md           Complete recovery procedures
│   └── ARCHITECTURE.md                System design decisions
│
└── scripts/
    └── port-forward.sh                Utility scripts
```

---

## Core Concepts

### Argo CD Projects (Organization)

| Project | Namespace | Purpose |
|---------|-----------|---------|
| **platform-observability** | observability | Prometheus, Grafana, Alertmanager |
| **platform-security** | security | Vault, External Secrets |
| **workloads** | workloads | User applications |

Each project has explicit namespace and source access. Clean ownership. No clutter.

### Namespaces (Isolation)

```
argocd              Argo CD control plane (bootstrap-only)
observability       Metrics, dashboards, alerts (6Gi quota)
security            Vault, secret management (1.5Gi quota)
workloads           User applications (4Gi quota)
```

Each namespace has:
- **ResourceQuota** - Maximum memory/CPU
- **LimitRange** - Per-pod defaults and limits
- Explicit naming convention

### GitOps Workflow

```
1. Edit infrastructure in Git
2. Commit and push to main
3. Argo CD auto-syncs (within 3 minutes)
4. Kubernetes state matches Git
5. All changes auditable
```

**No manual kubectl edits on managed resources.**

### Secret Management

```
Vault (kv/*)
    ↓
ExternalSecrets Operator
    ↓
Kubernetes Secrets
    ↓
Application mounts secret
```

Currently storing:
- `kv/alerting/discord` → Discord webhook for Alertmanager

---

## Common Operations

### Deploy Changes (via Git)

```bash
# 1. Make changes
vim infrastructure/observability/prometheus/values.yaml

# 2. Commit and push (this triggers Argo CD)
git add -A
git commit -m "Increase Prometheus retention to 30 days"
git push origin main

# 3. Watch Argo sync (automatic within 3 minutes)
watch kubectl get app -n argocd

# 4. Verify deployed
kubectl describe statefulset -n observability prometheus-kube-prometheus-stack-prometheus
```

### Check Alerts

```bash
# View all alert rules
kubectl get prometheusrule -n observability

# Check active alerts
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts'

# View Alertmanager config
kubectl get secret -n observability alertmanager-kube-prometheus-stack-alertmanager \
  -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d

# Check Discord webhook
kubectl get externalsecret -n observability alertmanager-discord
```

### Update Discord Webhook

```bash
# 1. Get new webhook URL from Discord channel settings

# 2. Update Vault
kubectl exec -n vault vault-0 -- \
  vault kv put kv/alerting/discord \
  webhook_url="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"

# 3. Force ExternalSecret sync
kubectl patch externalsecret alertmanager-discord -n observability \
  -p '{"spec":{"refreshInterval":"10s"}}'

# 4. Wait 30 seconds, then verify
kubectl get secret alertmanager-discord-secret -n observability -o yaml
```

### Backup Vault (Critical!)

```bash
# Create backup directory
mkdir -p ~/backups/vault

# Take snapshot
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ~/backups/vault/vault-$(date +%Y%m%d-%H%M%S).raft

# Verify
ls -lh ~/backups/vault/
```

### Add New Application

```bash
# 1. Create directory
mkdir -p infrastructure/apps/myapp

# 2. Create Argo Application
cat > infrastructure/apps/myapp/app.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: workloads
  source:
    repoURL: https://github.com/YOUR_ORG/platform-gitops.git
    targetRevision: main
    path: infrastructure/apps/myapp
  destination:
    server: https://kubernetes.default.svc
    namespace: workloads
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
EOF

# 3. Commit and apply
git add -A
git commit -m "Add myapp application"
git push origin main

kubectl apply -f infrastructure/apps/myapp/app.yaml
```

---

## Disaster Scenarios

### Scenario 1: Pod Crashes

**Symptom:** Pod in CrashLoopBackOff or Pending

```bash
# Diagnose
kubectl describe pod <pod-name> -n <namespace>
kubectl logs -n <namespace> <pod-name> --tail=50

# Check resource constraints
kubectl describe quota -n <namespace>
kubectl describe limitrange -n <namespace>

# Recovery
kubectl delete pod <pod-name> -n <namespace>
# Argo CD will recreate automatically
```

### Scenario 2: Application Out of Sync

**Symptom:** Argo shows "OutOfSync"

```bash
# Force sync
kubectl patch app <app-name> -n argocd \
  -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}'

# Or rollback via Git
cd ~/platform/gitops
git revert HEAD --no-edit
git push origin main
```

### Scenario 3: Complete Cluster Down (Recovery: ~15 minutes)

#### Step 1: Bootstrap Argo CD

```bash
kubectl apply -f bootstrap/argocd-bootstrap.yaml

# Wait for ready
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=argocd-server \
  -n argocd --timeout=300s
```

#### Step 2: Create Core Infrastructure

```bash
kubectl apply -f clusters/local/namespaces.yaml
kubectl apply -f clusters/local/resourcequotas.yaml
kubectl apply -f clusters/local/limitranges.yaml

# Verify
kubectl get ns
kubectl describe quota -A
```

#### Step 3: Create Argo Projects

```bash
kubectl apply -f infrastructure/argocd/projects/

# Verify
kubectl get appproject -n argocd
```

#### Step 4: Deploy Everything (via Root Application)

```bash
kubectl apply -f infrastructure/argocd/root-app.yaml

# Watch cascade
watch kubectl get app -n argocd

# Takes ~3-5 minutes for full sync
```

#### Step 5: Restore Vault (if needed)

```bash
# Wait for Vault pod
kubectl wait --for=condition=ready pod vault-0 -n vault --timeout=300s

# Restore from backup
kubectl cp ~/backups/vault/vault-*.raft vault/vault-0:/tmp/vault.raft

kubectl exec -n vault vault-0 -- \
  vault operator raft snapshot restore /tmp/vault.raft

# Verify secrets
kubectl exec -n vault vault-0 -- vault kv get kv/alerting/discord
```

#### Step 6: Verify All Components

```bash
# Check all pods running
kubectl get pods -A | grep -c Running

# Verify ExternalSecrets synced
kubectl get externalsecret -A

# Check Prometheus scraping
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length'

# Verify Grafana
kubectl get pod -n observability -l app.kubernetes.io/name=grafana
```

**Cluster is fully recovered from Git + Vault backup.**

---

## Troubleshooting

### Prometheus Not Scraping

```bash
# Check targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'

# Verify ServiceMonitors
kubectl get servicemonitor -n observability

# Check Prometheus config
kubectl describe prometheus -n observability kube-prometheus-stack-prometheus
```

### Alertmanager Not Sending Alerts

```bash
# Check running
kubectl get statefulset -n observability alertmanager-kube-prometheus-stack-alertmanager

# Verify config
kubectl exec -n observability alertmanager-kube-prometheus-stack-alertmanager-0 -- \
  cat /etc/alertmanager/config.yml

# Check webhook secret
kubectl get secret alertmanager-discord-secret -n observability -o yaml

# View logs
kubectl logs -n observability alertmanager-kube-prometheus-stack-alertmanager-0
```

### ExternalSecret Not Syncing

```bash
# Check status
kubectl describe externalsecret alertmanager-discord -n observability

# Check operator
kubectl logs -n external-secrets -l app=external-secrets -f

# Verify Vault secret exists
kubectl exec -n vault vault-0 -- vault kv get kv/alerting/discord

# Force refresh
kubectl patch externalsecret alertmanager-discord -n observability \
  -p '{"spec":{"refreshInterval":"10s"}}'

sleep 30

# Verify synced
kubectl get secret alertmanager-discord-secret -n observability
```

### Resource Quota Exceeded

```bash
# Check usage
kubectl describe quota -n observability

# View limits
kubectl describe limitrange -n observability

# Find heavy pods
kubectl top pods -n observability | sort -k3 -nr

# Increase quota (edit and reapply)
kubectl edit quota observability -n observability
```

### Pod in CrashLoopBackOff

```bash
# Get details
kubectl describe pod <pod-name> -n observability

# View logs (previous run)
kubectl logs -n observability <pod-name> --previous

# Common causes:
# - Memory limit exceeded
# - Image pull error
# - ConfigMap missing
# - Port conflict

# Recovery
kubectl delete pod <pod-name> -n observability
```

---

## Resource Allocation

### Current Quotas

```yaml
observability:
  memory: 6Gi (Prometheus 5Gi + Grafana 512Mi + other)
  cpu: 3 cores

security:
  memory: 1.5Gi (Vault, External Secrets)
  cpu: 1 core

workloads:
  memory: 4Gi (user applications)
  cpu: 2 cores
```

### Per-Pod Limits (LimitRange)

```yaml
observability:
  default: 512Mi
  max: 2Gi

security:
  default: 256Mi
  max: 1Gi

workloads:
  default: 512Mi
  max: 2Gi
```

### Check Usage

```bash
# Current usage
kubectl describe quota -A

# Pod breakdown
kubectl top pods -A | sort -k3 -nr

# Node usage
kubectl top nodes
```

---

## Maintenance Schedule

### Daily

```bash
# Monitor cluster health
kubectl get pods -A
kubectl describe quota -A
kubectl get app -n argocd
```

### Weekly

```bash
# Backup Vault
mkdir -p ~/backups/vault/weekly
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ~/backups/vault/weekly/vault-$(date +%Y%m%d).raft

# Check resource usage
kubectl top nodes
kubectl top pods -A | head -20

# Review applications
kubectl get app -n argocd -o wide
```

### Monthly

```bash
# Full backup
mkdir -p ~/backups/full-$(date +%Y%m%d)
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ~/backups/full-$(date +%Y%m%d)/vault.raft

# Test alert rules
# Send test message to Discord

# Review and optimize quotas
kubectl describe quota -A
```

### Quarterly

```bash
# Full disaster recovery test
# - Do not delete cluster
# - Verify backup can be restored
# - Test complete rebuild procedure

# Update documentation
# Review this README
```

---

## Key Design Decisions

### Why Argo CD Projects?

✅ Clean UI organization  
✅ Explicit namespace boundaries  
✅ Future-proof for multi-team  
✅ Role-based access control ready  

### Why prune: false?

✅ Safety first (prevents accidental deletes)  
✅ Manual deletion requires explicit action  
✅ Production standard for critical systems  

### Why Vault for Secrets?

✅ Single source of truth  
✅ Encrypted at rest  
✅ Audit trail of all access  
✅ Zero secrets in Git  

### Why Git as Source of Truth?

✅ All changes auditable  
✅ Easy rollback  
✅ Reproducible deployments  
✅ No drift between branches  

---

## Advanced Operations

### Manual Argo Sync

```bash
# Sync specific app
kubectl patch app observability-stack -n argocd \
  -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}'

# Sync all apps
kubectl get app -n argocd -o name | xargs -I {} kubectl patch {} \
  -n argocd -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}'
```

### Rollback via Git

```bash
cd ~/platform/gitops

# View history
git log --oneline -10

# Revert to previous state
git revert HEAD --no-edit
git push origin main

# Argo auto-syncs back (safe because prune: false)
```

### Create Read-Only Application

```bash
kubectl patch app <app-name> -n argocd \
  -p '{"spec":{"syncPolicy":{"automated":null}}}'
```

### Enable Mutations Only (No Deletes)

```bash
kubectl patch app <app-name> -n argocd \
  -p '{"spec":{"syncPolicy":{"automated":{"prune":false,"selfHeal":true}}}}'
```

---

## Monitoring & Alerting

### Current Alert Setup

```
Prometheus Rules (Git)
    ↓
Alertmanager (routes alerts)
    ↓
Discord Webhook (notifications)
    ↓
Discord Channel (you see it)
```

### Add Custom Alert Rules

```bash
# Create file: infrastructure/observability/prometheus/custom-rules.yaml
cat > infrastructure/observability/prometheus/custom-rules.yaml <<'EOF'
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: custom-alerts
  namespace: observability
spec:
  groups:
  - name: custom.rules
    rules:
    - alert: HighMemoryUsage
      expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Pod {{ $labels.pod }} high memory usage"
EOF

# Commit and push
git add infrastructure/observability/prometheus/custom-rules.yaml
git commit -m "Add custom memory alert"
git push origin main
```

### Silence Alerts

```bash
# Via API
curl -X POST http://localhost:9093/api/v2/silences \
  -H 'Content-Type: application/json' \
  -d '{
    "matchers": [{"name": "alertname", "value": "NodeDown"}],
    "startsAt": "2026-02-01T00:00:00Z",
    "endsAt": "2026-02-02T00:00:00Z",
    "comment": "Maintenance"
  }'
```

---

## Getting Help

### Documentation

- **[OPERATIONS.md](docs/OPERATIONS.md)** - Detailed daily operations
- **[DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md)** - Complete recovery guide
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design details

### Commands

```bash
# Check cluster status
kubectl get all -A

# View all Argo apps
kubectl get app -n argocd

# Check resource usage
kubectl describe quota -A

# View recent changes
git log --oneline -20
```

### Escalation Path

1. Check this README
2. Search relevant docs (Operations, Disaster Recovery, Architecture)
3. Run diagnostics from troubleshooting section
4. Review Git history for recent changes
5. Check operator logs for errors

---

## Summary

**What You Have:**

✅ Complete GitOps platform with Argo CD  
✅ Full observability (Prometheus, Grafana, Alertmanager)  
✅ Secure secrets (Vault + ExternalSecrets)  
✅ Discord alerts  
✅ 15-minute disaster recovery  
✅ Production-grade operations  

**How It Works:**

1. Edit infrastructure in Git
2. Push to main
3. Argo CD auto-deploys
4. Kubernetes state matches Git
5. All changes auditable

**Key Commands:**

```bash
# Check health
kubectl get all -A

# Deploy changes
git add -A && git commit -m "message" && git push origin main

# Backup
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft

# Recover
kubectl apply -f bootstrap/argocd-bootstrap.yaml
kubectl apply -f clusters/local/namespaces.yaml
kubectl apply -f infrastructure/argocd/root-app.yaml
```

---

**Version:** 2.0 (Production Ready)  
**Last Updated:** 2026-02-01  
**Status:** ✅ Operational  

Everything you need is here. No searching. No legacy references. Just modern, production-grade GitOps.
