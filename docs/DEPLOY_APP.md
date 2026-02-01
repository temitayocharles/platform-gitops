# How to Deploy an App

This guide shows exactly what files you need and where to put them. Example: deploying a 3-tier web app (frontend, API, database).

---

## File Structure You'll Create

```
infrastructure/workloads/my-biosite/
├── kustomization.yaml
├── app.yaml
├── namespace.yaml
├── frontend/
│   ├── kustomization.yaml
│   └── deployment.yaml
├── api/
│   ├── kustomization.yaml
│   └── deployment.yaml
└── database/
    ├── kustomization.yaml
    ├── statefulset.yaml
    └── pvc.yaml
```

---

## Step 1: Create the App Structure

```bash
cd ~/platform/gitops
mkdir -p infrastructure/workloads/my-biosite/{frontend,api,database}
```

---

## Step 2: Namespace (optional but recommended)

File: `infrastructure/workloads/my-biosite/namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: my-biosite
```

---

## Step 3: Frontend Deployment

File: `infrastructure/workloads/my-biosite/frontend/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: biosite-frontend
  namespace: my-biosite
  labels:
    app: biosite-frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: biosite-frontend
  template:
    metadata:
      labels:
        app: biosite-frontend
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: biosite-frontend
  namespace: my-biosite
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 80
  selector:
    app: biosite-frontend
```

File: `infrastructure/workloads/my-biosite/frontend/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: my-biosite
resources:
  - deployment.yaml
```

---

## Step 4: API Deployment

File: `infrastructure/workloads/my-biosite/api/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: biosite-api
  namespace: my-biosite
  labels:
    app: biosite-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: biosite-api
  template:
    metadata:
      labels:
        app: biosite-api
    spec:
      containers:
      - name: api
        image: your-repo/biosite-api:v1.0
        ports:
        - containerPort: 3000
        env:
        - name: DATABASE_HOST
          value: "biosite-db"
        - name: DATABASE_PORT
          value: "5432"
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: biosite-api
  namespace: my-biosite
spec:
  type: ClusterIP
  ports:
  - port: 3000
    targetPort: 3000
  selector:
    app: biosite-api
```

File: `infrastructure/workloads/my-biosite/api/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: my-biosite
resources:
  - deployment.yaml
```

---

## Step 5: Database StatefulSet + Storage

File: `infrastructure/workloads/my-biosite/database/pvc.yaml`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: biosite-db-pvc
  namespace: my-biosite
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 5Gi
```

File: `infrastructure/workloads/my-biosite/database/statefulset.yaml`

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: biosite-db
  namespace: my-biosite
spec:
  serviceName: biosite-db
  replicas: 1
  selector:
    matchLabels:
      app: biosite-db
  template:
    metadata:
      labels:
        app: biosite-db
    spec:
      containers:
      - name: postgres
        image: postgres:15
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: biosite
        - name: POSTGRES_USER
          value: biosite
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: password
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: local-path
      resources:
        requests:
          storage: 5Gi
---
apiVersion: v1
kind: Service
metadata:
  name: biosite-db
  namespace: my-biosite
spec:
  clusterIP: None
  ports:
  - port: 5432
    targetPort: 5432
  selector:
    app: biosite-db
---
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: my-biosite
type: Opaque
stringData:
  password: "changeme123"  # Change this!
```

File: `infrastructure/workloads/my-biosite/database/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: my-biosite
resources:
  - pvc.yaml
  - statefulset.yaml
```

---

## Step 6: Root Kustomization

File: `infrastructure/workloads/my-biosite/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: my-biosite
resources:
  - namespace.yaml
  - frontend/
  - api/
  - database/
```

---

## Step 7: Argo Application

File: `infrastructure/workloads/my-biosite/app.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-biosite
  namespace: argocd
spec:
  project: workloads
  
  source:
    repoURL: https://github.com/temitayocharles/platform-gitops.git
    targetRevision: main
    path: infrastructure/workloads/my-biosite
  
  destination:
    server: https://kubernetes.default.svc
    namespace: my-biosite
  
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

---

## Step 8: Deploy

```bash
# Add all files
git add infrastructure/workloads/my-biosite/

# Commit
git commit -m "feat: Add my-biosite deployment (frontend, api, database)"

# Push to Git
git push origin main
```

**That's it!** Argo CD automatically deploys within 30 seconds.

---

## Verify Deployment

```bash
# Check Argo app synced
kubectl get app -n argocd my-biosite

# Check pods
kubectl get pods -n my-biosite

# Check services
kubectl get svc -n my-biosite

# View logs
kubectl logs -n my-biosite deployment/biosite-api

# Port-forward to test
kubectl port-forward -n my-biosite svc/biosite-frontend 8000:80
# Then visit: http://localhost:8000
```

---

## Update Your App

1. Edit file (e.g., `infrastructure/workloads/my-biosite/api/deployment.yaml`)
2. Change image version: `image: your-repo/biosite-api:v1.1`
3. Commit: `git commit -m "chore: Update API to v1.1"`
4. Push: `git push origin main`
5. Argo redeploys automatically

---

## Using Helm Charts (Instead of Raw YAML)

If your app has a Helm chart, skip the YAML files above and use this instead:

File: `infrastructure/workloads/my-biosite/app.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-biosite
  namespace: argocd
spec:
  project: workloads
  
  source:
    repoURL: https://github.com/your-org/biosite-helm-chart.git
    targetRevision: main
    path: chart
    helm:
      values: |
        frontend:
          replicas: 2
          image: your-repo/frontend:v1.0
        
        api:
          replicas: 2
          image: your-repo/api:v1.0
        
        database:
          enabled: true
          storage: 5Gi
  
  destination:
    server: https://kubernetes.default.svc
    namespace: my-biosite
  
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

Then deploy the same way (git commit + git push).

---

## Common Patterns

### Change replicas
Edit the file, change `replicas: 2` to `replicas: 3`, commit & push.

### Change image
Edit the file, change `image: your-repo/api:v1.0` to `image: your-repo/api:v1.1`, commit & push.

### Change storage size
Edit the file, change `storage: 5Gi` to `storage: 10Gi`, commit & push.

### Add environment variables
Edit deployment, add to `env:` section, commit & push.

### Add database backup
Create new file `infrastructure/workloads/my-biosite/backup/cronjob.yaml`, add to root kustomization, commit & push.

---

## Checklist

Before pushing to Git:

- [ ] Created `infrastructure/workloads/my-biosite/` directory
- [ ] Added `namespace.yaml` (if using custom namespace)
- [ ] Added `frontend/deployment.yaml` + `frontend/kustomization.yaml`
- [ ] Added `api/deployment.yaml` + `api/kustomization.yaml`
- [ ] Added `database/statefulset.yaml` + `database/pvc.yaml` + `database/kustomization.yaml`
- [ ] Added root `infrastructure/workloads/my-biosite/kustomization.yaml`
- [ ] Added `infrastructure/workloads/my-biosite/app.yaml` (Argo Application)
- [ ] Verified all file paths match
- [ ] Changed image names to your actual images
- [ ] Changed database password
- [ ] Tested locally with `git diff infrastructure/workloads/my-biosite/`

---

## What Happens Next

1. You push to Git
2. Argo CD detects change (within 30s)
3. Argo creates namespace
4. Argo creates database secret
5. Argo creates database StatefulSet + PVC
6. Argo creates API deployment + service
7. Argo creates frontend deployment + service
8. Pods start (takes 30-60s)
9. Services become available
10. ✅ App is live

---

Done! Your app is now managed by GitOps.
