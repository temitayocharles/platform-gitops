# New Service Playbook (Argo Application + Values)

This repo is the source of truth for:
- ArgoCD `Application` manifests
- Environment values (`values-*.yaml`)

Charts live in `helm-charts`. ConfigMaps live in `configurations`. Secrets live in Vault (enforced by `vault-ops`).

## Cross-Repo Dependencies
- Charts: [`temitayocharles/helm-charts`](https://github.com/temitayocharles/helm-charts)
  - New chart playbook: [`helm-charts/docs/NEW_SERVICE.md`](https://github.com/temitayocharles/helm-charts/blob/main/docs/NEW_SERVICE.md)
- ConfigMaps + `.env.example`: [`temitayocharles/configurations`](https://github.com/temitayocharles/configurations)
- Vault boundaries (policies/roles/stores): [`temitayocharles/vault-ops`](https://github.com/temitayocharles/vault-ops)
  - New service playbook: [`vault-ops/docs/NEW_SERVICE.md`](https://github.com/temitayocharles/vault-ops/blob/main/docs/NEW_SERVICE.md)

## 1) Create the Argo App + Values (Generator Script)
```bash
cd /Users/charlie/Desktop/platform-gitops

python3 scripts/new_argocd_app.py \
  --group cila-health \
  --app cila-health-patient-service \
  --chart-path applications/cila-health-patient-service \
  --config-path applications/cila-health-patient-service/configmaps \
  --image-repo ghcr.io/temitayocharles/cila-health-patient-service \
  --hostname patient-service.local \
  --vault-store vault-cila-health-microservices-patient-service \
  --vault-base-path temitayo/staging/cila-health-microservices/patient-service
```

Generated files:
- `applications/<group>/<app>.yaml`
- `applications/<group>/<app>/values-staging.yaml`

## 2) Pin the Image Tag
Edit the generated values file and set:
```yaml
image:
  tag: "staging-<sha7>"
```

## 3) Commit + Push
```bash
git add applications/<group>/<app>.yaml applications/<group>/<app>/values-staging.yaml
git commit -m "feat(gitops): add <app>"
git push origin main
```

## 4) Verify in Cluster (Run in VM)
```bash
ssh ubuntu-vm
sudo -n k3s kubectl -n argocd get applications | grep <app>
sudo -n k3s kubectl -n apps-dev get pods
```

## 5) Cleanup (Resource Conservation)
If this app was only deployed for verification, delete it:
```bash
ssh ubuntu-vm
sudo -n k3s kubectl -n argocd delete application <app> --wait=true
```
