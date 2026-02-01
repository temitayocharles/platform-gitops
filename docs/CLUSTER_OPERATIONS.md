# Cluster Operations Guide - Platform GitOps

**Last Updated:** 2026-02-01  
**Status:** Production Ready  
**Cluster:** K3s Single Node  

---

## QUICK START

### Access Services

```bash
# Start port forwarding
~/.local/bin/k8s-port-forward.sh start

# Or use the repo script
cd ~/platform/gitops && ./clusters/local/port-forward.sh start
```

### Default Credentials

```
Grafana:  http://localhost:3000
          Username: admin
          Password: admin

Argo CD:  http://localhost:8080
          (Get password from: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)

Prometheus: http://localhost:9090 (metrics queries)
Alertmanager: http://localhost:9093 (alerts)
Vault: http://localhost:8200 (secrets management)
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

### Manage Alerts

```bash
# Check alert rules
kubectl get prometheusrules -n observability

# Edit alert rules
kubectl edit prometheusrule -n observability kube-prometheus-stack-alertmanager.rules

# Check Discord routing config
kubectl get secret alertmanager-discord-secret -n observability -o jsonpath='{.data.webhook_url}' | base64 -d

# Silence an alert in Alertmanager UI
# http://localhost:9093 → Silence button
```

### Backup Vault

```bash
# Manual snapshot
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/vault-backup.raft
kubectl cp vault/vault-0:/tmp/vault-backup.raft ~/vault-backup.raft

# Backup location (set BACKUP_DIR for automated backups)
ls -lh ~/vault-backup.raft
```

### Restore from Disaster

```bash
# If cluster is gone, rebuild:
1. kubectl apply -f ~/platform/gitops/clusters/local/namespaces.yaml
2. kubectl apply -f ~/platform/gitops/clusters/local/limit-ranges.yaml
3. kubectl apply -f ~/platform/gitops/clusters/local/resource-quotas.yaml
4. kubectl apply -f ~/platform/gitops/bootstrap/argocd-bootstrap.yaml
5. kubectl apply -f ~/platform/gitops/root-app.yaml
6. Argo auto-syncs all infrastructure from Git
7. Restore Vault from snapshot

Total time: ~15 minutes
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

### Vault Unreachable

```bash
# Check Vault pod
kubectl get pod -n vault

# Check Vault logs
kubectl logs -n vault vault-0

# Restart Vault
kubectl delete pod -n vault vault-0

# Check k8s auth
kubectl exec -n vault vault-0 -- vault auth list
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

## RESOURCE LIMITS

### Current Quotas

```yaml
observability:
  memory: 16Gi (hard limit)
  cpu: 8 cores (hard limit)

security:
  memory: 4Gi
  cpu: 2 cores

workloads:
  memory: 8Gi
  cpu: 4 cores
```

### Current Usage

```bash
# Check live usage
kubectl describe quota -A
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

## CONTACT & SUPPORT

- **Runbook Updates:** ~/platform/gitops/docs/
- **GitHub Repo:** https://github.com/temitayocharles/platform-gitops.git
- **Cluster Config:** ~/platform/gitops/infrastructure/
- **Monitoring:** http://localhost:3000 (Grafana)

---

**Remember:** All changes go through Git. No manual kubectl edits on managed resources.
