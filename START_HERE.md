# Start Here

This repo is the source of truth for ArgoCD Applications and environment values. Follow in order to deploy anything.

## 1. What This Repo Is
ArgoCD GitOps repo that defines Applications, ApplicationSets, and environment values. It references Helm charts and configurations from other repos using multi‑source Argo.

## 2. Repo Map (What Lives Where)
- [README.md](README.md): High‑level overview.
- Docs: [docs/QUICK_START.md](docs/QUICK_START.md), [docs/DEPLOY_APP.md](docs/DEPLOY_APP.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- New service playbook: [docs/NEW_SERVICE.md](docs/NEW_SERVICE.md)
- Applications and values live under [applications](applications).

## 3. Deploy a New App (Chronological)
1. Ensure the chart exists in the helm‑charts repo.
1. Ensure configs exist in the configurations repo.
1. Add a new Argo Application here under `applications/<group>/<app>/`.
1. Reference the chart repo and values repo as **multi‑source** in the Application manifest.
1. Commit and push; Argo will sync.

## 4. Update an Existing App
1. Edit the values file under `applications/<group>/<app>/values-<env>.yaml`.
1. Commit and push.
1. Sync in Argo if auto‑sync is off.

## 5. Secrets and Config
- ConfigMaps live in the configurations repo.
- Secrets are stored in Vault and pulled by ExternalSecrets/ESO.
- Values here should only reference secret names, not raw secret values.

## 6. Operations
- Cluster procedures: [docs/OPERATIONS.md](docs/OPERATIONS.md).
- Disaster recovery: [docs/DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md).
- Velero restore runbook: [docs/velero-restore-runbook.md](docs/velero-restore-runbook.md).

## 7. Troubleshooting
- If an app is missing, check Argo project permissions and repo‑server access.
- If OutOfSync, compare values and chart revisions first.
