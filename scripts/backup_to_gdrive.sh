#!/usr/bin/env bash
# ==============================================================================
# Shorekeeper Sanctuary - Automated Backup to Google Drive (via Rclone)
# ==============================================================================
set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLOG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
GDRIVE_REMOTE="${GDRIVE_REMOTE:-gdrive:Shorekeeper-Backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
BACKUP_TEMP="$(mktemp -d /tmp/shorekeeper_backup_XXXXXX)"
ARCHIVE_FILE="/tmp/halo_backup_${TIMESTAMP}.tar.gz"

log() {
  echo -e "\033[0;36m[$(date +'%Y-%m-%d %H:%M:%S')]\033[0m $*"
}

cleanup() {
  log "🧹 Cleaning up temporary files..."
  rm -rf "${BACKUP_TEMP}" "${ARCHIVE_FILE}"
}
trap cleanup EXIT

log "✨ Initiating Sanctuary Data Backup [${TIMESTAMP}]..."

# 1. Verify Rclone Availability
if ! command -v rclone &>/dev/null; then
  if [[ -x "/home/luna/.local/bin/rclone" ]]; then
    export PATH="/home/luna/.local/bin:${PATH}"
  else
    echo "❌ Error: rclone is not found in PATH." >&2
    exit 1
  fi
fi

# 2. Verify Google Drive Remote Configuration
REMOTE_NAME="${GDRIVE_REMOTE%%:*}"
if ! rclone listremotes | grep -q "^${REMOTE_NAME}:"; then
  echo "⚠️ Warning: Rclone remote '${REMOTE_NAME}' is not configured yet." >&2
  echo "Please run 'rclone config' to authenticate your Google Drive remote as '${REMOTE_NAME}'." >&2
  exit 1
fi

# 3. Dump PostgreSQL Database
log "📦 Exporting PostgreSQL database (halo-shorekeeper-db)..."
mkdir -p "${BACKUP_TEMP}/db"
docker exec halo-shorekeeper-db pg_dump -U halo -d halo > "${BACKUP_TEMP}/db/halo_database.sql"
gzip -9 "${BACKUP_TEMP}/db/halo_database.sql"

# 4. Copy Uploaded Media Files
log "🖼️  Archiving media upload streams..."
mkdir -p "${BACKUP_TEMP}/media"
if [[ -d "${BLOG_DIR}/halo-data/upload" ]]; then
  cp -r "${BLOG_DIR}/halo-data/upload" "${BACKUP_TEMP}/media/"
fi

# 5. Package Snapshot Archive
log "🗜️  Compressing consolidated backup archive..."
tar -czf "${ARCHIVE_FILE}" -C "${BACKUP_TEMP}" .
ARCHIVE_SIZE="$(du -h "${ARCHIVE_FILE}" | cut -f1)"
log "Archive created: ${ARCHIVE_FILE} (${ARCHIVE_SIZE})"

# 6. Upload Archive to Google Drive
log "🚀 Transmitting archive to Google Drive (${GDRIVE_REMOTE})..."
rclone copy "${ARCHIVE_FILE}" "${GDRIVE_REMOTE}/" --progress

# 7. Apply Rolling Retention Policy (Purge backups older than RETENTION_DAYS)
log "🕰️  Pruning Google Drive backups older than ${RETENTION_DAYS} days..."
rclone delete --min-age "${RETENTION_DAYS}d" "${GDRIVE_REMOTE}/" || true

log "🌟 Sanctuary backup completed successfully! (${ARCHIVE_SIZE} safely stored on Google Drive)"
