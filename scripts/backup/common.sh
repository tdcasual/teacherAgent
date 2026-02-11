#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

BACKUP_NAMESPACE="${BACKUP_NAMESPACE:-prod}"
BACKUP_STATE_DIR="${BACKUP_STATE_DIR:-${PROJECT_ROOT}/output/backups/state}"
BACKUP_WORK_DIR="${BACKUP_WORK_DIR:-${PROJECT_ROOT}/output/backups/work}"

mkdir -p "${BACKUP_STATE_DIR}" "${BACKUP_WORK_DIR}"

now_iso() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

now_compact() {
  date -u +"%Y%m%dT%H%M%SZ"
}

log() {
  printf '[backup] %s %s\n' "$(now_iso)" "$*"
}

die() {
  printf '[backup][error] %s %s\n' "$(now_iso)" "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

normalize_target() {
  local target="${1:-}"
  case "${target}" in
    s3|oss)
      printf '%s' "${target}"
      ;;
    *)
      die "invalid target '${target}', expected s3|oss"
      ;;
  esac
}

ensure_provider_env() {
  local target="$1"
  if [[ "${target}" == "s3" ]]; then
    [[ -n "${S3_BUCKET:-}" ]] || die "S3_BUCKET is required for target=s3"
    [[ -n "${AWS_ACCESS_KEY_ID:-}" ]] || die "AWS_ACCESS_KEY_ID is required for target=s3"
    [[ -n "${AWS_SECRET_ACCESS_KEY:-}" ]] || die "AWS_SECRET_ACCESS_KEY is required for target=s3"
    require_cmd aws
  else
    [[ -n "${OSS_BUCKET:-}" ]] || die "OSS_BUCKET is required for target=oss"
    [[ -n "${OSS_ENDPOINT:-}" ]] || die "OSS_ENDPOINT is required for target=oss"
    [[ -n "${OSS_ACCESS_KEY_ID:-}" ]] || die "OSS_ACCESS_KEY_ID is required for target=oss"
    [[ -n "${OSS_ACCESS_KEY_SECRET:-}" ]] || die "OSS_ACCESS_KEY_SECRET is required for target=oss"
    require_cmd ossutil
  fi
}

state_file_for_target() {
  local target="$1"
  printf '%s/latest_%s.json' "${BACKUP_STATE_DIR}" "${target}"
}

domain_paths_json() {
  cat <<'JSON'
[
  {"domain":"raw","path":"data/exams","required":false},
  {"domain":"raw","path":"data/assignments","required":false},
  {"domain":"raw","path":"uploads","required":false},
  {"domain":"derived","path":"data/analysis","required":false},
  {"domain":"serving","path":"data/student_profiles","required":false},
  {"domain":"serving","path":"data/teacher_workspaces","required":false},
  {"domain":"serving","path":"data/_system","required":false}
]
JSON
}

collect_domain_paths() {
  local work_json="$1"
  domain_paths_json >"${work_json}"
}

build_archive() {
  local archive_path="$1"
  local include_file="$2"
  local mode="$3"

  require_cmd tar

  if [[ "${mode}" == "incremental" ]]; then
    tar -czf "${archive_path}" -C "${PROJECT_ROOT}" --files-from "${include_file}"
  elif [[ "${mode}" == "full" ]]; then
    tar -czf "${archive_path}" -C "${PROJECT_ROOT}" --files-from "${include_file}"
  else
    die "unsupported snapshot type: ${mode}"
  fi
}

sha256_file() {
  local file_path="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${file_path}" | awk '{print $1}'
  else
    openssl dgst -sha256 "${file_path}" | awk '{print $2}'
  fi
}

upload_object() {
  local target="$1"
  local local_path="$2"
  local object_key="$3"

  if [[ "${target}" == "s3" ]]; then
    aws s3 cp "${local_path}" "s3://${S3_BUCKET}/${object_key}" --only-show-errors
  else
    local oss_uri="oss://${OSS_BUCKET}/${object_key}"
    ossutil cp -f "${local_path}" "${oss_uri}" --endpoint "${OSS_ENDPOINT}" >/dev/null
  fi
}

download_object() {
  local target="$1"
  local object_key="$2"
  local output_path="$3"

  if [[ "${target}" == "s3" ]]; then
    aws s3 cp "s3://${S3_BUCKET}/${object_key}" "${output_path}" --only-show-errors
  else
    local oss_uri="oss://${OSS_BUCKET}/${object_key}"
    ossutil cp -f "${oss_uri}" "${output_path}" --endpoint "${OSS_ENDPOINT}" >/dev/null
  fi
}

write_latest_state() {
  local target="$1"
  local state_payload="$2"
  local state_file
  state_file="$(state_file_for_target "${target}")"
  printf '%s\n' "${state_payload}" >"${state_file}"
}

load_latest_state() {
  local target="$1"
  local state_file
  state_file="$(state_file_for_target "${target}")"
  if [[ -f "${state_file}" ]]; then
    cat "${state_file}"
  else
    printf '{}'
  fi
}

