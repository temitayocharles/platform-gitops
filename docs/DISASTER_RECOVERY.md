# Disaster Recovery & Operations Runbook

**Last Updated:** 2026-02-01  
**Status:** Production Ready  
**Cluster:** K3s Single Node (16GB Mac, 10GB K3s, 6GB macOS)  
**Version:** Kubernetes 1.27+, Helm 3.x+, Argo CD 2.x+

---

## TABLE OF CONTENTS

1. **[NORMAL OPERATIONS](#normal-operations)** - Day-to-day tasks
2. **[ALERTING & NOTIFICATIONS](#alerting--notifications)** - Alert management
3. **[DISASTER RECOVERY](#disaster-recovery)** - Full cluster rebuild
4. **[VAULT BACKUP & RESTORE](#vault-backup--restore)** - Secrets protection
5. **[ARGO CD OPERATIONS](#argo-cd-operations)** - GitOps management
6. **[TROUBLESHOOTING](#troubleshooting)** - Fix common issues
7. **[RBAC & SECURITY](#rbac--security)** - Access control
8. **[MAINTENANCE](#maintenance)** - Keep system healthy

---

## NORMAL OPERATIONS

### Quick Start (30 Seconds)

```bash
# 1. Port forward all services
~/.local/bin/k8s-port-forward.sh start

# 2. Access services
# Grafana:      http://localhost:3000 (admin/admin)
# Prometheus:   http://localhost:9090 (metrics)
# Alertmanager: http://localhost:9093 (alerts)
# Vault:        http://localhost:8200 (secrets)
# Argo CD:      http://localhost:8080 (GitOps)
```

### Monitor Cluster Health

```bash
# Check all resources
kubectl get all -A

# Check resource usage
kubectl describe quota -A
kubectl describe limitrange -A

# Check Argo applications
kubectl get app -n argocd

# Check pod status
kubectl get pods -A -o wide
```

### Update Infrastructure via Git

```bash
# 1. Edit configuration
vim ~/platform/gitops/infrastructure/observability/prometheus/values.yaml

# 2. Commit and push (this triggers Argo CD)
cd ~/platform/gitops
git add -A
git commit -m "Update Prometheus retention to 30 days"
git push origin main

# 3. Watch Argo CD sync (automatic within 3 minutes)
kubectl get app -n argocd -w

# 4. Verify changes
kubectl describe statefulset -n observability prometheus-kube-prometheus-stack-prometheus
```

### Check Alert Status

```bash
# View all alert rules
kubectl get prometheusrule -n observability

# Check active alerts
curl http://localhost:9090/api/v1/alerts | jq .

# View Alertmanager configuration
kubectl get secret -n observability alertmanager-kube-prometheus-stack-alertmanager \
  -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d

# Check Discord webhook status
kubectl get externalsecret -n observability alertmanager-discord
```

### Backup Procedure (Daily/Weekly)

```bash
# Create backup directory
mkdir -p ~/backups/$(date +%Y-%m-%d)

# Backup Vault (CRITICAL)
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ~/backups/$(date +%Y-%m-%d)/vault.raft

# Backup Git configuration (easy recovery)
cd ~/platform/gitops && git log --oneline -10 > ~/backups/$(date +%Y-%m-%d)/git-log.txt

# Verify backup
ls -lh ~/backups/$(date +%Y-%m-%d)/
```

---

## ALERTING & NOTIFICATIONS

### Discord Webhook Management

**Current Setup:**
- Webhook URL stored in Vault: `kv/alerting/discord`
- Synced by ExternalSecrets to: `alertmanager-discord-secret`
- Used by Alertmanager for routing

#### Update Discord Webhook

```bash
# 1. Get new webhook URL from Discord channel settings

# 2. Update Vault
kubectl exec -n vault vault-0 -- \
  vault kv put kv/alerting/discord \
  webhook_url="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"

# 3. Force ExternalSecret sync (normally 1h)
kubectl patch externalsecret alertmanager-discord -n observability \
  -p '{"spec":{"refreshInterval":"10s"}}'

# 4. Wait for secret update (30 seconds)
sleep 30

# 5. Verify secret updated
kubectl get secret alertmanager-discord-secret -n observability -o yaml

# 6. Restart Alertmanager to use new webhook
kubectl rollout restart statefulset alertmanager-kube-prometheus-stack-alertmanager -n observability
```

#### Test Discord Webhook

```bash
# Get webhook URL from Vault
WEBHOOK=$(kubectl exec -n vault vault-0 -- \
  vault kv get -field=webhook_url kv/alerting/discord)

# Send test message
curl -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Test alert from Prometheus - integration working!"}'

# Check Discord channel for message
```

### Manage Alert Rules

#### View Current Alert Rules

```bash
# List all PrometheusRule resources
kubectl get prometheusrule -n observability

# View specific rule
kubectl get prometheusrule -n observability kube-prometheus-stack-alertmanager.rules -o yaml
```

#### Add New Alert Rule

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
        description: "Memory usage is {{ $value | humanizePercentage }}"
EOF

# Commit and push
cd ~/platform/gitops
git add infrastructure/observability/prometheus/custom-rules.yaml
git commit -m "Add custom alert rules for memory usage"
git push origin main

# Argo CD applies automatically
```

#### Silence Alerts Temporarily

```bash
# Via Alertmanager UI
# http://localhost:9093 → Click "Silence" on alert

# Via API
curl -X POST http://localhost:9093/api/v2/silences \
  -H 'Content-Type: application/json' \
  -d '{
    "matchers": [
      {"name": "alertname", "value": "NodeDown", "isRegex": false}
    ],
    "startsAt": "2026-02-01T00:00:00Z",
    "endsAt": "2026-02-01T04:00:00Z",
    "comment": "Maintenance window"
  }'
```

### Monitor Alertmanager

```bash
# Check if Alertmanager is running
kubectl get statefulset -n observability alertmanager-kube-prometheus-stack-alertmanager

# View Alertmanager logs
kubectl logs -n observability alertmanager-kube-prometheus-stack-alertmanager-0 -f

# Check alert routing configuration
kubectl exec -n observability alertmanager-kube-prometheus-stack-alertmanager-0 -- \
  cat /etc/alertmanager/config.yml
```

---

## DISASTER RECOVERY

### Scenario 1: Single Pod Crashes

**Symptom:** A pod is in CrashLoopBackOff or Pending

```bash
# Identify the pod
kubectl get pods -A | grep -i crash

# Get detailed error
kubectl describe pod <pod-name> -n <namespace>

# View logs
kubectl logs -n <namespace> <pod-name> --tail=50

# Check resource constraints
kubectl describe quota -n <namespace>
kubectl describe limitrange -n <namespace>

# Common fixes:
# 1. Pod out of memory → Increase quota
# 2. Image not found → Check Helm values
# 3. Dependency missing → Check if dependency app synced

# If all else fails, delete and let Argo recreate
kubectl delete pod <pod-name> -n <namespace>
```

### Scenario 2: Application Out of Sync

**Symptom:** Argo CD shows "OutOfSync"

```bash
# Check diff
kubectl get app <app-name> -n argocd -o yaml | grep -A 30 "status"

# Force sync (safe, no deletes)
kubectl patch app <app-name> -n argocd \
  -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}'

# Wait for sync
watch kubectl get app <app-name> -n argocd

# If still out of sync, check Git repository
cd ~/platform/gitops
git status
git log --oneline -5
```

### Scenario 3: Complete Node/Cluster Down

**Recovery Time:** ~15 minutes (automated)

#### Step 1: Bootstrap Argo CD

```bash
# This is done once during initial setup
kubectl apply -f ~/platform/gitops/bootstrap/argocd-bootstrap.yaml

# Wait for Argo CD to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server \
  -n argocd --timeout=300s
```

#### Step 2: Create Namespaces & Quotas

```bash
# Apply cluster-level configuration
kubectl apply -f ~/platform/gitops/clusters/local/namespaces.yaml
kubectl apply -f ~/platform/gitops/clusters/local/resourcequotas.yaml
kubectl apply -f ~/platform/gitops/clusters/local/limitranges.yaml

# Verify
kubectl get ns
kubectl describe quota -A
```

#### Step 3: Create Argo Projects

```bash
# Apply all Argo projects (enables proper scoping)
kubectl apply -f ~/platform/gitops/infrastructure/argocd/projects/

# Verify
kubectl get appproject -n argocd
```

#### Step 4: Deploy Root Application (Triggers All)

```bash
# This single application syncs ALL infrastructure from Git
kubectl apply -f ~/platform/gitops/root-app.yaml

# Watch the auto-sync cascade
watch kubectl get app -n argocd

# Full sync typically completes in 3-5 minutes
# Key sequence:
# 1. platform-observability syncs
# 2. platform-security syncs
# 3. External Secrets starts syncing secrets
# 4. Prometheus/Alertmanager pods start
```

#### Step 5: Restore Vault (If Needed)

```bash
# Wait for Vault pod to be ready
kubectl wait --for=condition=ready pod vault-0 -n vault --timeout=300s

# Check if Vault was wiped (only if you stored secrets)
kubectl exec -n vault vault-0 -- vault kv list kv/

# If empty, restore from backup
kubectl cp ~/backups/latest/vault.raft vault/vault-0:/tmp/vault.raft

kubectl exec -n vault vault-0 -- \
  vault operator raft snapshot restore /tmp/vault.raft

# Verify secrets restored
kubectl exec -n vault vault-0 -- vault kv get kv/alerting/discord
```

#### Step 6: Verify All Components

```bash
# Wait for ExternalSecrets to sync
kubectl get externalsecret -A

# Verify Alertmanager has Discord secret
kubectl get secret alertmanager-discord-secret -n observability

# Check Prometheus is scraping
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length'

# Verify Grafana is ready
kubectl get pod -n observability -l app.kubernetes.io/name=grafana

# All services should be running
kubectl get pods -A | grep -E "running|terminating" | wc -l
```

#### Step 7: Verify Alerting Path

```bash
# Check Alertmanager configuration
kubectl exec -n observability alertmanager-kube-prometheus-stack-alertmanager-0 -- \
  cat /etc/alertmanager/config.yml | grep -A 5 "discord_configs"

# Send test alert
kubectl exec -n observability prometheus-kube-prometheus-stack-prometheus-0 -- \
  promtool query instant "up{job='node-exporter'}" \
  --server http://localhost:9090

# Verify alert appears in Discord
```

**Full cluster is now recovered from Git.**

---

## VAULT BACKUP & RESTORE

### Backup Strategy

Vault stores all secrets. Backup is non-negotiable.

```bash
# Create backup directory structure
mkdir -p ~/backups/vault/{daily,weekly,monthly}

# Daily backup (automated via cron)
0 2 * * * /home/temitayocharles/scripts/backup-vault.sh

# Script content
#!/bin/bash
DATE=$(date +\%Y\%m\%d-\%H\%M\%S)
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ~/backups/vault/daily/vault-${DATE}.raft
# Keep last 7 days
find ~/backups/vault/daily -mtime +7 -delete
```

### Manual Backup

```bash
# Immediate backup before major changes
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ~/backups/vault/manual-$(date +%Y%m%d-%H%M%S).raft

# Verify backup integrity
ls -lh ~/backups/vault/manual-*
file ~/backups/vault/manual-* | head -1
```

### Vault Restore Procedure

```bash
# 1. Verify Vault pod is running
kubectl get pod -n vault vault-0

# 2. Check current Vault state
kubectl exec -n vault vault-0 -- vault status

# 3. Restore from backup
BACKUP_FILE="~/backups/vault/manual-20260201-120000.raft"

# Copy backup into pod
kubectl cp "$BACKUP_FILE" vault/vault-0:/tmp/vault-restore.raft

# Perform restoration
kubectl exec -n vault vault-0 -- \
  vault operator raft snapshot restore /tmp/vault-restore.raft

# 4. Restart Vault to apply restoration
kubectl delete pod vault-0 -n vault

# 5. Wait for pod to restart
kubectl wait --for=condition=ready pod vault-0 -n vault --timeout=300s

# 6. Verify secrets restored
kubectl exec -n vault vault-0 -- vault kv list kv/
kubectl exec -n vault vault-0 -- vault kv get kv/alerting/discord
```

---

## ARGO CD OPERATIONS

### Argo CD Status

```bash
# Check Argo CD health
kubectl get deployment -n argocd

# Get Argo admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d

# Check all applications
kubectl get app -n argocd

# View application status
kubectl get app -n argocd -o wide
```

### Manual Sync

```bash
# Sync specific application
argocd app sync observability-stack -n argocd

# Sync with hard refresh
kubectl patch app observability-stack -n argocd \
  -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}'

# Sync all applications
kubectl get app -n argocd -o name | xargs -I {} kubectl patch {} \
  -n argocd -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}'
```

### Rollback via Git

```bash
# View commit history
cd ~/platform/gitops
git log --oneline -20

# Revert to previous commit
git revert HEAD --no-edit
git push origin main

# Argo CD auto-syncs back to previous state
# (Safe because prune: false prevents unexpected deletes)

# Verify rollback
kubectl get app -n argocd -w
```

### Add New Application

```bash
# 1. Create application directory
mkdir -p ~/platform/gitops/infrastructure/myapp

# 2. Create Helm values
cat > ~/platform/gitops/infrastructure/myapp/values.yaml <<'EOF'
# Your values here
EOF

# 3. Create Argo Application manifest
cat > ~/platform/gitops/infrastructure/myapp/app.yaml <<'EOF'
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
    path: infrastructure/myapp
  destination:
    server: https://kubernetes.default.svc
    namespace: workloads
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
EOF

# 4. Commit and apply
cd ~/platform/gitops
git add -A
git commit -m "Add myapp to platform"
git push origin main

# 5. Apply the application manifest
kubectl apply -f infrastructure/myapp/app.yaml
```

---

## TROUBLESHOOTING

### Prometheus Not Scraping Targets

```bash
# Check target status
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'

# Check ServiceMonitors
kubectl get servicemonitor -n observability

# Check PrometheusRule
kubectl describe prometheus -n observability kube-prometheus-stack-prometheus

# Common fixes:
# 1. ServiceMonitor labels don't match → Check labels
# 2. Network policy blocking → Check network policies
# 3. Target endpoint down → Check target pod
```

### Alertmanager Not Sending Alerts

```bash
# Check Alertmanager is running
kubectl get statefulset -n observability alertmanager-kube-prometheus-stack-alertmanager

# Check configuration
kubectl exec -n observability alertmanager-kube-prometheus-stack-alertmanager-0 -- \
  cat /etc/alertmanager/config.yml

# Check Discord secret is present
kubectl get secret alertmanager-discord-secret -n observability -o yaml

# Verify webhook URL
kubectl get secret alertmanager-discord-secret -n observability \
  -o jsonpath='{.data.DISCORD_WEBHOOK_URL}' | base64 -d

# Check Alertmanager logs
kubectl logs -n observability alertmanager-kube-prometheus-stack-alertmanager-0
```

### ExternalSecret Not Syncing

```bash
# Check ExternalSecret status
kubectl describe externalsecret alertmanager-discord -n observability

# Check ExternalSecrets operator logs
kubectl logs -n external-secrets -l app=external-secrets -f

# Check Vault auth is working
kubectl describe externalsecret alertmanager-discord -n observability | grep -A 10 "Status"

# Verify Vault secret exists
kubectl exec -n vault vault-0 -- vault kv get kv/alerting/discord

# Force manual refresh (normally 1h)
kubectl patch externalsecret alertmanager-discord -n observability \
  -p '{"spec":{"refreshInterval":"10s"}}'

sleep 30

# Verify secret was synced
kubectl get secret alertmanager-discord-secret -n observability
```

### Resource Quota Exceeded

```bash
# Check current usage
kubectl describe quota -n observability

# View limits
kubectl describe limitrange -n observability

# Find resource-heavy pods
kubectl top pods -n observability | sort -k3 -nr

# Temporary increase quota (edit and reapply)
kubectl edit quota observability -n observability

# Or update Git (proper way)
vim ~/platform/gitops/clusters/local/resourcequotas.yaml
git add -A && git commit -m "Increase observability quota" && git push origin main
```

### Pod in CrashLoopBackOff

```bash
# Check pod details
kubectl describe pod <pod-name> -n observability

# Check logs
kubectl logs -n observability <pod-name> --previous

# Common causes:
# 1. Memory limit exceeded → Check LimitRange + Quota
# 2. Image pull error → Check image in values.yaml
# 3. ConfigMap missing → Check if app synced correctly
# 4. Port conflict → Check service ports

# Recovery
kubectl delete pod <pod-name> -n observability
# Argo CD will recreate it
```

---

## RBAC & SECURITY

### Argo Projects Control Access

Each Argo Project has specific namespace access.

```yaml
# Current Projects
platform-observability  → observability namespace only
platform-security       → security namespace only
workloads               → workloads namespace only
```

### Restrict Mutations

```bash
# Make application read-only (no sync)
kubectl patch app observability-stack -n argocd \
  -p '{"spec":{"syncPolicy":{"automated":null}}}'

# Enable sync with safety
kubectl patch app observability-stack -n argocd \
  -p '{"spec":{"syncPolicy":{"automated":{"prune":false,"selfHeal":true}}}}'
```

### Audit Changes

```bash
# View all Argo applications
kubectl get app -n argocd -o json | jq '.items[] | {name, syncPolicy}'

# View Git history (source of truth)
cd ~/platform/gitops
git log --oneline --all

# View specific change
git show <commit-hash>
```

---

## MAINTENANCE

### Weekly Tasks

```bash
# 1. Backup Vault
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ~/backups/vault/weekly-$(date +%Y%m%d).raft

# 2. Check resource usage
kubectl describe quota -A
kubectl top nodes
kubectl top pods -A | head -20

# 3. Review applications
kubectl get app -n argocd

# 4. Check for pod restarts
kubectl get pods -A --sort-by=.status.containerStatuses[0].restartCount | tail -10
```

### Monthly Tasks

```bash
# 1. Full backup
mkdir -p ~/backups/full-$(date +%Y%m%d)
cd ~/backups/full-$(date +%Y%m%d)
kubectl get all -A -o yaml > all-resources.yaml
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ./vault.raft

# 2. Test disaster recovery (optional)
# - Do not delete cluster
# - Just verify backup can be restored
# - Confirm Vault snapshot is valid

# 3. Review alert rules for noise
kubectl get prometheusrule -n observability

# 4. Update documentation
# - Review and update this runbook
# - Document any custom changes
```

### Quarterly Tasks

```bash
# 1. Full disaster recovery test
# - Scale down cluster (don't delete)
# - Rebuild from bootstrap
# - Restore Vault snapshot
# - Verify all services working

# 2. Review and optimize resource quotas
kubectl describe quota -A

# 3. Test alert rules
# Trigger a test alert to verify Discord routing

# 4. Review Argo CD applications
# Remove unused apps, update documentation
```

---

## SUMMARY

### What Protects Your Cluster

✅ **Argo CD with prune: false** - Prevents accidental deletes  
✅ **Git as source of truth** - All changes auditable  
✅ **Vault backup strategy** - Secrets protected  
✅ **Resource quotas** - Prevents pod evictions  
✅ **LimitRanges** - Guarantees pod fits  
✅ **Automated Argo projects** - Clear ownership  

### How to Recover from Anything

1. **Pod crash** → Delete pod, Argo recreates  
2. **Application broken** → Revert Git, Argo resync  
3. **Secrets lost** → Restore Vault from backup  
4. **Complete cluster down** → 15-minute automated recovery via Git + Vault backup  

### No Manual Intervention Needed

Everything is **declarative**, **auditable**, and **reproducible from Git**.

---

**Version:** 1.0 (Complete, Production Ready)  
**Last Updated:** 2026-02-01  
**Maintained By:** Platform Engineering Team
