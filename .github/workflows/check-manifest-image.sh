#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <manifest-file> <series-file>" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

manifest_file=$1
series_file=$2
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

release_output=$(bash "${script_dir}/resolve-release-version.sh" "${series_file}")
floating_tags=$(printf '%s\n' "${release_output}" | awk -F= '$1 == "floating_tags" { print $2; exit }')

if [[ -z "${floating_tags}" ]]; then
  echo "resolve-release-version.sh did not emit floating_tags" >&2
  exit 1
fi

expected_tag=
IFS=, read -r -a floating_tag_list <<< "${floating_tags}"
for floating_tag in "${floating_tag_list[@]}"; do
  [[ -n "${floating_tag}" ]] || continue
  expected_tag=${floating_tag}
done

if [[ -z "${expected_tag}" ]]; then
  echo "could not determine expected floating tag from ${series_file}" >&2
  exit 1
fi

EXPECTED_TAG="${expected_tag}" python3 - "${manifest_file}" "${series_file}" <<'PY'
import os
import re
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
series_path = Path(sys.argv[2])
expected_tag = os.environ["EXPECTED_TAG"]

try:
    manifest_text = manifest_path.read_text(encoding="utf-8")
except FileNotFoundError:
    print(f"manifest file does not exist: {manifest_path}", file=sys.stderr)
    sys.exit(1)

image_match = re.search(r'program\s*:\s*\{.*?\bimage\s*:\s*"([^"]+)"', manifest_text, re.DOTALL)
if image_match is None:
    print(f"could not find program.image in {manifest_path}", file=sys.stderr)
    sys.exit(1)

image_ref = image_match.group(1)
reference_without_digest, _, _ = image_ref.partition("@")
last_path_segment = reference_without_digest.rsplit("/", 1)[-1]
if ":" not in last_path_segment:
    print(
        f"program.image in {manifest_path} must use a tagged image reference, found: {image_ref}",
        file=sys.stderr,
    )
    sys.exit(1)

manifest_tag = reference_without_digest.rsplit(":", 1)[1]
if manifest_tag != expected_tag:
    print("amber manifest image tag does not match version-series.txt", file=sys.stderr)
    print(f"manifest: {manifest_path}", file=sys.stderr)
    print(f"series file: {series_path}", file=sys.stderr)
    print(f"program.image: {image_ref}", file=sys.stderr)
    print(f"expected floating tag: {expected_tag}", file=sys.stderr)
    sys.exit(1)

print(f"amber manifest image tag matches version-series.txt: {image_ref}")
PY
