#!/usr/bin/env bash

set -euo pipefail

managed_tag_marker='managed-by=agentbeats-gateway-ci'

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <series-file> [image-ref]" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required" >&2
  exit 1
fi

series_file=$1
image_ref=${2:-}
series=$(tr -d '[:space:]' <"${series_file}")

if [[ -z "${series}" ]]; then
  echo "version series file is empty: ${series_file}" >&2
  exit 1
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "must be run from within a git repository" >&2
  exit 1
fi

tag_exists() {
  git rev-parse -q --verify "refs/tags/$1" >/dev/null 2>&1
}

is_managed_tag() {
  local tag=$1
  local object_type

  object_type=$(git for-each-ref --format='%(objecttype)' "refs/tags/${tag}")
  [[ "${object_type}" == "tag" ]] || return 1
  git for-each-ref --format='%(contents)' "refs/tags/${tag}" | grep -Fxq "${managed_tag_marker}"
}

floating_tags=()
version_tag_pattern=

if [[ "${series}" =~ ^([0-9]+)\.([0-9]+)\.x$ ]]; then
  major=${BASH_REMATCH[1]}
  minor=${BASH_REMATCH[2]}
  version_prefix="v${major}.${minor}."
  if (( major > 0 )); then
    floating_tags=("v${major}" "v${major}.${minor}")
  else
    floating_tags=("v${major}.${minor}")
  fi
  version_tag_pattern="^v${major}\\.${minor}\\.([0-9]+)$"
elif [[ "${series}" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)-([0-9A-Za-z.-]+)\.x$ ]]; then
  major=${BASH_REMATCH[1]}
  minor=${BASH_REMATCH[2]}
  patch=${BASH_REMATCH[3]}
  prerelease=${BASH_REMATCH[4]}
  prerelease_pattern=${prerelease//./\\.}
  version_prefix="v${major}.${minor}.${patch}-${prerelease}."
  floating_tags=("v${major}.${minor}.${patch}-${prerelease}")
  version_tag_pattern="^v${major}\\.${minor}\\.${patch}-${prerelease_pattern}\\.([0-9]+)$"
else
  echo "unsupported version series: ${series}" >&2
  echo "expected MAJOR.MINOR.x or MAJOR.MINOR.PATCH-PRERELEASE.x" >&2
  exit 1
fi

head_commit=$(git rev-parse HEAD^{commit})
max_index=-1
head_index=-1

while IFS= read -r tag; do
  local_index=

  [[ -n "${tag}" ]] || continue
  [[ "${tag}" =~ ${version_tag_pattern} ]] || continue
  local_index=$((10#${BASH_REMATCH[1]}))

  if ! is_managed_tag "${tag}"; then
    continue
  fi

  if (( local_index > max_index )); then
    max_index=${local_index}
  fi

  if [[ "$(git rev-list -n 1 "refs/tags/${tag}")" == "${head_commit}" ]] && (( local_index > head_index )); then
    head_index=${local_index}
  fi
done < <(git for-each-ref --format='%(refname:strip=2)' refs/tags)

if (( head_index >= 0 )); then
  next_index=${head_index}
else
  next_index=$((max_index + 1))
fi

version_tag="${version_prefix}${next_index}"
version="${version_tag#v}"

if tag_exists "${version_tag}" && ! is_managed_tag "${version_tag}"; then
  echo "version tag exists but is not managed by CI: ${version_tag}" >&2
  exit 1
fi

release_tags=("${version_tag}")
for floating_tag in "${floating_tags[@]}"; do
  release_tags+=("${floating_tag}")
done

printf 'version=%s\n' "${version}"
printf 'version_tag=%s\n' "${version_tag}"
printf 'floating_tags=%s\n' "$(IFS=,; echo "${floating_tags[*]}")"
printf 'git_tags<<__GIT_TAGS__\n'
printf '%s\n' "${release_tags[@]}"
printf '__GIT_TAGS__\n'

if [[ -n "${image_ref}" ]]; then
  image_tags=()
  for release_tag in "${release_tags[@]}"; do
    image_tags+=("${image_ref}:${release_tag}")
  done

printf 'image_tags<<__IMAGE_TAGS__\n'
printf '%s\n' "${image_tags[@]}"
printf '__IMAGE_TAGS__\n'
fi
