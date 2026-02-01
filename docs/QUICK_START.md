# Quick Start Guide - Get Up and Running

**For:** New team members or quick reference  
**Time:** 5 minutes to productive  
**Updated:** 2026-02-01

---

## 1. Access the Platform (30 seconds)

Your tools are already accessible - no setup needed!

```
Argo CD (Deployments):   http://localhost:8080
Prometheus (Metrics):    http://localhost:9090
Grafana (Dashboards):    http://localhost:3000
Alertmanager (Alerts):   http://localhost:9093
Vault (Secrets):         http://localhost:8200
```

If services not available:
```bash
systemctl --user start k8s-port-forward-*.service
```

---

## 2. Deploy Your First Application (2 minutes)

### Step 1: Create app directory
```bash
cd ~/platform/gitops
mkdir -p infrastructure/workloads/my-first-app
```

### Step 2: Create Argo Application
Create `infrastructure/workloads/my-first-app/app.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-first-app
  namespace: argocd
spec:
  project: workloads
  source:
    repoURL: https://github.com/my-org/my-app
    targetRevision: main
    path: helm
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

### Step 3: Deploy
```bash
git add infrastructure/workloads/my-first-app/
git commit -m "feat: Add my-first-app"
git push origin main
```

### Step 4: Watch it deploy
```bash
# Open Argo CD in browser
# http://localhost:8080

# Or watch via CLI
kubectl get app -n argocd -w
```

**That's it!** ✅ Your app is deployed

---

## 3. Check Status (1 minute)

### All applications synced?
```bash
kubectl get app -n argocd
```

Should show:
```
NAME             SYNC STATUS   HEALTH
observability    Synced        Healthy
platform-root    OutOfSync     Healthy  ← Normal for root app
platform-tools   OutOfSync     Healthy  ← Normal for root app
security         Synced        Healthy
workloads        Synced        Healthy
my-first-app     Synced        Healthy  ← Your app!
```

### Check your app pods
```bash
kubectl get pods -n workloads
```

### View app logs
```bash
kubectl logs -n workloads deployment/my-first-app
```

---

## 4. Common Tasks (Copy-Paste Ready)

### Update your app
```bash
# Edit the app
vim infrastructure/workloads/my-first-app/app.yaml

# Deploy the update
git add infrastructure/workloads/my-first-app/app.yaml
git commit -m "chore: Update my-first-app config"
git push origin main
```

### Delete your app
```bash
# Remove the directory
rm -rf infrastructure/workloads/my-first-app

# Remove from Git
git add infrastructure/workloads/
git commit -m "chore: Remove my-first-app"
git push origin main

# Argo will auto-delete after sync
```

### View application details
```bash
kubectl describe app -n argocd my-first-app
```

### Force sync an app
```bash
kubectl patch app -n argocd my-first-app -p '{"spec":{"syncPolicy":{"syncOptions":["Refresh=hard"]}}}' --type=merge
```

### Port-forward your app
```bash
kubectl port-forward -n workloads svc/my-first-app 8000:8000
```

---

## 5. Understanding the Structure

### Your app lives here:
```
infrastructure/workloads/
├── my-first-app/
│   └── app.yaml          ← Your app definition
└── another-app/
    └── app.yaml
```

### Projects (Team isolation):
```
platform-tools        → Vault, ESO, Argo CD (Admins only)
platform-observability → Prometheus, Grafana (DevOps)
platform-security     → RBAC, policies (Security)
workloads             → Your apps (Developers) ← YOU ARE HERE
```

### Deployment flow:
```
You push to Git
    ↓
Argo CD detects change
    ↓
Argo CD applies to cluster
    ↓
Your app runs in workloads namespace
    ↓
Prometheus monitors it
    ↓
Grafana displays metrics
    ↓
Alertmanager notifies Discord if issues
```

---

## 6. Troubleshooting (3 minutes)

### App not deploying?
```bash
# Check app status
kubectl describe app -n argocd my-first-app

# Check if repo is allowed
kubectl get appproject -n argocd workloads -o yaml

# Check Argo logs
kubectl logs -n argocd deployment/argocd-application-controller
```

### Can't access service?
```bash
# Check pods are running
kubectl get pods -n workloads

# Check pod logs
kubectl logs -n workloads <pod-name>

# Try port-forwarding manually
kubectl port-forward -n workloads svc/my-first-app 8000:8000
```

### Port-forwards not working?
```bash
# Check service status
systemctl --user status k8s-port-forward-argo.service

# View logs
journalctl --user -u k8s-port-forward-argo.service -n 10

# Restart all
systemctl --user restart k8s-port-forward-*.service
```

---

## 7. Key Commands Cheat Sheet

```bash
# Applications
kubectl get app -n argocd                          # List apps
kubectl describe app -n argocd <name>              # Details
kubectl patch app -n argocd <name> -p '...'        # Update

# Projects
kubectl get appproject -n argocd                   # List projects
kubectl get appproject -n argocd <name> -o yaml    # Project RBAC

# Pods in your namespace
kubectl get pods -n workloads                      # List pods
kubectl logs -n workloads <pod-name>               # Pod logs
kubectl describe pod -n workloads <pod-name>       # Pod details

# Port-forward
kubectl port-forward -n workloads svc/<name> 8000:8000

# Check sync status
kubectl get app -n argocd my-app -o jsonpath='{.status.sync.status}'

# View what Argo would deploy
kubectl diff -f infrastructure/workloads/my-app/app.yaml
```

---

## 8. Next Steps

- ✅ Deploy your app (see Step 2)
- ✅ Check Grafana dashboards (http://localhost:3000)
- ✅ View metrics in Prometheus (http://localhost:9090)
- ✅ Check alerts in Alertmanager (http://localhost:9093)
- Read [ARCHITECTURE.md](./ARCHITECTURE.md) for deep dive
- Read [OPERATIONS.md](./OPERATIONS.md) for day-2 ops

---

## Pro Tips

### Tip 1: Always push to Git
Never use `kubectl apply` directly - always edit files and push to Git!

### Tip 2: Use Argo CD UI
The web UI shows sync status visually. It's helpful!

### Tip 3: Check before deleting
Always check `kubectl get all -n workloads` before deleting!

### Tip 4: Use templates
Copy existing apps as templates for new ones.

### Tip 5: Review before committing
Always review your changes:
```bash
git diff infrastructure/workloads/my-app/
```

---

## Getting Help

| Question | Answer |
|----------|--------|
| How do I deploy? | See Step 2: Deploy Your First Application |
| Where's my app? | `infrastructure/workloads/my-app/app.yaml` |
| How do I check status? | `kubectl get app -n argocd` |
| Where are metrics? | Prometheus: http://localhost:9090 |
| Where are dashboards? | Grafana: http://localhost:3000 |
| How do I delete my app? | Remove directory + `git push` |
| System broken? | See docs/DISASTER_RECOVERY.md |

---

**Ready to deploy?** Go to Step 2! 🚀
