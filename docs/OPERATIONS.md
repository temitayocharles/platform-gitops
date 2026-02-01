# Operations Guide - Daily Platform Management

**Version:** 2.0 (Fresh)  
**Last Updated:** 2026-02-01  
**Purpose:** Detailed procedures for daily platform operations  
**Audience:** Platform operators and engineers

---

## Table of Contents

1. **[Startup & Access](#startup--access)** - Getting started each session
2. **[Health Monitoring](#health-monitoring)** - Checking system status
3. **[Configuration Changes](#configuration-changes)** - Deploying via Git
4. **[Alert Management](#alert-management)** - Discord webhook and rules
5. **[Backup Procedures](#backup-procedures)** - Protecting critical data
6. **[Routine Maintenance](#routine-maintenance)** - Weekly/monthly tasks
7. **[Quick Reference](#quick-reference)** - Common commands

---

## Startup & Access

### Before You Start Each Session

```bash
# 1. Port forward services (runs in background)
~/.local/bin/k8s-port-forward.sh start

# Wait 5 seconds for ports to open, then verify:
sleep 5

# 2. Test connectivity
curl -s http://localhost:3000 > /dev/null && echo "✓ Grafana ready" || echo "✗ Grafana not ready"
curl -s http://localhost:9090 > /dev/null && echo "✓ Prometheus ready" || echo "✗ Prometheus not ready"

# 3. Get Argo CD password (save it or create alias)
ARGO_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d)
echo "Argo CD password: $ARGO_PASSWORD"
```

### Access Each Service

| Service | Port | Login | Purpose |
|---------|------|-------|---------|
| Grafana | 3000 | admin/admin | View dashboards, create graphs |
| Prometheus | 9090 | - | Query metrics, view targets |
| Alertmanager | 9093 | - | View alerts, manage silences |
| Argo CD | 8080 | admin/[password] | Manage applications |
| Vault | 8200 | - | Manage secrets |

### Verify Cluster is Healthy

```bash
# All pods running?
kubectl get pods -A --field-selector=status.phase!=Running

# No CrashLoops?
kubectl get pods -A | grep -i crash

# All applications synced?
kubectl get app -n argocd --field-selector=status.operationState.finishedAt=""

# Result: Should be empty (no issues)
```

---

## Health Monitoring

### Daily Health Check (5 minutes)

Run this each day:

```bash
#!/bin/bash
# Save as: ~/scripts/daily-check.sh

echo "=== CLUSTER HEALTH CHECK ===" 
echo ""

echo "1. Pod Status"
RUNNING=$(kubectl get pods -A --field-selector=status.phase=Running | wc -l)
TOTAL=$(kubectl get pods -a | tail -1 | awk '{print $1}')
echo "   Running: $RUNNING / Total: $TOTAL"

echo ""
echo "2. Resource Usage"
kubectl describe quota -A | grep -E "Name:|Used|Quota" | head -20

echo ""
echo "3. Argo Applications"
kubectl get app -n argocd --no-headers | awk '{print $1, $2}'

echo ""
echo "4. Recent Errors (last 10 minutes)"
kubectl get events -A --sort-by='.lastTimestamp' | grep -E "Error|Warning" | tail -5 || echo "   No errors"

echo ""
echo "5. Resource Top Users"
kubectl top pods -A --sort-by=memory | head -6
```

Run it:
```bash
chmod +x ~/scripts/daily-check.sh
~/scripts/daily-check.sh
```

### Check Specific Components

#### Prometheus Status

```bash
# Is it running?
kubectl get statefulset -n observability prometheus-kube-prometheus-stack-prometheus

# Is it scraping?
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length'
# Should return > 0

# Recent metrics?
curl 'http://localhost:9090/api/v1/query?query=up' | jq '.data.result | length'
# Should return > 0
```

#### Alertmanager Status

```bash
# Is it running?
kubectl get statefulset -n observability alertmanager-kube-prometheus-stack-alertmanager

# Can it reach Discord?
kubectl logs -n observability alertmanager-kube-prometheus-stack-alertmanager-0 | grep -i discord | tail -5

# Current configuration?
kubectl exec -n observability alertmanager-kube-prometheus-stack-alertmanager-0 -- \
  cat /etc/alertmanager/config.yml | head -30
```

#### Grafana Status

```bash
# Is it running?
kubectl get pod -n observability -l app.kubernetes.io/name=grafana

# Can you access it?
curl -s http://localhost:3000/api/health | jq '.database'
# Should return: "ok"

# Dashboards loaded?
curl -s http://localhost:3000/api/search?query=&tag=&type=dash-db | jq '. | length'
# Should return > 0
```

#### Argo CD Status

```bash
# Is it running?
kubectl get deployment -n argocd argocd-server

# All applications synced?
kubectl get app -n argocd -o jsonpath='{.items[*].status.sync.status}' | grep -o Synced | wc -l

# Any applications failing?
kubectl get app -n argocd -o jsonpath='{.items[?(@.status.health.status=="Healthy")].metadata.name}' | wc -w
```

#### Vault Status

```bash
# Is it running?
kubectl get pod -n vault vault-0

# Is it initialized and unsealed?
kubectl exec -n vault vault-0 -- vault status | grep -E "Sealed|Initialized"

# Can you list secrets?
kubectl exec -n vault vault-0 -- vault kv list kv/

# Most critical secret present?
kubectl exec -n vault vault-0 -- vault kv get kv/alerting/discord
```

---

## Configuration Changes

### Standard Deployment Flow

All infrastructure changes go through Git. This ensures auditability and reproducibility.

#### Step 1: Make Changes Locally

```bash
# Example: Increase Prometheus retention
vim infrastructure/observability/prometheus/values.yaml

# Find: retention: 15d
# Change to: retention: 30d

# Or: Change alert rule
vim infrastructure/observability/prometheus/custom-rules.yaml

# Or: Update Grafana dashboard
vim infrastructure/observability/grafana/values.yaml
```

#### Step 2: Test Changes (Optional)

```bash
# For Helm changes, preview what will deploy:
cd infrastructure/observability/prometheus

# If using helmfile (optional):
helmfile diff

# Or inspect the values
cat values.yaml | grep -A 5 "retention:"
```

#### Step 3: Commit to Git

```bash
cd ~/platform/gitops

# Review what you're changing
git diff infrastructure/observability/prometheus/values.yaml

# Stage changes
git add infrastructure/observability/prometheus/values.yaml

# Commit with clear message
git commit -m "Increase Prometheus retention to 30 days

Rationale: Store more historical data for analysis
Affected: observability namespace
Approval: Self-owned platform"

# Push to main
git push origin main
```

#### Step 4: Verify Argo CD Deployment

```bash
# Argo will sync within 3 minutes
watch kubectl get app -n argocd

# When synced, verify the change
kubectl get statefulset -n observability prometheus-kube-prometheus-stack-prometheus \
  -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -i retention

# Check Prometheus is still running
kubectl logs -n observability prometheus-kube-prometheus-stack-prometheus-0 | grep "retention" | head -1
```

#### Step 5: Rollback (if needed)

```bash
# If change breaks something, revert in Git
cd ~/platform/gitops

git revert HEAD --no-edit
git push origin main

# Argo auto-syncs back to previous state (safe because prune: false)

# Monitor
watch kubectl get app -n argocd
```

### Deploying Multiple Changes

```bash
# Example: Update Prometheus AND Grafana in one commit

vim infrastructure/observability/prometheus/values.yaml  # Change 1
vim infrastructure/observability/grafana/values.yaml    # Change 2

git add infrastructure/observability/prometheus/values.yaml
git add infrastructure/observability/grafana/values.yaml
git commit -m "Update observability stack

- Increase Prometheus retention to 30 days
- Update Grafana to 10.2.1
- Add new dashboard provisioning"

git push origin main

# Both deploy together in next Argo sync
```

---

## Alert Management

### Current Alert Setup

```
Prometheus Rules (Git) → Alertmanager (routes) → Discord (webhook from Vault)
```

### Check if Alerts Reach Discord

```bash
# 1. Verify webhook is in Vault
kubectl exec -n vault vault-0 -- vault kv get kv/alerting/discord

# 2. Verify secret is synced to Kubernetes
kubectl get secret alertmanager-discord-secret -n observability -o yaml | grep DISCORD_WEBHOOK_URL

# 3. Verify Alertmanager has the config
kubectl exec -n observability alertmanager-kube-prometheus-stack-alertmanager-0 -- \
  cat /etc/alertmanager/config.yml | grep -A 5 "discord"

# 4. Send test message
WEBHOOK=$(kubectl exec -n vault vault-0 -- vault kv get -field=webhook_url kv/alerting/discord)
curl -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Test alert from Prometheus - integration working!"}'

# 5. Check Discord channel - you should see the message
```

### Update Discord Webhook URL

```bash
# Get new webhook URL from Discord channel → Channel Settings → Integrations → Webhooks

# 1. Update Vault (single source of truth)
kubectl exec -n vault vault-0 -- \
  vault kv put kv/alerting/discord \
  webhook_url="https://discord.com/api/webhooks/YOUR_NEW_ID/YOUR_NEW_TOKEN"

# 2. Force ExternalSecret to sync immediately (normally 1 hour)
kubectl patch externalsecret alertmanager-discord -n observability \
  -p '{"spec":{"refreshInterval":"10s"}}'

# 3. Wait for sync
sleep 30

# 4. Verify secret updated
kubectl get secret alertmanager-discord-secret -n observability -o jsonpath='{.data.DISCORD_WEBHOOK_URL}' | base64 -d

# 5. Restart Alertmanager to use new webhook
kubectl rollout restart statefulset alertmanager-kube-prometheus-stack-alertmanager -n observability

# 6. Verify it's running
kubectl get statefulset -n observability alertmanager-kube-prometheus-stack-alertmanager
```

### Add Custom Alert Rules

Alert rules live in Git. All changes go through version control.

```bash
# 1. Create/edit alert rules file
vim infrastructure/observability/prometheus/custom-rules.yaml

# Example: Alert when pod memory exceeds 90%
cat >> infrastructure/observability/prometheus/custom-rules.yaml <<'EOF'
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: custom-high-memory
  namespace: observability
spec:
  groups:
  - name: custom-memory
    interval: 30s
    rules:
    - alert: PodHighMemory
      expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
      for: 5m
      labels:
        severity: warning
        team: platform
      annotations:
        summary: "Pod {{ $labels.pod }} high memory usage"
        description: "Pod {{ $labels.pod }} memory at {{ $value | humanizePercentage }}"
EOF

# 2. Commit
git add infrastructure/observability/prometheus/custom-rules.yaml
git commit -m "Add alert for pods exceeding 90% memory"
git push origin main

# 3. Verify Prometheus loads it
sleep 30
curl http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name=="custom-memory")'

# 4. Test it works (fill a pod with data, watch alert fire)
```

### Silence Alerts (Temporary)

```bash
# Via Alertmanager UI
# 1. Open http://localhost:9093
# 2. Click alert
# 3. Click "Silence"
# 4. Set duration
# 5. Add comment (required)

# OR via API
curl -X POST http://localhost:9093/api/v2/silences \
  -H 'Content-Type: application/json' \
  -d '{
    "matchers": [
      {"name": "alertname", "value": "NodeDown", "isRegex": false}
    ],
    "startsAt": "2026-02-01T00:00:00Z",
    "endsAt": "2026-02-02T00:00:00Z",
    "comment": "Maintenance window"
  }'

# Verify silence was created
curl http://localhost:9093/api/v2/silences | jq '.[] | {id, comment, matchers}'
```

### View Active Alerts

```bash
# Via Prometheus
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | {state, labels, annotations}'

# Via Alertmanager
curl http://localhost:9093/api/v1/alerts | jq '.[] | {labels, annotations}'

# In Grafana
# Home → Alerts & IRM → Alert list
```

---

## Backup Procedures

### Vault Backup (CRITICAL!)

Vault stores all secrets. Backup is non-negotiable.

```bash
# 1. Create backup directory
mkdir -p ~/backups/vault/$(date +%Y/%m)

# 2. Take snapshot
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft

# 3. Copy out
kubectl cp vault/vault-0:/tmp/vault.raft ~/backups/vault/$(date +%Y/%m)/vault-$(date +%Y%m%d-%H%M%S).raft

# 4. Verify backup
ls -lh ~/backups/vault/$(date +%Y/%m)/ | head -3

# 5. Keep backup offsite or encrypted
# (In production, sync to S3, cloud storage, etc.)
```

### Automated Daily Backups

```bash
# Add to crontab
crontab -e

# Add this line:
0 2 * * * /home/temitayocharles/scripts/backup-vault-daily.sh
```

Create the script:

```bash
#!/bin/bash
# ~/scripts/backup-vault-daily.sh

set -e

DATE=$(date +%Y/%m/%d)
mkdir -p ~/backups/vault/$DATE

kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ~/backups/vault/$DATE/vault-$(date +%H%M%S).raft

# Keep last 30 days
find ~/backups/vault -type f -mtime +30 -delete

echo "Vault backup completed: ~/backups/vault/$DATE/"
```

Make it executable:
```bash
chmod +x ~/scripts/backup-vault-daily.sh
```

### Test Backup Restoration

Do this quarterly to verify backups work:

```bash
# 1. Create test Vault pod (don't use production!)
kubectl run vault-test -n vault --image=vault:latest --rm -it -- sh

# 2. Init and unseal test Vault (follow prompts)
vault operator init
vault operator unseal

# 3. Copy backup in
kubectl cp ~/backups/vault/latest/vault.raft vault/vault-test:/tmp/vault-test.raft

# 4. Restore
kubectl exec vault-test -n vault -- vault operator raft snapshot restore /tmp/vault-test.raft

# 5. Verify secrets are there
kubectl exec vault-test -n vault -- vault kv list kv/

# 6. Delete test pod
kubectl delete pod vault-test -n vault
```

---

## Routine Maintenance

### Daily (5 minutes)

```bash
# Run health check
~/scripts/daily-check.sh

# Review recent errors
kubectl get events -A --sort-by='.lastTimestamp' | tail -20

# Verify all apps synced
kubectl get app -n argocd | grep -v Synced
```

### Weekly (30 minutes)

```bash
# 1. Backup Vault
~/scripts/backup-vault-daily.sh

# 2. Check resource usage
kubectl describe quota -A
kubectl top pods -n observability | sort -k3 -nr

# 3. Review applications
kubectl get app -n argocd -o wide

# 4. Check for pod restarts
kubectl get pods -A --sort-by='.status.containerStatuses[0].restartCount' | tail -10

# 5. Verify Argo CD itself is healthy
kubectl get pod -n argocd -l app.kubernetes.io/name=argocd-server

# 6. Test one manual change
# (Update a non-critical value in Git, verify Argo syncs)
```

### Monthly (1 hour)

```bash
# 1. Full backup
mkdir -p ~/backups/full-$(date +%Y%m%d)
cd ~/backups/full-$(date +%Y%m%d)

# Backup Vault
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault.raft
kubectl cp vault/vault-0:/tmp/vault.raft ./vault.raft

# Export all resources
kubectl get all -A -o yaml > all-resources.yaml

# Export Git history
cd ~/platform/gitops && git log --oneline -100 > /path/to/backup/git-log.txt

# 2. Review and optimize quotas
kubectl describe quota -A

# 3. Update alert rules for accuracy
kubectl get prometheusrule -n observability -o yaml | less

# 4. Check certificate expiration
kubectl get certificate -A 2>/dev/null || echo "No cert-manager installed"

# 5. Review and update this documentation
# Ensure procedures are still accurate
```

### Quarterly (2-3 hours)

```bash
# 1. FULL DISASTER RECOVERY TEST
#    (Do not delete cluster, just test rebuild procedure)

# A. Take fresh backup
~/scripts/backup-vault-daily.sh

# B. Scale down cluster to 0 (keep storage)
kubectl scale deployment -n argocd --all --replicas=0
kubectl scale statefulset -n vault --all --replicas=0
# ... (scale all down)

# C. Rebuild from bootstrap
kubectl apply -f bootstrap/argocd-bootstrap.yaml
kubectl apply -f clusters/local/namespaces.yaml
kubectl apply -f infrastructure/argocd/root-app.yaml

# D. Verify everything comes back
watch kubectl get app -n argocd

# E. Restore Vault
kubectl cp ~/backups/vault/latest/vault.raft vault/vault-0:/tmp/vault.raft
kubectl exec -n vault vault-0 -- vault operator raft snapshot restore /tmp/vault.raft

# F. Verify all secrets restored
kubectl exec -n vault vault-0 -- vault kv list kv/

# 2. Performance review
# Review metrics in Grafana for bottlenecks

# 3. Documentation review
# Update README, OPERATIONS, and DISASTER_RECOVERY docs

# 4. Team process review (if multi-team)
# Review RBAC, approval processes, etc.
```

---

## Quick Reference

### Common Commands

```bash
# Health checks
kubectl get pods -A                    # All pods running?
kubectl describe quota -A              # Resources available?
kubectl get app -n argocd              # Apps synced?

# Deploy changes
cd ~/platform/gitops
git add -A && git commit -m "message" && git push origin main

# Check specific services
kubectl logs -n observability prometheus-kube-prometheus-stack-prometheus-0 | tail -20
kubectl logs -n observability alertmanager-kube-prometheus-stack-alertmanager-0 | tail -20
kubectl logs -n external-secrets -l app=external-secrets -f

# Vault operations
kubectl exec -n vault vault-0 -- vault status
kubectl exec -n vault vault-0 -- vault kv list kv/
kubectl exec -n vault vault-0 -- vault kv get kv/alerting/discord

# Argo operations
kubectl get app -n argocd
kubectl get app <app-name> -n argocd -o yaml | grep -A 5 "syncPolicy"

# Troubleshooting
kubectl describe pod <pod-name> -n <namespace>
kubectl logs -n <namespace> <pod-name> --previous
kubectl top pods -n <namespace>
```

### When Cluster is Stuck

```bash
# 1. Check what's stuck
kubectl get pods -A | grep -E "Pending|CrashLoop"

# 2. Get details
kubectl describe pod <stuck-pod> -n <namespace>

# 3. Check resources
kubectl describe quota -n <namespace>
kubectl describe limitrange -n <namespace>

# 4. Delete and let Argo recreate
kubectl delete pod <stuck-pod> -n <namespace>

# 5. Monitor recreation
watch kubectl get pod <stuck-pod> -n <namespace>
```

---

## Summary

**Daily Operations:**
- Run health check
- Monitor alerts
- Deploy changes via Git

**Weekly:**
- Backup Vault
- Review resource usage
- Check application status

**Monthly:**
- Full backup
- Optimize quotas
- Update documentation

**Quarterly:**
- Disaster recovery test
- Performance review

**Key Principle:**
All changes go through Git. No manual kubectl edits on managed resources.

---

**Version:** 2.0 (Fresh)  
**Last Updated:** 2026-02-01  
**Status:** Ready for Production
