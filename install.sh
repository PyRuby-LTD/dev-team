#!/usr/bin/env bash
# Install only the launcher alias; tools and authentication belong to the user.
set -e
checkout=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
if [[ "$checkout" =~ [[:space:]] || "$checkout" == *[\*\?\[\]\(\)\"\'\\]* ]]; then
    echo "Harness checkout path cannot contain whitespace or * ? [ ] ( ) \" ' \\" >&2
    exit 1
fi

missing=0
for tool in uv git; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Missing required prerequisite: $tool" >&2
        missing=1
    fi
done
for tool in claude codex gh; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "WARNING: $tool is missing from PATH" >&2
    fi
done
if command -v git >/dev/null 2>&1; then
    for key in user.name user.email; do
        if [[ -z "$(git config --get "$key" || true)" ]]; then
            echo "WARNING: git $key is not configured" >&2
        fi
    done
fi
if (( missing )); then
    exit 1
fi
if [[ -f "$HOME/.bashrc" ]] && grep -Eq '^[[:space:]]*alias[[:space:]]+dev-team=' "$HOME/.bashrc"; then
    echo "WARNING: dev-team alias already exists in ~/.bashrc; left unchanged" >&2
    exit 0
fi
printf '\nalias dev-team=\x27uv run --project "%s" python -P -m devteam\x27\n' "$checkout" >> "$HOME/.bashrc"
echo "Added dev-team alias to ~/.bashrc. Open a new shell or source ~/.bashrc."
