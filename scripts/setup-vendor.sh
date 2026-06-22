#!/usr/bin/env bash
# =============================================================================
# StarVoyage — Vendor Dependency Setup (Bash)
# =============================================================================
# Clones ShortGPT & OpenMontage into vendor/ so they live inside the project
# directory instead of being installed globally.
#
# Usage:  bash scripts/setup-vendor.sh
# =============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENDOR_DIR="$PROJECT_DIR/vendor"

echo "==> Setting up vendor dependencies in: $VENDOR_DIR"
mkdir -p "$VENDOR_DIR"

# ── ShortGPT ─────────────────────────────────────────────────────────────
if [ -d "$VENDOR_DIR/ShortGPT" ]; then
    echo "    ShortGPT already exists, updating..."
    cd "$VENDOR_DIR/ShortGPT" && git pull --ff-only
else
    echo "    Cloning ShortGPT..."
    git clone --depth 1 https://github.com/RayVentura/ShortGPT.git "$VENDOR_DIR/ShortGPT"
fi

# ── OpenMontage ──────────────────────────────────────────────────────────
if [ -d "$VENDOR_DIR/OpenMontage" ]; then
    echo "    OpenMontage already exists, updating..."
    cd "$VENDOR_DIR/OpenMontage" && git pull --ff-only
else
    echo "    Cloning OpenMontage..."
    git clone --depth 1 https://github.com/calesthio/OpenMontage.git "$VENDOR_DIR/OpenMontage"
fi

# ── Install their Python dependencies ────────────────────────────────────
echo ""
echo "==> Installing vendor dependency requirements..."
pip install -q -r "$VENDOR_DIR/ShortGPT/requirements.txt" 2>/dev/null || true
if [ -f "$VENDOR_DIR/OpenMontage/requirements.txt" ]; then
    pip install -q -r "$VENDOR_DIR/OpenMontage/requirements.txt" 2>/dev/null || true
fi

echo ""
echo "✅ Vendor setup complete!"
echo "   ShortGPT:    $VENDOR_DIR/ShortGPT"
echo "   OpenMontage: $VENDOR_DIR/OpenMontage"
echo ""
echo "   These are now importable because src/__init__.py adds vendor/ to sys.path."
