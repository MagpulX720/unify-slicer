# Unify Slicer

Unify Slicer is a macOS build of **Snapmaker Orca** (itself built on **OrcaSlicer**, derived from Bambu Studio / PrusaSlicer) with:

- the official, current **Snapmaker U1** machine, process and filament profiles (pulled from `Snapmaker/snapmaker-profiles` at build time) bundled offline;
- **Unify house presets** for the U1 0.4 nozzle: PLA 0.20 Balanced, PLA 0.12 Fine Detail, PLA 0.20 Articulated (no supports), PETG 0.20 Balanced, PETG 0.24 Strong, plus Unify PLA / Unify PETG filaments (`resources/unify_profiles`). Speeds are the tuned "Speeds v2" set (cooling-limited walls, slower overhangs and bridges); slow down for curled perimeters is off;
- **Wall direction options**: alternate every layer or every N layers, start direction, and which walls (outer / inner / holes) follow it, plus **Calibration > Wall direction (Unify)** test plate;
- **Snapmaker U1 resonance fast check** (Printer settings > Basic information): optional X/Y input-shaper sweep at the start of each print;
- adaptive bed mesh on the U1;
- its own settings folder (`~/Library/Application Support/Unify_Slicer`) so it never clashes with an installed Snapmaker Orca.

All Orca / Snapmaker Orca features are included: support, seam, color and fuzzy-skin painting, tree and organic supports, Arachne walls, Full Spectrum color mixing, calibration tools, U1 device control.

Source changes to upstream files are applied at build time by `unify/apply_unify.py`, so the fork can be synced with Snapmaker Orca easily. Improvement requests are tracked in GitHub Issues.

Build: push to `main`, or run **Actions > Build Unify Slicer (macOS)**, or build locally with `unify/build_local_mac.sh`. The DMG appears under Releases. Licensed AGPL-3.0 like OrcaSlicer.
