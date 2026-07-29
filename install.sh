#!/bin/sh
# Install or update the LoopSpec CLI.
#
#   curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh
#
# The same command does both: an existing install is overwritten with the target
# version. Set LOOPSPEC_VERSION=0.1.0 to pin a version instead of taking the
# latest release.
#
# Every download is verified against the release's checksums.txt before anything
# is installed, and there is deliberately no way to skip that. Nothing here needs
# sudo and nothing is written outside your uv/pipx tool directory.
#
# Everything lives in functions and main is called on the last line, so a
# truncated download can never execute half an install.

set -eu

REPO="mingyuans/LoopSpec"
VERSION_PATTERN='^[0-9]\{1,\}\.[0-9]\{1,\}\.[0-9]\{1,\}\([._-]\{0,1\}\(a\|b\|rc\|alpha\|beta\|dev\|post\)[0-9]\{1,\}\)\{0,1\}$'

log() {
	printf '%s\n' "$*"
}

die() {
	printf 'error: %s\n' "$*" >&2
	exit 1
}

# Only ever https, and never downgraded to http by a redirect.
fetch() {
	curl -fsSL --proto '=https' --tlsv1.2 "$1"
}

fetch_to() {
	curl -fsSL --proto '=https' --tlsv1.2 -o "$2" "$1"
}

# The gate every externally-supplied version string has to pass before it is
# allowed anywhere near a URL, a filename or a command argument.
validate_version() {
	printf '%s' "$1" | grep -q "$VERSION_PATTERN" || die "not a valid version: '$1'"
}

resolve_version() {
	if [ -n "${LOOPSPEC_VERSION:-}" ]; then
		validate_version "$LOOPSPEC_VERSION"
		printf '%s' "$LOOPSPEC_VERSION"
		return
	fi

	api_url="https://api.github.com/repos/$REPO/releases/latest"
	if ! response=$(fetch "$api_url"); then
		die "could not query the latest release ($api_url).
  If the network is fine, the API rate limit may be the cause, or the
  repository may have no releases yet. Pin a version to skip this lookup:
    curl -fsSL <this script's url> | LOOPSPEC_VERSION=0.1.0 sh"
	fi

	# Deliberately lenient extraction, strict validation: no jq dependency, and
	# whatever comes out still has to satisfy validate_version.
	tag=$(printf '%s' "$response" |
		sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' |
		head -n 1)
	[ -n "$tag" ] || die "could not find tag_name in the latest release response"

	version=${tag#v}
	validate_version "$version"
	printf '%s' "$version"
}

# Locate the wheel's line in checksums.txt by exact basename match.
#
# A substring match would let 0.1.0 hit 0.1.0.post1, and "no line found" must
# count as a verification failure rather than a pass -- hence the explicit
# "exactly one line" assertion. --ignore-missing is not an option: macOS shasum
# does not have it, and implementations disagree on what "zero files checked"
# means.
extract_checksum_line() {
	checksums_file=$1
	wheel_name=$2
	output=$3

	awk -v want="$wheel_name" '
		{
			name = $2
			sub(/^\*/, "", name)       # sha256sum binary-mode marker
			if (name == want) print
		}
	' "$checksums_file" >"$output"

	matches=$(wc -l <"$output" | tr -d ' ')
	if [ "$matches" -eq 0 ]; then
		die "no checksum entry for $wheel_name in checksums.txt -- refusing to install unverified"
	fi
	if [ "$matches" -gt 1 ]; then
		die "$matches checksum entries for $wheel_name -- ambiguous, refusing to install"
	fi
}

verify_checksum() {
	workdir=$1
	if command -v sha256sum >/dev/null 2>&1; then
		(cd "$workdir" && sha256sum -c wheel.sha256 >/dev/null) ||
			die "checksum verification failed -- the downloaded wheel does not match the release"
	elif command -v shasum >/dev/null 2>&1; then
		(cd "$workdir" && shasum -a 256 -c wheel.sha256 >/dev/null) ||
			die "checksum verification failed -- the downloaded wheel does not match the release"
	else
		die "no sha256 tool found (need sha256sum or shasum) -- refusing to install unverified"
	fi
}

# Installs from the local, already-verified file: letting the installer fetch the
# URL itself would mean the bytes we checked are not the bytes we install.
install_wheel() {
	wheel_path=$1
	if command -v uv >/dev/null 2>&1; then
		log "Installing with uv..."
		uv tool install --force "$wheel_path"
	elif command -v pipx >/dev/null 2>&1; then
		log "Installing with pipx..."
		pipx install --force "$wheel_path"
	else
		die "need uv or pipx to install, found neither.
  Install uv:
    curl -LsSf https://astral.sh/uv/install.sh | sh
  ...then re-run this script."
	fi
}

report_result() {
	version=$1
	if command -v loopspec >/dev/null 2>&1; then
		log "Installed: $(loopspec version)"
		return 0
	fi
	# The package is installed; only this shell's PATH is stale, so this is a
	# warning rather than a failure.
	log "Installed loopspec $version, but it is not on your PATH yet."
	log ""
	log "  uv:   uv tool update-shell   (then restart your shell)"
	log "  pipx: pipx ensurepath        (then restart your shell)"
	log ""
	log "Or add the tool directory (usually ~/.local/bin) to PATH yourself."
	return 0
}

main() {
	command -v curl >/dev/null 2>&1 || die "curl is required"

	version=$(resolve_version)
	wheel_name="loopspec-$version-py3-none-any.whl"
	base_url="https://github.com/$REPO/releases/download/v$version"

	tmp=$(mktemp -d)
	trap 'rm -rf "$tmp"' EXIT INT TERM

	log "Downloading loopspec $version..."
	fetch_to "$base_url/$wheel_name" "$tmp/$wheel_name" ||
		die "could not download $base_url/$wheel_name"
	fetch_to "$base_url/checksums.txt" "$tmp/checksums.txt" ||
		die "could not download $base_url/checksums.txt"

	extract_checksum_line "$tmp/checksums.txt" "$wheel_name" "$tmp/wheel.sha256"
	verify_checksum "$tmp"
	log "Checksum verified."

	install_wheel "$tmp/$wheel_name"
	report_result "$version"
}

main "$@"
