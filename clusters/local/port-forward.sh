#!/bin/bash
# Kubernetes Port Forwarding Manager
# Automatically forwards key cluster services to localhost
# Usage: ./port-forward.sh [start|stop]

set -e

ACTION="${1:-start}"
LOG_FILE="${LOG_FILE:-/tmp/k8s-port-forward.log}"
PID_FILE="${PID_FILE:-/tmp/k8s-port-forward.pids}"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

start_forwarding() {
    log "Starting Kubernetes port forwarding..."
    
    # Argo CD
    kubectl port-forward -n argocd svc/argocd-server 8080:80 >> "$LOG_FILE" 2>&1 &
    echo $! >> "$PID_FILE"
    log "✅ Argo CD: localhost:8080"
    
    # Vault
    kubectl port-forward -n vault svc/vault 8200:8200 >> "$LOG_FILE" 2>&1 &
    echo $! >> "$PID_FILE"
    log "✅ Vault: localhost:8200"
    
    # Prometheus
    kubectl port-forward -n observability svc/kube-prometheus-stack-prometheus 9090:9090 >> "$LOG_FILE" 2>&1 &
    echo $! >> "$PID_FILE"
    log "✅ Prometheus: localhost:9090"
    
    # Grafana
    kubectl port-forward -n observability svc/kube-prometheus-stack-grafana 3000:80 >> "$LOG_FILE" 2>&1 &
    echo $! >> "$PID_FILE"
    log "✅ Grafana: localhost:3000 (admin/admin)"
    
    # Alertmanager
    kubectl port-forward -n observability svc/kube-prometheus-stack-alertmanager 9093:9093 >> "$LOG_FILE" 2>&1 &
    echo $! >> "$PID_FILE"
    log "✅ Alertmanager: localhost:9093"
    
    log "All port forwards active"
}

stop_forwarding() {
    if [ -f "$PID_FILE" ]; then
        log "Stopping port forwarding..."
        while IFS= read -r pid; do
            kill "$pid" 2>/dev/null && log "Killed $pid" || true
        done < "$PID_FILE"
        rm "$PID_FILE"
    fi
}

trap stop_forwarding EXIT

case "$ACTION" in
    start) start_forwarding; wait ;;
    stop) stop_forwarding; exit 0 ;;
    *) echo "Usage: $0 [start|stop]"; exit 1 ;;
esac
