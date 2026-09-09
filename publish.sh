#!/usr/bin/env bash
# Clean, build, and publish LHT to PyPI.
#
# Order: read current version -> propose a bump -> confirm with the user ->
# clean old build artifacts -> build -> ask test or prod -> ask for the
# PyPI token -> upload. See BUILD_AND_DISTRIBUTION.md for the manual steps
# this automates.
set -euo pipefail

PYPROJECT="pyproject.toml"

die() { echo "Error: $*" >&2; exit 1; }
lower() { echo "$1" | tr '[:upper:]' '[:lower:]'; }

# Checks that a python module is importable with the python3 on PATH; if not,
# offers to pip install it into that same interpreter so the rest of the
# script (which uses `python3 -m build` / `python3 -m twine`) sees it too.
ensure_installed() {
    local module="$1" package="$2"
    python3 -c "import $module" 2>/dev/null && return 0

    echo "'$package' is not installed for $(command -v python3)."
    read -rp "Install it now with 'python3 -m pip install $package'? [y/N] " install_confirm
    if [[ "$(lower "$install_confirm")" == "y" || "$(lower "$install_confirm")" == "yes" ]]; then
        python3 -m pip install "$package" \
            || die "Failed to install $package. Install it manually: pip install $package"
        python3 -c "import $module" 2>/dev/null \
            || die "$package still not importable after install. Check you're using the intended Python environment (e.g. activate the right venv) and try again."
        echo "Installed $package."
    else
        die "$package is required. Install it manually: pip install $package"
    fi
}

[ -f "$PYPROJECT" ] || die "Run this from the repo root (pyproject.toml not found)."

command -v python3 >/dev/null 2>&1 || die "python3 not found on PATH."
ensure_installed build build
ensure_installed twine twine

# --- 1. current version ---
current_version=$(grep -m1 '^version = ' "$PYPROJECT" | sed -E 's/version = "(.*)"/\1/')
[ -n "$current_version" ] || die "Could not read a version from $PYPROJECT."

IFS='.' read -r major minor patch <<< "$current_version"
[[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ && "$patch" =~ ^[0-9]+$ ]] \
    || die "Version '$current_version' isn't in X.Y.Z form; edit $PYPROJECT manually."
default_next="$major.$minor.$((patch + 1))"

echo "Current version in $PYPROJECT: $current_version"

# Best-effort check against what's already live, so we don't propose a
# version that's behind PyPI (bit us once already: local said 2.0.73 while
# 2.0.74 was already published).
remote_latest=""
if command -v curl >/dev/null 2>&1; then
    remote_latest=$(curl -s --max-time 5 https://pypi.org/pypi/lht/json 2>/dev/null \
        | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    rs = [v for v, files in d.get('releases', {}).items() if files]
    rs.sort(key=lambda s: [int(x) for x in s.split('.')])
    print(rs[-1] if rs else '')
except Exception:
    print('')
" 2>/dev/null || true)
fi
[ -n "$remote_latest" ] && echo "Latest version on PyPI:       $remote_latest"

# --- 2. propose + confirm ---
read -rp "New version [$default_next]: " new_version
new_version="${new_version:-$default_next}"
[[ "$new_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "Version must look like X.Y.Z"

if [ -n "$remote_latest" ]; then
    lowest=$(printf '%s\n%s\n' "$new_version" "$remote_latest" | sort -V | head -n1)
    if [ "$new_version" = "$remote_latest" ] || [ "$lowest" = "$new_version" ]; then
        die "New version $new_version is not greater than the latest published version $remote_latest."
    fi
fi

echo
echo "  $current_version  ->  $new_version"
read -rp "Proceed with this version? [y/N] " confirm_version
[[ "$(lower "$confirm_version")" == "y" || "$(lower "$confirm_version")" == "yes" ]] || die "Aborted."

tmp=$(mktemp)
sed -E "s/^version = \".*\"/version = \"$new_version\"/" "$PYPROJECT" > "$tmp"
mv "$tmp" "$PYPROJECT"
echo "Updated $PYPROJECT to $new_version"
echo "(This is an uncommitted local change - commit it yourself once the publish succeeds.)"

# --- 3. clean ---
echo
echo "Cleaning previous build artifacts..."
rm -rf dist/ build/ src/lht.egg-info/ ./*.egg-info/

# --- 4. build ---
echo "Building package..."
python3 -m build || die "python3 -m build failed (see output above) - the script stops here and never reaches the test/prod prompt."

[ -d dist ] && [ -n "$(ls -A dist/ 2>/dev/null)" ] || die "Build produced no files in dist/."
echo
echo "Built:"
ls -1 dist/

# --- 5. test or prod ---
echo
read -rp "Publish to [test/prod]: " target
target=$(lower "$target")
case "$target" in
    test|t|testpypi)
        repo_args=(--repository-url https://test.pypi.org/legacy/)
        target_label="Test PyPI"
        verify_url="https://test.pypi.org/project/lht/$new_version/"
        token_env_var="LHT_PYPI_TOKEN_TEST"
        ;;
    prod|p|production|pypi)
        repo_args=()
        target_label="Production PyPI"
        verify_url="https://pypi.org/project/lht/$new_version/"
        token_env_var="LHT_PYPI_TOKEN_PROD"
        ;;
    *)
        die "Must be 'test' or 'prod'."
        ;;
esac

echo
echo "About to publish lht $new_version to $target_label."

# --- 6. token ---
if [ -n "${!token_env_var:-}" ]; then
    pypi_token="${!token_env_var}"
    echo "Using token from \$$token_env_var"
else
    read -rsp "PyPI API token (starts with pypi-, or set \$$token_env_var to skip this prompt): " pypi_token
    echo
fi
[ -n "$pypi_token" ] || die "No token entered."

TWINE_USERNAME="__token__" TWINE_PASSWORD="$pypi_token" python3 -m twine upload "${repo_args[@]}" dist/*
unset pypi_token

echo
echo "Published lht $new_version to $target_label."
echo "Verify: $verify_url"
