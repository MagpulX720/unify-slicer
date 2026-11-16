# Unify Slicer

Unify Slicer is a macOS build of **Snapmaker Orca** (itself built on **OrcaSlicer**, derived from Bambu Studio / PrusaSlicer) with:

- the official, current **Snapmaker U1** machine, process and filament profiles (pulled from `Snapmaker/snapmaker-profiles` at build time) bundled offline;
- **Unify house presets** for the U1 0.4 nozzle: PLA 0.20 Balanced, PLA 0.12 Fine Detail, PLA 0.20 Articulated (no supports), PETG 0.20 Balanced, PETG 0.24 Strong, plus Unify PLA / Unify PETG filaments (`resources/unify_profiles`);
- **Help > Ask Claude...**: a built-in assistant that sees your current settings and can apply suggested changes (uses your own Anthropic API key);
- its own settings folder (`~/Library/Application Support/Unify_Slicer`) so it never clashes with an installed Snapmaker Orca.

All Orca / Snapmaker Orca features are included: support, seam, color and fuzzy-skin painting, tree and organic supports, Arachne walls, Full Spectrum color mixing, calibration tools, U1 device control.

Source changes to upstream files are applied at build time by `unify/apply_unify.py`, so the fork can be synced with Snapmaker Orca easily.

Build: push to `main`, or run **Actions > Build Unify Slicer (macOS)**. The DMG appears under Releases. Licensed AGPL-3.0 like OrcaSlicer.
