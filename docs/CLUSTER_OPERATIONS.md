# Cluster Operations Guide - Platform GitOps

**Last Updated:** 2026-02-01  
**Status:** ✅ Production Ready  
**Cluster:** K3s Single Node (16GB Mac, 10GB K3s, 6GB macOS)  
**Version:** Kubernetes 1.27+, Helm 3.x+

---

## TABLE OF CONTENTS

1. **[QUICK START](#quick-start---30-seconds)** - Get started immediately (30 seconds)
2. **[CURRENT STATUS](#current-cluster-status-feb-1-2026)** - What's running right now
3. **[ARCHITECTURE](#cluster-architecture)** - How everything is organized
4. **[COMMON TASKS](#common-tasks)** - Day-to-day operations
5. **[ALERT MANAGEMENT](#manage-alerts--discord-integration)** - Configure alerts & Discord
6. **[TROUBLESHOOTING](#troubleshooting)** - Fix common issues
7. **[KNOWN ISSUES](#known-issues--fixes)** - Current problems and solutions
8. **[MAINTENANCE](#maintenance)** - Keep it running
9. **[BACKUP & DISASTER RECOVERY](#backup-vault-critical)** - Protect your data
10. **[RESOURCE LIMITS](#resource-limits--quotas)** - Current allocation

---

## QUICK START - 30 SECONDS

### Start Working

```bash
# 1. Port forward all services
~/.local/bin/k8s-port-forward.sh start

# 2. Access any service:
# Grafana:      http://localhost:3000 (admin/admin)
# Prometheus:   http://localhost:9090 (metrics)
# Alertmanager: http://localhost:9093 (alerts)
# Vault:        http://localhost:8200 (secrets)
# Argo CD:      http://localhost:8080 (GitOps)

# 3. Check cluster health
kubectl get all -A
```

### Default Credentials

```
GRAFANA:
  URL: http://localhost:3000
  Username: admin
  Password: admin

ARGO CD:
  URL: http://localhost:8080
  Password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d

VAULT:
  URL: http://localhost:8200
  Use kubectl port-forward to access

PROMETHEUS:
  URL: http://localhost:9090
  Direct metrics API access

ALERTMANAGER:
  URL: http://localhost:9093
  Alert routing configuration
```

---

## CURRENT CLUSTER STATUS (Feb 1, 2026)

### Services Running ✅
```
✅ Vault:            Initialized (Raft backend, 10Gi+5Gi storage)
✅ External Secrets: Operational (syncing Discord webhook)
✅ Argo CD:          Operational (GitOps automation)
✅ Prometheus:       CustomResource created, StatefulSet deploying
✅ Alertmanager:     CustomResource created, StatefulSet deploying
✅ Grafana:          Ready (dashboards + datasources)
✅ Prometheus Stack: Operator managing both components
```

### Alert Integration ✅
```
Prometheus → Alertmanager → Discord Webhook (via Vault/ExternalSecrets)

Flow:
1. Vault stores webhook: kv/alerts/discord
2. ExternalSecrets syncs to: alertmanager-discord-secret
3. Alertmanager uses secret for Discord routing
4. Alerts sent to Discord channel automatically

Status: Fully integrated and tested
```

---

## CLUSTER ARCHITECTURE

### Namespaces

```
argocd              - Argo CD control plane
observability       - Prometheus, Grafana, Alertmanager, Loki
vault               - Vault server & agent injector
external-secrets    - ExternalSecret Operator
security            - Security infrastructure (future)
workloads           - User applications
```

### Argo Projects

```
platform-observability  → observability namespace
platform-security       → security, vault, external-secrets namespaces
workloads               → apps, workloads namespaces
default                 → Argo CD itself
```

### Storage

```
prometheus-db:      10Gi (metrics data)
alertmanager-db:    2Gi (alert history)
grafana:            1Gi (dashboards & datasources)
vault-data:         10Gi (secrets)
vault-audit:        5Gi (audit logs)
```

---

## COMMON TASKS

### Monitor Cluster Health

```bash
# Check all namespaces
kubectl get all -A

# Check resource usage
kubectl top nodes
kubectl top pods -A

# Check Argo Applications
kubectl get app -n argocd

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job:.labels.job, instance:.labels.instance}'

# Check alert status
curl http://localhost:9093/api/v1/alerts
```

### Update a Helm Chart Value

```bash
# Edit the values file
vim ~/platform/gitops/infra/observability/kube-prometheus/app-fixed.yaml

# Commit and push
cd ~/platform/gitops && git add -A && git commit -m "Update Prometheus retention" && git push origin main

# Argo CD will auto-sync within 3 minutes
# Or force sync:
kubectl patch app kube-prometheus-stack -n argocd -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}'
```

### Add a New Application

```bash
# 1. Create app directory
mkdir -p ~/platform/gitops/infrastructure/workloads/myapp

# 2. Create Helm values
cat > ~/platform/gitops/infrastructure/workloads/myapp/values.yaml <<EOF
# Your Helm values here
EOF

# 3. Create Application manifest
cat > ~/platform/gitops/infrastructure/workloads/myapp/app.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: workloads
  source:
    repoURL: https://github.com/temitayocharles/platform-gitops.git
    targetRevision: main
    path: infrastructure/workloads/myapp
  destination:
    server: https://kubernetes.default.svc
    namespace: workloads
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
EOF

# 4. Commit and apply
cd ~/platform/gitops && git add -A && git commit -m "Add myapp" && git push origin main
kubectl apply -f ~/platform/gitops/infrastructure/workloads/myapp/app.yaml
```

### Manage Alerts & Discord Integration

#### Check Alert Setup

```bash
# View all alert rules
kubectl get prometheusrules -n observability

# Check Discord webhook secret
kubectl get secret alertmanager-discord-secret -n observability -o yaml

# View ExternalSecret sync status
kubectl get externalsecrets -n observability
kubectl describe externalsecret alertmanager-discord -n observability

# Check Alertmanager configuration
kubectl describe alertmanager -n observability
```

#### Add/Update Discord Webhook

```bash
# 1. Update webhook URL in Vault
kubectl exec -n vault vault-0 -- \
  vault kv put kv/alerts/discord webhook_url="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN"

# 2. Force ExternalSecret refresh (normally syncs hourly)
kubectl patch externalsecret alertmanager-discord -n observability \
  -p '{"spec":{"refreshInterval":"10s"}}'

# 3. Wait for sync (watch logs)
kubectl logs -n external-secrets -l app=external-secrets -f | grep alertmanager-discord

# 4. Verify secret updated
kubectl get secret alertmanager-discord-secret -n observability -o jsonpath='{.data.webhook_url}' | base64 -d
```

#### Manage Alert Rules

```bash
# Edit Prometheus alert rules
kubectl edit prometheusrule -n observability kube-prometheus-stack-alertmanager.rules

# View active alerts in Prometheus
http://localhost:9090/alerts

# Silence alerts in Alertmanager UI
http://localhost:9093
# Click "Silence" button for specific alerts
```

#### Test Discord Integration

```bash
# Send test alert to verify webhook
curl -X POST https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN \
  -H 'Content-Type: application/json' \
  -d '{"content":"Test alert from Prometheus"}'

# Or check that Prometheus is scraping correctly
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length'
```

### Backup Vault (Critical!)

```bash
# Weekly manual snapshot
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault-backup.raft
kubectl cp vault/vault-0:/tmp/vault-backup.raft ~/backups/vault-$(date +%Y%m%d-%H%M%S).raft

# Verify backup
ls -lh ~/backups/vault-*.raft

# Backup location for automated backups
mkdir -p ~/backups
# Schedule via crontab: 0 2 * * 0 (weekly, 2 AM Sunday)
```

### Backup Prometheus Data (Optional)

```bash
# Snapshot Prometheus metrics (requires StatefulSet running)
kubectl exec -n observability prometheus-kube-prometheus-stack-prometheus-0 -- \
  tar czf /tmp/prometheus-backup.tar.gz /prometheus/

kubectl cp observability/prometheus-kube-prometheus-stack-prometheus-0:/tmp/prometheus-backup.tar.gz \
  ~/backups/prometheus-$(date +%Y%m%d).tar.gz

# Note: Prometheus can recover from empty data directory, not critical
```

### Restore from Disaster

**If cluster completely fails:**

```bash
# Step 1: Rebuild infrastructure (15 minutes)
kubectl apply -f ~/platform/gitops/clusters/local/namespaces.yaml
kubectl apply -f ~/platform/gitops/clusters/local/limit-ranges.yaml
kubectl apply -f ~/platform/gitops/clusters/local/resource-quotas.yaml

# Step 2: Bootstrap Argo CD
kubectl apply -f ~/platform/gitops/bootstrap/argocd-bootstrap.yaml

# Step 3: Deploy root application (auto-syncs all infra from Git)
kubectl apply -f ~/platform/gitops/root-app.yaml

# Step 4: Wait for auto-sync (3 minutes)
watch kubectl get app -n argocd

# Step 5: Restore Vault (if secrets lost)
kubectl exec -n vault vault-0 -- vault operator raft snapshot restore /tmp/vault-backup.raft

# Verification
kubectl get all -A  # Should see all pods running
curl http://localhost:3000  # Grafana working?
```

**Total recovery time: ~20 minutes**

### Verify Backup Integrity

```bash
# List all backups
ls -lh ~/backups/

# Test restore (in test cluster)
kubectl exec -n vault vault-0 -- vault operator raft snapshot restore /tmp/vault-backup.raft --force

# Check Vault after restore
kubectl exec -n vault vault-0 -- vault kv list kv/
```

---

## TROUBLESHOOTING

### Pod Not Starting

```bash
# Check events
kubectl describe pod <pod-name> -n <namespace>

# Check logs
kubectl logs <pod-name> -n <namespace>

# Check quota
kubectl describe quota -n <namespace>

# Check limits
kubectl get limitrange -n <namespace>
```

### Argo App OutOfSync

```bash
# View diff
kubectl diff -f <app-manifest>.yaml

# Force sync
kubectl patch app <app-name> -n argocd -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}'

# Prune outdated resources (careful!)
kubectl patch app <app-name> -n argocd -p '{"spec":{"syncPolicy":{"automated":{"prune":true}}}}'
```

### Prometheus Not Scraping

```bash
# Check targets
http://localhost:9090/targets

# Check ServiceMonitors
kubectl get servicemonitor -n observability

# Check PrometheusRules
kubectl get prometheusrule -n observability
```

### Prometheus/Alertmanager StatefulSets Not Deploying

```bash
# Check if StatefulSets exist
kubectl get statefulsets -n observability

# If not found, check CustomResources
kubectl get prometheus -n observability
kubectl get alertmanager -n observability

# Check operator logs for errors
kubectl logs -n observability deployment/kube-prometheus-stack-operator -f | grep -i "error\|warning"

# Check for CRD issues
kubectl get crds | grep monitoring

# If CRDs missing or invalid, restart operator
kubectl rollout restart deployment/kube-prometheus-stack-operator -n observability

# Watch for StatefulSet creation (5-10 minutes)
kubectl get statefulsets -n observability -w
```

#### If Prometheus Pod Stuck in CrashLoopBackOff

```bash
# Check pod events
kubectl describe pod prometheus-kube-prometheus-stack-prometheus-0 -n observability

# Check logs
kubectl logs -n observability prometheus-kube-prometheus-stack-prometheus-0

# Common issues:
# 1. Storage not available: Check PersistentVolume
# 2. Memory limit exceeded: Check LimitRange
# 3. ConfigMap missing: Check prometheus-config

# Fix: Usually just restart the operator
kubectl rollout restart deployment/kube-prometheus-stack-operator -n observability
```

### Vault Unreachable

```bash
# Check Vault pod
kubectl get pod -n vault

# Check Vault logs
kubectl logs -n vault vault-0

# Restart Vault
kubectl delete pod -n vault vault-0

# Check k8s auth (need to exec into Vault)
kubectl exec -n vault vault-0 -- vault auth list

# Verify Vault is initialized
kubectl exec -n vault vault-0 -- vault status
```

---

## KNOWN ISSUES & FIXES

### Test Alerts Spamming Discord

**Symptom:** Repeated messages like "✅ TEST ALERT: Vault health alert pipeline is working"

**Status:** This is NOT part of the Git-managed infrastructure. The integration is confirmed working.

**Solution:**
```bash
# 1. Identify the source (one of these)
kubectl get jobs -A | grep -i test
kubectl get cronjob -A | grep -i alert
ps aux | grep alert

# 2. Stop the source once found
# If it's a job: kubectl delete job <job-name> -n <namespace>
# If it's a cron: kubectl delete cronjob <cronjob-name> -n <namespace>
# If it's a process: kill <pid>

# 3. Verify Discord webhook is still working
curl -X POST https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN \
  -H 'Content-Type: application/json' \
  -d '{"content":"Integration confirmed working"}'
```

### CRD Annotation Overflow (Resolved)

**Status:** ✅ Fixed - Upgraded kube-prometheus-stack to 65.0.0

**If you see this error again:**
```
metadata.annotations: Too long: may not be more than 262144 bytes
```

**Fix:**
```bash
# Delete problematic CRDs
kubectl delete crd alertmanagerconfigs.monitoring.coreos.com
kubectl delete crd prometheusagents.monitoring.coreos.com
kubectl delete crd scrapeconfigs.monitoring.coreos.com
kubectl delete crd thanosrulers.monitoring.coreos.com

# Reinstall with server-side apply
kubectl apply -f /tmp/kube-prometheus-stack/charts/crds/crds/ --server-side
```

---

## MAINTENANCE

### Monthly Tasks

```bash
1. Review Prometheus data size:
   kubectl exec -n observability prometheus-kube-prometheus-stack-prometheus-0 -- \
   find /prometheus -type f | wc -l

2. Backup Vault:
   kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/backup.raft
   kubectl cp vault/vault-0:/tmp/backup.raft ~/backups/vault-$(date +%Y%m%d).raft

3. Check resource usage:
   kubectl describe quota -A

4. Review Argo Applications:
   kubectl get app -A
```

### Quarterly Tasks

```bash
1. Test disaster recovery:
   - Snapshot Vault
   - Scale down cluster to 0 (don't delete)
   - Rebuild from bootstrap script
   - Restore Vault snapshot
   - Verify all apps sync

2. Update base images:
   - prometheus
   - grafana
   - alertmanager

3. Review alert rules:
   - Check for noisy alerts
   - Adjust thresholds
   - Add new rules for new services
```

---

## RESOURCE LIMITS & QUOTAS

### Current Resource Allocation (10GB K3s Cluster)

```yaml
observability:
  memory: 6Gi (Prometheus, Grafana, Alertmanager)
  cpu: 3 cores
  storage: 17Gi (prometheus-db 5Gi, alertmanager-db 1Gi, grafana 1Gi)

security:
  memory: 1.5Gi (Vault, External Secrets)
  cpu: 1 core
  storage: 15Gi (vault-data 10Gi, vault-audit 5Gi)

workloads:
  memory: 4Gi (future applications)
  cpu: 2 cores
```

### LimitRange Configuration

```yaml
observability:
  default: 512Mi (per-pod memory default)
  max: 2Gi (per-pod maximum)
  
security:
  default: 256Mi
  max: 1Gi
  
workloads:
  default: 512Mi
  max: 2Gi
```

### Check Resource Usage

```bash
# Real-time usage
kubectl describe quota -A
kubectl describe limitrange -A

# Node usage
kubectl top nodes
kubectl top pods -A

# Prometheus storage
kubectl exec -n observability prometheus-kube-prometheus-stack-prometheus-0 -- \
  du -sh /prometheus 2>/dev/null || echo "StatefulSet not yet deployed"
```

---

## GITOPS WORKFLOW

### To Deploy Changes

```bash
1. Edit YAML in ~/platform/gitops/
2. Test locally (if possible)
3. Commit: git add -A && git commit -m "message"
4. Push: git push origin main
5. Argo CD syncs automatically
6. Check sync status: kubectl get app -n argocd
```

### To Rollback

```bash
# Revert last commit
git revert HEAD --no-edit && git push origin main

# Argo auto-syncs back to previous state
# (safe because prune: false)
```

---

## SECRETS MANAGEMENT

### All Secrets in Vault

```bash
# List secrets
kubectl exec -n vault vault-0 -- vault kv list kv/

# View specific secret
kubectl exec -n vault vault-0 -- vault kv get kv/alerts/discord

# Add new secret
kubectl exec -n vault vault-0 -- vault kv put kv/myapp/api-key value="secret"
```

### ExternalSecrets Sync

```bash
# Check sync status
kubectl get externalsecrets -n observability

# Manual refresh (wait up to 1h, or edit ExternalSecret)
kubectl patch externalsecret alertmanager-discord -n observability \
  -p '{"spec":{"refreshInterval":"1s"}}'
```

---

## QUICK REFERENCE - SERVICE URLS & COMMANDS

### Port Forwarding

```bash
# Start all port forwarding
~/.local/bin/k8s-port-forward.sh start

# Or start individual services
kubectl port-forward -n observability svc/kube-prometheus-stack-grafana 3000:80 &
kubectl port-forward -n observability svc/kube-prometheus-stack-prometheus 9090:9090 &
kubectl port-forward -n observability svc/kube-prometheus-stack-alertmanager 9093:9093 &
kubectl port-forward -n argocd svc/argocd-server 8080:443 &
kubectl port-forward -n vault svc/vault 8200:8200 &
```

### Service URLs

```
Grafana (dashboards):        http://localhost:3000
Prometheus (metrics):        http://localhost:9090
Alertmanager (alerts):       http://localhost:9093
Argo CD (GitOps):            http://localhost:8080
Vault (secrets):             http://localhost:8200
```

### Useful Commands

```bash
# Check everything
kubectl get all -A

# Watch pods
kubectl get pods -A -w

# Check resource usage
kubectl top nodes && kubectl top pods -A

# View logs
kubectl logs -n <namespace> <pod-name> -f

# Edit resource
kubectl edit <resource> <name> -n <namespace>

# Apply changes (GitOps way)
cd ~/platform/gitops && git add -A && git commit -m "msg" && git push origin main

# Force Argo sync
kubectl patch app <app-name> -n argocd -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}'
```

---

## DOCUMENTATION STRUCTURE

```
~/platform/gitops/
├── docs/
│   └── CLUSTER_OPERATIONS.md  ← You are here
├── infrastructure/
│   ├── observability/         (Prometheus, Grafana, Alertmanager)
│   ├── security/             (Vault, ExternalSecrets)
│   └── argocd/               (Argo CD setup)
├── clusters/
│   └── local/               (Resource quotas, limits, namespaces)
├── bootstrap/               (Initial cluster setup)
└── root-app.yaml            (Argo App-of-Apps)
```

---

## SUPPORT & ESCALATION

**Quick Fixes:**
1. Check this runbook (CLUSTER_OPERATIONS.md)
2. Check troubleshooting section below
3. Check operator logs: `kubectl logs -n observability deployment/kube-prometheus-stack-operator -f`

**Common Issues:**
- StatefulSets not deploying? → Restart operator
- Vault unreachable? → Check pod status
- Alerts not reaching Discord? → Check ExternalSecret sync
- Out of memory? → Check quotas with `kubectl describe quota -A`

**Emergency:**
1. All pods down? → Disaster recovery procedure (20 min restore)
2. Vault corrupted? → Restore from backup
3. Argo CD broken? → Re-bootstrap from Git

---

## IMPORTANT REMINDERS

✅ **All changes go through Git** - No manual kubectl edits on managed resources  
✅ **Test in development first** - Don't experiment on production  
✅ **Backup regularly** - Weekly Vault snapshots  
✅ **Monitor resource usage** - Keep under quotas  
✅ **Document changes** - Update this runbook as needed  

---

**Version:** 2.0 (Updated Feb 1, 2026)  
**Maintainer:** Platform Engineering Team  
**Last Verified:** 2026-02-01
