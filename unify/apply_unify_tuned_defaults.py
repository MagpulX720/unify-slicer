# Unify Slicer: tuned defaults (Nov 22 2026), from the Eryone Silk PLA Silver tests (samples A-I).
# Runs from apply_unify_phase3.py, before the build copies resources/unify_profiles into the Snapmaker bundle.
#   - Every Unify process profile gets the tuned settings below (each keeps its own layer height, walls and speeds).
#   - New process profile: Unify Silk PLA 0.20 Shine (Balanced + tuned settings + silk speeds, Classic walls).
#   - New filament profile: Eryone Silk PLA Silver @U1 0.4 nozzle (Unify PLA + the calibrated values).
# To change a default later, edit the tables here.
import glob, json, os

print("Applying Unify tuned defaults (Nov 22)")
_P = ROOT / "resources/unify_profiles/Snapmaker"

TUNED = {
    "outer_wall_speed": ["50", "50"], "top_surface_speed": ["40", "50"], "top_solid_infill_flow_ratio": "1",
    "max_volumetric_extrusion_rate_slope": "16", "max_volumetric_extrusion_rate_slope_segment_length": ["1", "3"],
    "extrusion_rate_smoothing_external_perimeter_only": ["1", "0"],
    "seam_position": "back", "seam_gap": "5%", "seam_slope_type": "none", "scarf_joint_flow_ratio": "0.92",
    "wipe_on_loops": "1", "wipe_before_external_loop": "1",
    "extra_perimeters_on_overhangs": "1", "overhang_reverse": "1", "overhang_reverse_internal_only": "1",
    "overhang_reverse_threshold": "0%", "enable_overhang_speed": ["1", "1"],
    "overhang_1_4_speed": ["40", "40"], "overhang_2_4_speed": ["25", "25"], "overhang_3_4_speed": ["15", "15"],
    "overhang_4_4_speed": ["10", "10"], "slowdown_for_curled_perimeters": "0",
    "unify_inner_wall_slowdown": "manual", "unify_inner_wall_slowdown_angle": "50", "unify_inner_wall_slowdown_pct": "40%",
    "unify_overhang_layers": "1", "unify_overhang_layers_manual_min": "1", "unify_overhang_layers_min": "0.12",
    "unify_overhang_layers_manual_steps": "1", "unify_overhang_layers_steps": "5", "unify_bridge_smart_direction": "1",
}
NOTE = (" Tuned defaults (Nov 22 2026, from the Eryone Silk PLA tests): outer wall 50 mm/s, top 40 mm/s, top flow 1.0, "
        "seam back / gap 5% / no scarf, smoothing 16 outer walls only, extra perimeters + reverse on even (internal) on "
        "overhangs, inner wall slowdown 40% from 50 deg, Overhang layer height on (min 0.12, 5 transition layers).")

def _load(rel):
    return json.load(open(_P / rel, encoding="utf-8"))

def _save(rel, d):
    json.dump(d, open(_P / rel, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  + {rel}")

_silk_rel = "process/Unify Silk PLA 0.20 Shine @Snapmaker U1 (0.4 nozzle).json"
for _f in sorted(glob.glob(str(_P / "process" / "*.json"))):
    _rel = "process/" + os.path.basename(_f)
    if _rel == _silk_rel:
        continue
    _d = _load(_rel)
    _d.update(TUNED)
    if NOTE.strip()[:20] not in _d.get("description", ""):
        _d["description"] = _d.get("description", "") + NOTE
    _save(_rel, _d)

_d = _load("process/Unify PLA 0.20 Balanced @Snapmaker U1 (0.4 nozzle).json")
_d.update({"name": "Unify Silk PLA 0.20 Shine @Snapmaker U1 (0.4 nozzle)", "setting_id": "UNIFY_P006",
           "description": "Unify house profile for silk PLA (tuned Nov 21-22 2026 with Eryone Silk PLA Silver, samples A-I): "
                          "slower walls and smoothing for shine and a clean seam. Classic walls; switch to Arachne for toys "
                          "with thin features." + NOTE,
           "inner_wall_speed": ["80", "80"], "sparse_infill_speed": ["110", "110"], "internal_solid_infill_speed": ["90", "90"],
           "bridge_speed": ["15", "25"], "wall_generator": "classic"})
_save(_silk_rel, _d)

ERYONE = {
    "nozzle_temperature": "210", "nozzle_temperature_initial_layer": "210", "filament_flow_ratio": "0.99",
    "pressure_advance": "0.04", "enable_pressure_advance": "1", "filament_max_volumetric_speed": "10",
    "fan_min_speed": "70", "fan_max_speed": "100", "additional_cooling_fan_speed": "70", "overhang_fan_speed": "100",
    "overhang_fan_threshold": "10%", "internal_bridge_fan_speed": "100", "full_fan_speed_layer": "3",
    "close_fan_the_first_x_layers": "1", "slow_down_layer_time": "8", "slow_down_min_speed": "20",
    "filament_retraction_length": "0.8", "filament_retraction_speed": "40", "filament_density": "1.24", "filament_cost": "20",
    "default_filament_colour": "#8C9099",
    "hot_plate_temp": "60", "hot_plate_temp_initial_layer": "60", "textured_plate_temp": "60",
    "textured_plate_temp_initial_layer": "60", "cool_plate_temp": "35", "cool_plate_temp_initial_layer": "35",
    "eng_plate_temp": "55", "eng_plate_temp_initial_layer": "55", "textured_cool_plate_temp": "40",
    "textured_cool_plate_temp_initial_layer": "40", "supertack_plate_temp": "50", "supertack_plate_temp_initial_layer": "50",
    "graphic_effect_plate_temp": "60", "graphic_effect_plate_temp_initial_layer": "60",
}
ERYONE_NOTES = (
    "TUNED Nov 21-22 2026 on Snapmaker U1 / Unify 0.9.0 Beta (test samples A-I). Final = Sample I.\n\nCALIBRATION\n"
    "- Pressure advance 0.04 (PA Pattern 0-0.08 step 0.005; best 0.04-0.045). Enable PA ON. The U1 auto value resets to 0 when filament is unloaded, so it is fixed here.\n"
    "- Flow ratio 0.99 (YOLO test; best tile +0.01, rings from +0.03).\n\nFILAMENT (changed vs original profile)\n"
    "- Nozzle 210 C all layers (was 215 / 220 first layer): less tip curl.\n- Flow ratio 0.99 (was 0.98).\n"
    "- Pressure advance 0.04, enabled (was off).\n\nPROCESS (changed vs original profile)\n"
    "- Outer wall 50 mm/s (was 100): main fix for seam bulge, shinier walls.\n"
    "- Top surface flow ratio 1.0 (was 0.97): fixed grid showing through tops. Top surface speed 40 (was 50).\n"
    "- Extrusion rate smoothing 16 mm3/s2, outer walls only (was 50); segment length 1 mm (was 4): gradual slowdown into overhangs.\n"
    "- Overhang layer height ON: min 0.12, 5 steps (prints ~0.144 mm). Below ~0.1 mm the tips curled (Unify bug #17 with 2+ objects).\n"
    "- Extra perimeters on overhangs ON. Reverse on even = internal walls only (outer-wall reverse caused a double seam).\n"
    "- Seam: scarf OFF, position Back, seam gap 5%, restart extra 0. Gives a thin straight line. Scarf 0.92 bulged, 0.88 was fuzzy/starved; restart -0.04 left a gap line.\n"
    "- Slow down for curled perimeters OFF (keep off).\n"
    "- Wall generator: Classic for test prints; use Arachne for toys with thin features.\n\nRESULTS / LIMITS\n"
    "- 45-60 deg overhang faces: clean. 70 deg faces print but rough with small sags (hidden surfaces only).\n"
    "- Corner edges are steeper than faces (45 face = ~55 edge, 60 = ~68, 70 = ~76). Keep visible corner edges <= 60 deg; chamfer/blunt sharp tips.\n"
    "- Seams: thin line, small blob at the first-layer start only. Paint the seam to the back on display pieces.")
_f = _load("filament/Unify PLA @U1 0.4 nozzle.json")
for _k in [k for k in _f if k.startswith("unify_overhang_auto")]:
    del _f[_k]
_f.update({"name": "Eryone Silk PLA Silver @U1 0.4 nozzle", "setting_id": "UNIFY_F003", "filament_vendor": ["Eryone"]})
for _k, _v in ERYONE.items():
    _f[_k] = [_v]
_f["filament_notes"] = [ERYONE_NOTES]
_save("filament/Eryone Silk PLA Silver @U1 0.4 nozzle.json", _f)

# --- Issue #17 (Nov 22): Overhang layer height must match on every object of the plate --------------------------
# Objects with different Overhang layer height settings slice on different layer schedules; the owner chose to allow
# only plates where every object uses the same settings, so that case can't happen.
edit("src/libslic3r/Print.cpp",
     "    if (extruders.empty())\n        return { L(\"No extrusions under current settings.\") };\n",
     "    if (extruders.empty())\n        return { L(\"No extrusions under current settings.\") };\n\n"
     "    // Unify Slicer: Overhang layer height must be set the same way for every object on the plate (issue #17)\n"
     "    if (m_objects.size() > 1) {\n"
     "        const PrintObjectConfig &c0 = m_objects.front()->config();\n"
     "        for (const PrintObject *obj : m_objects) {\n"
     "            const PrintObjectConfig &c = obj->config();\n"
     "            const bool differs = c.unify_overhang_layers.value != c0.unify_overhang_layers.value ||\n"
     "                (c0.unify_overhang_layers.value &&\n"
     "                 (c.unify_overhang_layers_manual_min.value != c0.unify_overhang_layers_manual_min.value ||\n"
     "                  std::abs(c.unify_overhang_layers_min.value - c0.unify_overhang_layers_min.value) > EPSILON ||\n"
     "                  c.unify_overhang_layers_manual_steps.value != c0.unify_overhang_layers_manual_steps.value ||\n"
     "                  c.unify_overhang_layers_steps.value != c0.unify_overhang_layers_steps.value));\n"
     "            if (differs)\n"
     "                return { L(\"Overhang layer height must be set the same way for every object on the plate. \"\n"
     "                           \"Match it on all objects (or turn it off on all of them), then slice again.\"),\n"
     "                         obj, \"unify_overhang_layers\" };\n"
     "        }\n"
     "    }\n",
     "Overhang layer height must be set the same way for every object on the plate (issue #17)")
