#!/bin/bash
# sandbox-droplet.sh — Disposable execution sandbox for reeree daemons
#
# Spins up a minimal droplet, rsyncs project files in, runs commands,
# rsyncs results out. Destroys when done. Per-second billing.
#
# Usage:
#   sandbox-droplet.sh up [project-dir]    # Create sandbox, sync project in
#   sandbox-droplet.sh down                # Destroy sandbox (stops billing)
#   sandbox-droplet.sh status              # Check if running
#   sandbox-droplet.sh ssh                 # Shell into sandbox
#   sandbox-droplet.sh sync-in [dir]       # Push project files to sandbox
#   sandbox-droplet.sh sync-out [dir]      # Pull results back
#   sandbox-droplet.sh exec "command"      # Run a command in the sandbox

set -euo pipefail

DROPLET_NAME="reeree-sandbox"
REGION="nyc3"
SIZE="${SANDBOX_SIZE:-s-1vcpu-1gb}"  # $0.009/hr — less than a penny
IMAGE="ubuntu-24-04-x64"
SSH_KEY_IDS=$(doctl compute ssh-key list --format ID --no-header | tr '\n' ',' | sed 's/,$//')
SANDBOX_USER="sandbox"
SANDBOX_HOME="/home/sandbox"
PROJECT_DIR="${2:-.}"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

get_droplet_id() {
    doctl compute droplet list --format Name,ID --no-header 2>/dev/null | \
        grep "^${DROPLET_NAME}" | awk '{print $2}' || true
}

get_droplet_ip() {
    doctl compute droplet get "$(get_droplet_id)" --format PublicIPv4 --no-header 2>/dev/null
}

wait_for_ssh() {
    local ip="$1"
    log "Waiting for SSH..."
    for i in $(seq 1 60); do
        if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "root@$ip" true 2>/dev/null; then
            return 0
        fi
        sleep 3
    done
    return 1
}

cmd_up() {
    local existing
    existing=$(get_droplet_id)
    if [ -n "$existing" ]; then
        local ip
        ip=$(get_droplet_ip)
        log "Sandbox already running (ID: $existing, IP: $ip)"
        return 0
    fi

    log "Creating sandbox ($SIZE in $REGION) — ~\$0.009/hr"

    # Cloud-init: create restricted sandbox user, install python + git
    local user_data
    user_data=$(cat <<'CLOUD_INIT'
#!/bin/bash
set -e

# Create sandbox user (no sudo, restricted shell access)
useradd -m -s /bin/bash sandbox
mkdir -p /home/sandbox/.ssh
cp /root/.ssh/authorized_keys /home/sandbox/.ssh/
chown -R sandbox:sandbox /home/sandbox/.ssh
chmod 700 /home/sandbox/.ssh
chmod 600 /home/sandbox/.ssh/authorized_keys

# Install minimal toolchain
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git rsync >/dev/null

# Restrict sandbox user
# No sudo, no access to /root, no systemctl
chmod 700 /root

# Create project workspace
mkdir -p /home/sandbox/project
chown sandbox:sandbox /home/sandbox/project

# Signal ready
touch /tmp/sandbox-ready
CLOUD_INIT
)

    doctl compute droplet create "$DROPLET_NAME" \
        --region "$REGION" \
        --size "$SIZE" \
        --image "$IMAGE" \
        --ssh-keys "$SSH_KEY_IDS" \
        --user-data "$user_data" \
        --tag-names "sandbox,reeree" \
        --wait

    local ip
    ip=$(get_droplet_ip)
    log "Sandbox created at $ip"

    if wait_for_ssh "$ip"; then
        log "SSH ready."
        # Wait for cloud-init to finish
        log "Waiting for setup to complete..."
        for i in $(seq 1 30); do
            if ssh -o ConnectTimeout=5 "root@$ip" "test -f /tmp/sandbox-ready" 2>/dev/null; then
                break
            fi
            sleep 3
        done
        log "Sandbox ready."

        # Sync project in if a directory was given
        if [ -d "$PROJECT_DIR" ]; then
            cmd_sync_in
        fi
    else
        log "WARNING: SSH not ready after 3 min"
    fi

    log ""
    log "Commands:"
    log "  $0 ssh                    # shell in"
    log "  $0 exec 'pytest tests/'   # run a command"
    log "  $0 sync-in ./sandbox      # push project files"
    log "  $0 sync-out ./sandbox     # pull results back"
    log "  $0 down                   # destroy (stops billing)"
}

cmd_down() {
    local id
    id=$(get_droplet_id)
    if [ -z "$id" ]; then
        log "No sandbox running."
        return 0
    fi

    log "Destroying sandbox (ID: $id)..."
    doctl compute droplet delete "$id" --force
    log "Destroyed. Billing stopped."
}

cmd_status() {
    local id
    id=$(get_droplet_id)
    if [ -z "$id" ]; then
        echo "Sandbox: not running"
        return 0
    fi

    local ip
    ip=$(get_droplet_ip)
    echo "Sandbox: RUNNING"
    echo "  ID: $id"
    echo "  Size: $SIZE"
    echo "  IP: $ip"
    echo "  SSH: ssh sandbox@$ip"
    echo "  Cost: ~\$0.009/hr"
}

cmd_ssh() {
    local ip
    ip=$(get_droplet_ip)
    if [ -n "$ip" ]; then
        ssh "sandbox@$ip"
    else
        echo "No sandbox running."
        exit 1
    fi
}

cmd_sync_in() {
    local ip
    ip=$(get_droplet_ip)
    if [ -z "$ip" ]; then
        echo "No sandbox running."
        exit 1
    fi

    local dir="${2:-$PROJECT_DIR}"
    log "Syncing $dir → sandbox:project/"
    rsync -az --delete \
        --exclude '.git' \
        --exclude '.venv' \
        --exclude '__pycache__' \
        --exclude 'node_modules' \
        --exclude '.reeree/session.log' \
        "$dir/" "sandbox@$ip:project/"
    log "Sync complete."

    # Set up venv if requirements exist
    ssh "sandbox@$ip" "cd project && python3 -m venv .venv 2>/dev/null; \
        if [ -f requirements.txt ]; then .venv/bin/pip install -q -r requirements.txt; fi; \
        if [ -f pyproject.toml ]; then .venv/bin/pip install -q -e . 2>/dev/null; fi" || true
    log "Environment ready."
}

cmd_sync_out() {
    local ip
    ip=$(get_droplet_ip)
    if [ -z "$ip" ]; then
        echo "No sandbox running."
        exit 1
    fi

    local dir="${2:-$PROJECT_DIR}"
    log "Syncing sandbox:project/ → $dir"
    rsync -az \
        --exclude '.venv' \
        --exclude '__pycache__' \
        --exclude 'node_modules' \
        "sandbox@$ip:project/" "$dir/"
    log "Sync complete."
}

cmd_exec() {
    local ip
    ip=$(get_droplet_ip)
    if [ -z "$ip" ]; then
        echo "No sandbox running."
        exit 1
    fi

    shift  # remove "exec" from args
    local command="$*"
    log "sandbox\$ $command"
    ssh "sandbox@$ip" "cd project && source .venv/bin/activate 2>/dev/null; $command"
}

# --- Main ---
case "${1:-}" in
    up)        cmd_up ;;
    down)      cmd_down ;;
    status)    cmd_status ;;
    ssh)       cmd_ssh ;;
    sync-in)   cmd_sync_in ;;
    sync-out)  cmd_sync_out ;;
    exec)      cmd_exec "$@" ;;
    *)
        echo "Usage: sandbox-droplet.sh {up|down|status|ssh|sync-in|sync-out|exec \"cmd\"}"
        echo ""
        echo "Disposable execution sandbox for reeree daemons."
        echo "Cost: ~\$0.009/hr (s-1vcpu-1gb). Destroy when done."
        echo ""
        echo "Environment variables:"
        echo "  SANDBOX_SIZE=s-2vcpu-2gb   # Override droplet size"
        exit 1
        ;;
esac
