#!/usr/bin/env python3
"""Create an ArgoCD Application + env values folder for a new service.

This follows the multi-source pattern:
- helm-charts: chart templates
- platform-gitops: values (ref: values)
- configurations: ConfigMaps (optional source path)
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Create Argo app + values scaffolding")
    p.add_argument("--group", required=True, help="applications/<group>/ (e.g. cila-health)")
    p.add_argument("--app", required=True, help="Argo application name (e.g. cila-health-patient-service)")
    p.add_argument("--project", default="workloads", help="Argo project name (default: workloads)")
    p.add_argument("--dest-namespace", default="apps-dev", help="K8s namespace to deploy into (default: apps-dev)")
    p.add_argument("--env", default="staging", help="Environment name (default: staging)")

    p.add_argument("--chart-repo-url", default="https://github.com/temitayocharles/helm-charts.git")
    p.add_argument("--chart-revision", default="main")
    p.add_argument("--chart-path", required=True, help="Path in helm-charts repo (e.g. applications/cila-health-patient-service)")

    p.add_argument("--values-repo-url", default="https://github.com/temitayocharles/platform-gitops.git")
    p.add_argument("--values-revision", default="main")

    p.add_argument("--config-repo-url", default="https://github.com/temitayocharles/configurations.git")
    p.add_argument("--config-revision", default="main")
    p.add_argument("--config-path", required=True, help="Path in configurations repo (e.g. applications/cila-health-patient-service/configmaps)")

    p.add_argument("--image-repo", required=True, help="GHCR image repository (e.g. ghcr.io/temitayocharles/cila-health-patient-service)")
    p.add_argument("--hostname", required=True, help="Ingress hostname (e.g. patient-service.local)")

    p.add_argument("--vault-store", required=True, help="ClusterSecretStore name (e.g. vault-cila-health-microservices-patient-service)")
    p.add_argument("--vault-base-path", required=True, help="Vault remoteRef.key base (e.g. temitayo/staging/cila-health-microservices/patient-service)")

    args = p.parse_args()

    group_dir = ROOT / "applications" / args.group
    app_yaml = group_dir / f"{args.app}.yaml"
    values_dir = group_dir / args.app
    values_file = values_dir / f"values-{args.env}.yaml"

    if app_yaml.exists():
        raise SystemExit(f"App already exists: {app_yaml}")
    if values_file.exists():
        raise SystemExit(f"Values already exists: {values_file}")

    app_manifest = f"""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {args.app}
  namespace: argocd
spec:
  project: {args.project}
  sources:
    - repoURL: {args.chart_repo_url}
      targetRevision: {args.chart_revision}
      path: {args.chart_path}
      helm:
        valueFiles:
          - $values/applications/{args.group}/{args.app}/values-{args.env}.yaml
    - repoURL: {args.values_repo_url}
      targetRevision: {args.values_revision}
      ref: values
      path: applications/{args.group}/{args.app}
    - repoURL: {args.config_repo_url}
      targetRevision: {args.config_revision}
      path: {args.config_path}
  destination:
    server: https://kubernetes.default.svc
    namespace: {args.dest_namespace}
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
"""

    # Values here are intentionally minimal and match the microservice chart template.
    values = f"""replicaCount: 1
image:
  repository: {args.image_repo}
  tag: "staging-CHANGE-ME"
  pullPolicy: Always
imagePullSecrets:
  - name: ghcr-creds

service:
  type: ClusterIP
  port: 80

containerPort: 8000

resources:
  requests:
    memory: "64Mi"
    cpu: "50m"
  limits:
    memory: "256Mi"
    cpu: "250m"

env:
  config: {{}}

secrets:
  - envName: EXAMPLE_SECRET
    secretName: {args.app}-secret
    secretKey: EXAMPLE_SECRET

externalSecrets:
  enabled: true
  storeRef: {args.vault_store}
  refreshInterval: 1m
  basePath: {args.vault_base_path}

ingress:
  enabled: true
  className: traefik
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
  hosts:
    - host: {args.hostname}
      paths:
        - path: /
          pathType: Prefix
"""

    write(app_yaml, app_manifest)
    write(values_file, values)
    print(f"Created: {app_yaml}")
    print(f"Created: {values_file}")


if __name__ == "__main__":
    main()

