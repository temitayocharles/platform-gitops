# Velero Backup & Restore Runbook (K3s)

This runbook documents the **backup/restore** flow for this cluster and the **S3-backed Velero** setup. It also explains how to recover the K3s data-dir (SQLite datastore) using local snapshots.

## 1. Verify Velero Storage Location

```bash
kubectl -n velero get backupstoragelocations
```
Expected: `default` is **Available**.

## 2. Create On-Demand Backup (All Namespaces)

```bash
cat > /tmp/velero-backup.yaml <<YAML
apiVersion: velero.io/v1
kind: Backup
metadata:
  name: on-demand-$(date +%Y%m%d%H%M%S)
  namespace: velero
spec:
  ttl: 240h
  includedNamespaces:
  - "*"
YAML

kubectl apply -f /tmp/velero-backup.yaml
kubectl -n velero get backups
```

## 3. Restore (All Namespaces)

```bash
cat > /tmp/velero-restore.yaml <<YAML
apiVersion: velero.io/v1
kind: Restore
metadata:
  name: restore-$(date +%Y%m%d%H%M%S)
  namespace: velero
spec:
  backupName: <BACKUP_NAME>
YAML

kubectl apply -f /tmp/velero-restore.yaml
kubectl -n velero get restores
```

## 4. Test Restore (Safe Validation)

This is the recommended non-destructive test:

```bash
kubectl create ns velero-restore-test
kubectl -n velero-restore-test create configmap sample --from-literal=ok=1

# Create backup
cat > /tmp/velero-restore-test-backup.yaml <<YAML
apiVersion: velero.io/v1
kind: Backup
metadata:
  name: restore-test-$(date +%Y%m%d%H%M%S)
  namespace: velero
spec:
  ttl: 24h
  includedNamespaces:
  - velero-restore-test
YAML
kubectl apply -f /tmp/velero-restore-test-backup.yaml

# Delete namespace
kubectl delete ns velero-restore-test

# Restore
cat > /tmp/velero-restore-test-restore.yaml <<YAML
apiVersion: velero.io/v1
kind: Restore
metadata:
  name: restore-restore-test-$(date +%Y%m%d%H%M%S)
  namespace: velero
spec:
  backupName: <RESTORE_TEST_BACKUP_NAME>
YAML
kubectl apply -f /tmp/velero-restore-test-restore.yaml
```

## 5. K3s Datastore Backup (SQLite)

This cluster is **not running etcd**, so etcd snapshots do not apply. Use the local data-dir backup instead:

```bash
~/backup-k3s.sh
```

This creates a tarball in `~/backups/` containing `/data`.

## 6. K3s Datastore Restore (SQLite)

High-level steps:

1. Stop K3s
2. Restore `/data` from the last tarball
3. Start K3s

Example:

```bash
sudo systemctl stop k3s
sudo tar --numeric-owner -xzf ~/backups/k3s-<timestamp>.tar.gz -C /
sudo systemctl start k3s
```

## Notes
- Velero uses bucket prefix `velero/` in `charlie-dev12212025`.
- The AWS plugin must be loaded via initContainer in Velero.
