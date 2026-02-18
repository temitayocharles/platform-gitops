# Architecture

  ## Role in Platform Architecture
  **Layer 2 - GitOps Deployment Control Plane**

  ## Global Dependency Graph
  ```mermaid
  flowchart TD
TM["terraform-module"] --> IE["infra-environments"]
VO["vault-ops"] --> CFG["configurations"]
VO --> SW["shared-workflows"]
CFG --> HC["helm-charts"]
VO --> HC
SW --> APP["app repos"]
HC --> PG["platform-gitops"]
CFG --> PG
VO --> PG
SW --> PG
HC --> CHG["cila-health-infrastructure-gitops"]
CFG --> CHG
VO --> CHG
HC --> FG["fintech-gitops"]
CFG --> FG
VO --> FG
APP --> IMG["GHCR Images"]
IMG --> PG
IMG --> CHG
IMG --> FG
  ```

  ## Commit-to-Production Flow
  1. Code change lands in app/infra repo.
  2. `shared-workflows` executes standardized CI.
  3. Image is pushed to GHCR (for runtime repos).
  4. GitOps values/app manifests are updated.
  5. ArgoCD reconciles desired state to cluster.
  6. Secrets are resolved via Vault/ESO paths controlled by `vault-ops`.

  ## Standards
  - Avoid manual drift in running clusters; use GitOps as source of truth.
  - Keep non-secret defaults in `configurations`; secrets in Vault.
  - Pin Terraform module versions by release tags in environment repos.

  ## Cross-Links
  - [`DEPENDENCY_LADDER.md`](./DEPENDENCY_LADDER.md)
  - [`START_HERE.md`](./START_HERE.md)
