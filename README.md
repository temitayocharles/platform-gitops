# Platform GitOps - Production Kubernetes Platform

**Version:** 2.1 (Production Ready - Restructured)  
**Last Updated:** 2026-02-01  
**Status:** ✅ Fully Operational  
**Cluster:** K3s Single Node (16GB Mac, 10GB K3s, 6GB macOS)

---

## What Is This?

A **complete, self-owned, team-ready Kubernetes platform** with:

- **GitOps automation** via Argo CD with proper team-based projects
- **Full observability** (Prometheus, Grafana, Alertmanager)
- **Secure secrets management** via Vault
- **Multi-team namespace isolation** with RBAC
- **Discord alert notifications**
- **Persistent tool access** (auto-forwarded ports)
- **Automated disaster recovery** (~15 minutes)

Everything is **declarative**, **auditable**, **reproducible from Git**, and **organized by team/function**.

---

## Quick Start

### 1. Port-Forward Services (Automatic)

Port-forwarding services run automatically on login via systemd:

```bash
# Services are already running! Check status:
systemctl --user status k8s-port-forward-*.service

# Access them in browser (see below)
```

Or manually start/stop:
```bash
# Start all
systemctl --user start k8s-port-forward-*.service

# Stop all  
systemctl --user stop k8s-port-forward-*.service

# View logs
journalctl --user -u k8s-port-forward-argo.service -f
```

### 2. Access Services

| Service | URL | Purpose |
|---------|-----|---------|
| **Argo CD** | http://localhost:8080 | GitOps deployment |
| **Prometheus** | http://localhost:9090 | Metrics |
| **Grafana** | http://localhost:3000 | Dashboards (admin/admin) |
| **Alertmanager** | http://localhost:9093 | Alert routing |
| **Vault** | http://localhost:8200 | Secrets |

### 3. Check System Health

```bash
# All applications synced?
kubectl get app -n argocd

# All projects visible?
kubectl get appproject -n argocd

# All pods running?
kubectl get pods -A --sort-by=.metadata.namespace
```

---

## Repository Structure

### New (Restructured) - Organization by Team/Function

```
platform-gitops/
├── README.md                          This file
├── root-app.yaml                      Root Argo app (platform-tools project)
│
├── infrastructure/
│   ├── argo-projects.yaml             Team projects with RBAC definitions
│   ├── kustomization.yaml             Root kustomization
│   │
│   ├── platform-tools-app.yaml        App orchestrator for platform
│   ├── observability-app.yaml         App orchestrator for observability  
│   ├── security-app.yaml              App orchestrator for security
│   ├── workloads-app.yaml             App orchestrator for user apps
│   │
│   ├── platform/                      Core platform (platform-tools project)
│   │   ├── kustomization.yaml
│   │   ├── vault/
│   │   │   ├── kustomization.yaml
│   │   │   └── app.yaml               Vault Helm Application
│   │   ├── external-secrets/
│   │   │   ├── kustomization.yaml
│   │   │   ├── app.yaml               ESO Helm Application
│   │   │   └── secretstore.yaml       Vault backend config
│   │   └── argo-cd/
│   │       ├── kustomization.yaml
│   │       └── app.yaml               Argo CD self-manages
│   │
│   ├── observability/                 Monitoring (platform-observability)
│   │   ├── kustomization.yaml
│   │   ├── prometheus/
│   │   │   ├── kustomization.yaml
│   │   │   └── app.yaml               kube-prometheus-stack
│   │   ├── alertmanager/
│   │   │   ├── kustomization.yaml
│   │   │   └── alertmanager-config.yaml
│   │   └── grafana/
│   │       └── kustomization.yaml
│   │
│   ├── security/                      RBAC & Policies (platform-security)
│   │   ├── kustomization.yaml
│   │   └── rbac/
│   │       └── default-rbac.yaml
│   │
│   └── workloads/                     User apps (workloads project)
│       └── kustomization.yaml         Empty - for your applications
│
├── docs/
│   ├── ARCHITECTURE.md                System design & decisions
│   ├── OPERATIONS.md                  How to operate the platform
│   ├── DISASTER_RECOVERY.md           Recovery procedures
│   └── CLUSTER_OPERATIONS.md          Cluster maintenance
│
└── .gitignore
```

---

## Argo Projects (Team Organization)

### Available Projects

| Project | Purpose | Namespaces | Access | Use Case |
|---------|---------|-----------|--------|----------|
| `platform-tools` | Core infrastructure | vault, external-secrets, argocd | Admin only | System foundations |
| `platform-observability` | Monitoring stack | observability | DevOps team | Metrics & dashboards |
| `platform-security` | Security & RBAC | security | Security team | Access controls |
| `workloads` | User applications | workloads, applications, services | Developers | Your applications |

### How Projects Work

Each project:
- ✅ Can deploy only to assigned namespaces
- ✅ Has its own Argo Application
- ✅ Syncs automatically from Git
- ✅ Can be restricted by source repo
- ✅ Enables team isolation

---

## Quick Tasks

### Deploy a New Application

1. Create directory in `infrastructure/workloads/`:
```bash
mkdir -p infrastructure/workloads/my-app
```

2. Create Argo Application file (`infrastructure/workloads/my-app/app.yaml`):
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: workloads
  source:
    repoURL: https://github.com/your-org/your-repo
    targetRevision: main
    path: helm/my-app
  destination:
    server: https://kubernetes.default.svc
    namespace: workloads
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

3. Push to Git:
```bash
git add infrastructure/workloads/my-app/app.yaml
git commit -m "feat: Add my-app application"
git push origin main
```

4. ✅ Argo CD automatically deploys via the `workloads` project

### Add a New Team Project

1. Edit `infrastructure/argo-projects.yaml` and add:
```yaml
---
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: my-team
  namespace: argocd
spec:
  description: "My team applications"
  sourceRepos:
  - 'https://github.com/my-team-repo.git'
  destinations:
  - namespace: 'my-team'
    server: https://kubernetes.default.svc
```

2. Create directory and app orchestrator:
```bash
mkdir -p infrastructure/my-team
# Add kustomization.yaml
# Add app.yaml that references infrastructure/my-team
```

3. Update `infrastructure/kustomization.yaml`:
```yaml
resources:
  - argo-projects.yaml
  - platform-tools-app.yaml
  - observability-app.yaml
  - security-app.yaml
  - my-team-app.yaml  # Add this
  - workloads-app.yaml
```

4. Push to Git
```bash
git add infrastructure/
git commit -m "feat: Add my-team project and apps"
git push origin main
```

### Check Application Status

```bash
# All apps synced?
kubectl get app -n argocd

# Detailed status
kubectl describe app -n argocd my-app

# See what's deployed
kubectl get all -n workloads
```

### Update an Application

1. Edit the config in Git (e.g., `infrastructure/workloads/my-app/app.yaml`)
2. Push to Git
3. Argo CD automatically syncs the change

```bash
git add infrastructure/workloads/my-app/app.yaml
git commit -m "chore: Update my-app Helm values"
git push origin main
```

---

## System Components

### Core Infrastructure (platform-tools project)

**Vault**
- Secrets storage
- ESO backend
- Auto-unsealed at startup
- HA enabled with Raft storage

**External Secrets Operator (ESO)**
- Syncs secrets from Vault to Kubernetes
- Stores Discord webhook in observability namespace
- Continuously reconciles with Vault

**Argo CD**
- GitOps controller
- Manages all applications
- Auto-reconciles cluster with Git
- Self-manages via app in `infrastructure/platform/argo-cd/`

### Observability Stack (platform-observability project)

**Prometheus**
- Scrapes cluster metrics
- Evaluates alert rules
- Stores 15 days of data
- Sends alerts to Alertmanager

**Alertmanager**
- Routes alerts from Prometheus
- Sends to Discord via webhook
- Webhook URL from Vault (via ESO)

**Grafana**
- Visualizes Prometheus metrics
- Default dashboards enabled
- Accessible at http://localhost:3000

---

## Key Features

### ✅ All-in-Git Architecture

```
Every configuration lives in Git:
- Argo Projects (RBAC)
- Applications (deployment specs)
- Helm charts (component config)
- Kustomizations (overlays)

No manual `kubectl apply` needed - Git is source of truth!
```

### ✅ Team-Based Access Control

```
Projects isolate teams by:
- Allowed namespaces
- Allowed source repositories
- Cluster resource types
- Custom permissions

Developer can't accidentally delete monitoring!
```

### ✅ Persistent Tool Access

```
5 systemd services keep tunnels open:
- Auto-start on login
- Auto-restart on failure
- Always available in browser
- No manual port-forward needed
```

### ✅ Disaster Recovery

Complete recovery from Git + Vault:
```
1. Deploy fresh cluster
2. Apply infrastructure/ from Git
3. Unseal Vault (3 keys)
4. All apps auto-deploy
5. Backups restore
```
**Time: ~15 minutes**

---

## Troubleshooting

### Port-forwards not working?

```bash
# Check service status
systemctl --user status k8s-port-forward-argo.service

# View logs
journalctl --user -u k8s-port-forward-argo.service -n 20

# Manually test
curl http://localhost:8080  # Should get Argo CD login page
```

### Application not syncing?

```bash
# Check app status
kubectl describe app -n argocd my-app

# Check project restrictions
kubectl get appproject -n argocd my-team -o yaml

# Check if repo is allowed
# Make sure sourceRepos in project includes your repo URL
```

### Vault not unsealing?

```bash
# Check Vault status
kubectl exec -n vault vault-0 -- vault status

# Port-forward and unseal manually
kubectl port-forward -n vault svc/vault 8200:8200 &
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>
```

---

## Files Summary

| File | Purpose |
|------|---------|
| `infrastructure/argo-projects.yaml` | All Argo projects with RBAC |
| `infrastructure/platform/vault/app.yaml` | Vault deployment |
| `infrastructure/platform/external-secrets/app.yaml` | ESO deployment |
| `infrastructure/observability/prometheus/app.yaml` | kube-prometheus-stack |
| `infrastructure/observability/alertmanager/alertmanager-config.yaml` | Discord routing |
| `~/.config/systemd/user/k8s-port-forward-*.service` | Persistent tunnels |
| `root-app.yaml` | Root Argo application |

---

## Next Steps

1. ✅ Access Argo CD: http://localhost:8080
2. ✅ Verify all applications synced
3. ✅ Deploy your first app to `infrastructure/workloads/`
4. ✅ Create team projects as needed
5. ✅ Setup CI/CD for automatic deployments

---

## Resources

- [Argo CD Documentation](https://argo-cd.readthedocs.io/)
- [Kustomize Guide](https://kustomize.io/)
- [Kubernetes Namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)
- [GitOps Best Practices](https://opengitops.dev/)

---

**Questions?** Check the docs/ directory for detailed guides on architecture, operations, and recovery.
