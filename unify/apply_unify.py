#!/usr/bin/env python3
"""Apply the Unify Slicer changes to a Snapmaker Orca checkout (idempotent)."""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def edit(rel, old, new, marker):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    if marker in s:
        print(f"  = {rel} (already applied)")
        return
    if old not in s:
        sys.exit(f"ERROR: anchor not found in {rel}:\n{old[:120]}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")
    print(f"  + {rel}")


print("Applying Unify Slicer changes")

# Branding (display name only; internal file/target names stay the same)
edit("version.inc", 'set(SLIC3R_APP_NAME "Snapmaker Orca")', 'set(SLIC3R_APP_NAME "Unify Slicer")', '"Unify Slicer"')
edit("src/common_func/common_func.hpp", '#define SLIC3R_APP_NAME "Snapmaker Orca"', '#define SLIC3R_APP_NAME "Unify Slicer"', '"Unify Slicer"')
edit("src/CMakeLists.txt", 'MACOSX_BUNDLE_BUNDLE_NAME "Snapmaker Orca"', 'MACOSX_BUNDLE_BUNDLE_NAME "Unify Slicer"', 'MACOSX_BUNDLE_BUNDLE_NAME "Unify Slicer"')

# Own settings folder: ~/Library/Application Support/Unify_Slicer
edit("src/slic3r/GUI/GUI_App.cpp", "    SetAppName(SLIC3R_APP_KEY);\n",
     "    // Unify Slicer: separate settings folder so it never clashes with Snapmaker Orca\n    SetAppName(\"Unify_Slicer\");\n",
     'SetAppName("Unify_Slicer")')

# Profiles ship inside the app (official Snapmaker set + Unify presets): skip the Snapmaker cloud profile update,
# which would replace the bundled set and remove the Unify presets.
edit("src/slic3r/Utils/PresetUpdater.cpp", "void PresetUpdater::priv::sync_config(bool isAuto_check)\n{\n",
     "void PresetUpdater::priv::sync_config(bool isAuto_check)\n{\n"
     "    // Unify Slicer: bundled profiles are refreshed by each Unify build; cloud profile update disabled.\n"
     "    if (!isAuto_check) GUI::wxGetApp().QueueEvent(new wxCommandEvent(EVT_NO_PRESET_UPDATE));\n    return;\n",
     "Unify Slicer: bundled profiles")

# The app is the only source of Snapmaker profiles (cloud update disabled), so refresh the installed copy from the
# app every launch - otherwise profile changes in a new Unify build never reach an existing install.
edit("src/slic3r/Utils/PresetUpdater.cpp",
     "                        if (!version_match || (vendor_ver < resource_ver)) {\n",
     "                        // Unify Slicer: always refresh the Snapmaker bundle from the app\n"
     "                        if (!version_match || (vendor_ver < resource_ver) || vendor_name == PresetBundle::SM_BUNDLE) {\n",
     "Unify Slicer: always refresh the Snapmaker bundle")

# Merge Unify presets into the Snapmaker bundle after the profiles submodule is synced
OVERLAY = r'''# Unify Slicer: overlay the Unify house presets onto the synced Snapmaker bundle
# and register them in Snapmaker.json so they appear as system presets.
set(_unify_dir "${_repository}/resources/unify_profiles")
if(EXISTS "${_unify_dir}/Snapmaker")
    file(READ "${DST}/Snapmaker.json" _bundle)
    foreach(_kind process filament)
        file(GLOB _unify_files LIST_DIRECTORIES false "${_unify_dir}/Snapmaker/${_kind}/*.json")
        foreach(_uf IN LISTS _unify_files)
            get_filename_component(_fname "${_uf}" NAME)
            string(REGEX REPLACE "\\.json$" "" _pname "${_fname}")
            configure_file("${_uf}" "${DST}/Snapmaker/${_kind}/${_fname}" COPYONLY)
            string(JSON _n LENGTH "${_bundle}" "${_kind}_list")
            set(_entry "{\"name\": \"${_pname}\", \"sub_path\": \"${_kind}/${_fname}\"}")
            string(FIND "${_bundle}" "\"${_kind}/${_fname}\"" _already)
            if(_already EQUAL -1)
                string(JSON _bundle SET "${_bundle}" "${_kind}_list" ${_n} "${_entry}")
            endif()
        endforeach()
    endforeach()
    file(WRITE "${DST}/Snapmaker.json" "${_bundle}")
    message(STATUS "Unify Slicer: merged Unify presets into Snapmaker profiles")
endif()

'''
anchor = "# Report and record the revision only when it changes."
edit("cmake/SyncSnapmakerProfiles.cmake", anchor, OVERLAY + anchor, "Unify Slicer: overlay")
# Unify Slicer: adaptive bed mesh on the U1 - only probe where the first layer prints.
# Same command Snapmaker/OrcaSlicer use upstream; limits match the U1 printer.cfg [bed_mesh] area (3..267 mm).
MESH = r"""# Unify Slicer: adaptive bed mesh for the Snapmaker U1.
set(_u1_mesh "BED_MESH_CALIBRATE mesh_min={adaptive_bed_mesh_min[0]},{adaptive_bed_mesh_min[1]} mesh_max={adaptive_bed_mesh_max[0]},{adaptive_bed_mesh_max[1]} ALGORITHM=[bed_mesh_algo] PROBE_COUNT={bed_mesh_probe_count[0]},{bed_mesh_probe_count[1]} ADAPTIVE=0 ADAPTIVE_MARGIN=0")
file(GLOB _u1_machines LIST_DIRECTORIES false "${DST}/Snapmaker/machine/Snapmaker U1 (*nozzle).json")
foreach(_mf IN LISTS _u1_machines)
    file(READ "${_mf}" _mj)
    string(REPLACE "BED_MESH_CALIBRATE PROBE_COUNT=11,11" "${_u1_mesh}" _mj "${_mj}")
    file(WRITE "${_mf}" "${_mj}")
endforeach()
if(EXISTS "${DST}/Snapmaker/machine/fdm_U1.json")
    file(READ "${DST}/Snapmaker/machine/fdm_U1.json" _fj)
    string(JSON _fj SET "${_fj}" "bed_mesh_min" "\"3,3\"")
    string(JSON _fj SET "${_fj}" "bed_mesh_max" "\"267,267\"")
    string(JSON _fj SET "${_fj}" "bed_mesh_probe_distance" "\"25,25\"")
    string(JSON _fj SET "${_fj}" "adaptive_bed_mesh_margin" "\"5\"")
    file(WRITE "${DST}/Snapmaker/machine/fdm_U1.json" "${_fj}")
endif()
message(STATUS "Unify Slicer: adaptive bed mesh enabled for Snapmaker U1")

"""
edit("cmake/SyncSnapmakerProfiles.cmake", anchor, MESH + anchor, "Unify Slicer: adaptive bed mesh")
# Unify Slicer: Calibration > Wall direction test (issue #4). Sources + menu entries (Windows/Linux top bar and macOS menu bar).
edit("src/slic3r/CMakeLists.txt", "    GUI/WebPreprintDialog.cpp\n",
     "    GUI/WebPreprintDialog.cpp\n    GUI/UnifyCalibration.hpp\n    GUI/UnifyCalibration.cpp\n", "UnifyCalibration.cpp")
edit("src/slic3r/GUI/MainFrame.cpp", '#include "MainFrame.hpp"\n',
     '#include "MainFrame.hpp"\n#include "UnifyCalibration.hpp"\n', '#include "UnifyCalibration.hpp"')
edit("src/slic3r/GUI/MainFrame.cpp",
     "    // help\n    append_menu_item(m_topbar->GetCalibMenu(), wxID_ANY, _L(\"Tutorial\")",
     "    // Unify Slicer: wall direction test (top bar)\n"
     "    m_topbar->GetCalibMenu()->AppendSeparator();\n"
     "    append_menu_item(m_topbar->GetCalibMenu(), wxID_ANY, _L(\"Wall direction (Unify)\"), _L(\"Compare wall direction options on six towers\"),\n"
     "        [this](wxCommandEvent&) { if (m_plater) unify_calib_wall_direction(m_plater); }, \"\", nullptr,\n"
     "        [this]() {return m_plater->is_view3D_shown();; }, this);\n\n"
     "    // help\n    append_menu_item(m_topbar->GetCalibMenu(), wxID_ANY, _L(\"Tutorial\")",
     "Unify Slicer: wall direction test (top bar)")
edit("src/slic3r/GUI/MainFrame.cpp",
     "    m_menubar->Append(calib_menu,wxString::Format(\"&%s\", _L(\"Calibration\")));\n",
     "    // Unify Slicer: wall direction test (menu bar)\n"
     "    calib_menu->AppendSeparator();\n"
     "    append_menu_item(calib_menu, wxID_ANY, _L(\"Wall direction (Unify)\"), _L(\"Compare wall direction options on six towers\"),\n"
     "        [this](wxCommandEvent&) { if (m_plater) unify_calib_wall_direction(m_plater); }, \"\", nullptr,\n"
     "        [this]() {return m_plater->is_view3D_shown();; }, this);\n\n"
     "    m_menubar->Append(calib_menu,wxString::Format(\"&%s\", _L(\"Calibration\")));\n",
     "Unify Slicer: wall direction test (menu bar)")
# ---------------------------------------------------------------------------------------------
# Unify Slicer phase 1 (issues #1-#4)
# ---------------------------------------------------------------------------------------------

# --- #4 Wall direction: alternate every layer / every N layers, start direction, which walls ---
edit("src/libslic3r/PrintConfig.hpp",
     "    Clockwise,\n    Count,\n};",
     "    Clockwise,\n    // Unify Slicer: alternating wall direction (issue #4)\n    AlternateEveryLayer,\n    AlternateEveryN,\n    Count,\n};",
     "AlternateEveryLayer,")
edit("src/libslic3r/PrintConfig.hpp",
     "    ((ConfigOptionEnum<WallDirection>,  wall_direction))\n",
     "    ((ConfigOptionEnum<WallDirection>,  wall_direction))\n"
     "    // Unify Slicer: wall direction options (issue #4)\n"
     "    ((ConfigOptionInt,                 wall_direction_alternate_layers))\n"
     "    ((ConfigOptionBool,                wall_direction_start_cw))\n"
     "    ((ConfigOptionBool,                wall_direction_outer))\n"
     "    ((ConfigOptionBool,                wall_direction_inner))\n"
     "    ((ConfigOptionBool,                wall_direction_holes))\n",
     "wall_direction_alternate_layers))")
edit("src/libslic3r/PrintConfig.cpp",
     "    { \"cw\",   int(WallDirection::Clockwise)},\n",
     "    { \"cw\",   int(WallDirection::Clockwise)},\n"
     "    { \"alternate\",   int(WallDirection::AlternateEveryLayer)},\n"
     "    { \"alternate_n\", int(WallDirection::AlternateEveryN)},\n",
     "int(WallDirection::AlternateEveryLayer)")
WALLDIR_DEFS = r'''    // Unify Slicer: alternating wall direction (issue #4)
    def->enum_values.push_back("alternate");
    def->enum_values.push_back("alternate_n");
    def->enum_labels.push_back(L("Alternate every layer"));
    def->enum_labels.push_back(L("Alternate every N layers"));

    def = this->add("wall_direction_alternate_layers", coInt);
    def->label = L("Alternate every");
    def->category = L("Quality");
    def->tooltip = L("Number of layers printed in one direction before the wall direction flips (Alternate every N layers). Min 2, max 50.");
    def->sidetext = L("layers (2-50)");
    def->min = 2;
    def->max = 50;
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionInt(2));

    def = this->add("wall_direction_start_cw", coBool);
    def->label = L("Start clockwise");
    def->category = L("Quality");
    def->tooltip = L("Direction of the first layer when the wall direction alternates. Off = counter-clockwise first, on = clockwise first.");
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionBool(false));

    def = this->add("wall_direction_outer", coBool);
    def->label = L("Apply to outer walls");
    def->category = L("Quality");
    def->tooltip = L("Outer walls follow the wall direction. When off they stay counter-clockwise. Alternating outer walls can leave a slight texture.");
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionBool(true));

    def = this->add("wall_direction_inner", coBool);
    def->label = L("Apply to inner walls");
    def->category = L("Quality");
    def->tooltip = L("Inner walls follow the wall direction. When off they stay counter-clockwise.");
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionBool(true));

    def = this->add("wall_direction_holes", coBool);
    def->label = L("Apply to holes");
    def->category = L("Quality");
    def->tooltip = L("Walls around holes follow the wall direction. When off they stay counter-clockwise.");
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionBool(true));
'''
edit("src/libslic3r/PrintConfig.cpp",
     "    def->enum_labels.push_back(L(\"Clockwise\"));\n    def->mode = comAdvanced;\n    def->set_default_value(new ConfigOptionEnum<WallDirection>(WallDirection::Auto));\n",
     "    def->enum_labels.push_back(L(\"Clockwise\"));\n    def->mode = comAdvanced;\n    def->set_default_value(new ConfigOptionEnum<WallDirection>(WallDirection::Auto));\n" + WALLDIR_DEFS,
     "wall_direction_alternate_layers\", coInt")
edit("src/libslic3r/Preset.cpp",
     "    \"layer_height\", \"initial_layer_print_height\", \"wall_loops\", \"alternate_extra_wall\",",
     "    \"layer_height\", \"initial_layer_print_height\", \"wall_loops\", \"alternate_extra_wall\",\n"
     "    \"wall_direction_alternate_layers\", \"wall_direction_start_cw\", \"wall_direction_outer\", \"wall_direction_inner\", \"wall_direction_holes\",",
     "\"wall_direction_alternate_layers\", \"wall_direction_start_cw\"")
edit("src/libslic3r/PrintObject.cpp",
     "            || opt_key == \"wall_direction\"\n",
     "            || opt_key == \"wall_direction\"\n"
     "            || opt_key == \"wall_direction_alternate_layers\"\n"
     "            || opt_key == \"wall_direction_start_cw\"\n"
     "            || opt_key == \"wall_direction_outer\"\n"
     "            || opt_key == \"wall_direction_inner\"\n"
     "            || opt_key == \"wall_direction_holes\"\n",
     "opt_key == \"wall_direction_alternate_layers\"")
edit("src/libslic3r/Layer.cpp",
     "\t\t&& config.wall_direction                         == other_config.wall_direction\n",
     "\t\t&& config.wall_direction                         == other_config.wall_direction\n"
     "\t\t&& config.wall_direction_alternate_layers        == other_config.wall_direction_alternate_layers\n"
     "\t\t&& config.wall_direction_start_cw                == other_config.wall_direction_start_cw\n"
     "\t\t&& config.wall_direction_outer                   == other_config.wall_direction_outer\n"
     "\t\t&& config.wall_direction_inner                   == other_config.wall_direction_inner\n"
     "\t\t&& config.wall_direction_holes                   == other_config.wall_direction_holes\n",
     "config.wall_direction_alternate_layers")
PG_HELPERS = r'''
// Unify Slicer: alternating wall direction and which walls it applies to (issue #4).
// Turns "Alternate every layer / every N layers" into CW or CCW for this layer.
static WallDirection unify_resolve_wall_direction(const PrintRegionConfig &cfg, int layer_id)
{
    const WallDirection wd = cfg.wall_direction.value;
    if (wd != WallDirection::AlternateEveryLayer && wd != WallDirection::AlternateEveryN)
        return wd;
    const int  n    = wd == WallDirection::AlternateEveryLayer ? 1 : std::max(2, cfg.wall_direction_alternate_layers.value);
    const bool flip = ((std::max(0, layer_id) / n) % 2) == 1;
    return (cfg.wall_direction_start_cw.value != flip) ? WallDirection::Clockwise : WallDirection::CounterClockwise;
}

// After the loops were made clockwise, put the wall types the user excluded back to counter-clockwise.
static void unify_apply_wall_direction_scope(ExtrusionEntityCollection &entities, const PrintRegionConfig &cfg, WallDirection resolved)
{
    if (resolved != WallDirection::Clockwise)
        return;
    const bool outer = cfg.wall_direction_outer.value, inner = cfg.wall_direction_inner.value, holes = cfg.wall_direction_holes.value;
    if (outer && inner && holes)
        return;
    for (auto entity : entities) {
        if (!entity->is_loop())
            continue;
        ExtrusionLoop *eloop   = static_cast<ExtrusionLoop *>(entity);
        const bool     is_hole = (eloop->loop_role() & elrHole) == elrHole;
        bool           is_outer = false;
        for (const auto &path : eloop->paths)
            if (path.role() == erExternalPerimeter) { is_outer = true; break; }
        const bool apply = is_hole ? holes : (is_outer ? outer : inner);
        if (!apply)
            eloop->make_counter_clockwise();
    }
}
'''
edit("src/libslic3r/PerimeterGenerator.cpp",
     "\n// Reorient loop direction\nstatic void reorient_perimeters(",
     PG_HELPERS + "\n// Reorient loop direction\nstatic void reorient_perimeters(",
     "unify_resolve_wall_direction(const PrintRegionConfig")
edit("src/libslic3r/PerimeterGenerator.cpp",
     "            const WallDirection wall_direction = config->wall_direction;\n",
     "            const WallDirection wall_direction = unify_resolve_wall_direction(*config, this->layer_id); // Unify Slicer (classic)\n",
     "// Unify Slicer (classic)")
edit("src/libslic3r/PerimeterGenerator.cpp",
     "        const WallDirection wall_direction = config->wall_direction;\n",
     "        const WallDirection wall_direction = unify_resolve_wall_direction(*config, this->layer_id); // Unify Slicer (arachne)\n",
     "// Unify Slicer (arachne)")
edit("src/libslic3r/PerimeterGenerator.cpp",
     "                reorient_perimeters(entities, steep_overhang_contour, steep_overhang_hole,\n"
     "                                    // Reverse internal only if the wall direction is auto\n"
     "                                    this->config->overhang_reverse_internal_only && wall_direction == WallDirection::Auto);\n"
     "            }\n",
     "                reorient_perimeters(entities, steep_overhang_contour, steep_overhang_hole,\n"
     "                                    // Reverse internal only if the wall direction is auto\n"
     "                                    this->config->overhang_reverse_internal_only && wall_direction == WallDirection::Auto);\n"
     "            }\n"
     "            unify_apply_wall_direction_scope(entities, *config, wall_direction);\n",
     "unify_apply_wall_direction_scope(entities,")
edit("src/libslic3r/PerimeterGenerator.cpp",
     "            }\n            this->loops->append(extrusion_coll);\n",
     "            }\n            unify_apply_wall_direction_scope(extrusion_coll, *config, wall_direction);\n            this->loops->append(extrusion_coll);\n",
     "unify_apply_wall_direction_scope(extrusion_coll,")
CM_TOGGLES = r'''
    {   // Unify Slicer: wall direction options (issue #4)
        const WallDirection wd  = config->opt_enum<WallDirection>("wall_direction");
        const bool          alt = wd == WallDirection::AlternateEveryLayer || wd == WallDirection::AlternateEveryN;
        toggle_line("wall_direction_alternate_layers", !has_spiral_vase && wd == WallDirection::AlternateEveryN);
        toggle_line("wall_direction_start_cw", !has_spiral_vase && alt);
        for (auto el : {"wall_direction_outer", "wall_direction_inner", "wall_direction_holes"})
            toggle_line(el, !has_spiral_vase && wd != WallDirection::Auto);
        // at least one wall type must follow the direction
        if (!config->opt_bool("wall_direction_outer") && !config->opt_bool("wall_direction_inner") && !config->opt_bool("wall_direction_holes")) {
            DynamicPrintConfig new_conf = *config;
            new_conf.set_key_value("wall_direction_outer", new ConfigOptionBool(true));
            apply(config, &new_conf);
        }
    }
'''
edit("src/slic3r/GUI/ConfigManipulation.cpp",
     "    toggle_field(\"wall_direction\", !has_spiral_vase);\n",
     "    toggle_field(\"wall_direction\", !has_spiral_vase);\n" + CM_TOGGLES,
     "Unify Slicer: wall direction options (issue #4)")
edit("src/slic3r/GUI/Tab.cpp",
     "        optgroup->append_single_option_line(\"wall_direction\", \"quality_settings_wall_and_surfaces#wall-loop-direction\");\n",
     "        optgroup->append_single_option_line(\"wall_direction\", \"quality_settings_wall_and_surfaces#wall-loop-direction\");\n"
     "        // Unify Slicer: wall direction options (issue #4)\n"
     "        optgroup->append_single_option_line(\"wall_direction_alternate_layers\");\n"
     "        optgroup->append_single_option_line(\"wall_direction_start_cw\");\n"
     "        optgroup->append_single_option_line(\"wall_direction_outer\");\n"
     "        optgroup->append_single_option_line(\"wall_direction_inner\");\n"
     "        optgroup->append_single_option_line(\"wall_direction_holes\");\n",
     "append_single_option_line(\"wall_direction_alternate_layers\")")

# --- #1 Snapmaker U1 resonance fast check: printer settings + start G-code block ---
edit("src/libslic3r/PrintConfig.hpp",
     "    ((ConfigOptionString,              machine_start_gcode))\n",
     "    ((ConfigOptionString,              machine_start_gcode))\n"
     "    // Unify Slicer: Snapmaker U1 resonance fast check (issue #1)\n"
     "    ((ConfigOptionBool,                unify_resonance_check))\n"
     "    ((ConfigOptionInt,                 unify_resonance_check_time))\n",
     "unify_resonance_check))")
RES_DEFS = r'''    // Unify Slicer: Snapmaker U1 resonance fast check (issue #1)
    def = this->add("unify_resonance_check", coBool);
    def->label = L("Resonance fast check before each print");
    def->tooltip = L("Snapmaker U1: before each print, sweeps X and Y with the toolhead accelerometer (T0) and applies the best input shaper for that print only. Nothing is saved; the printer goes back to its calibrated values after a restart. Adds about 40-80 seconds to the start of the print.");
    def->mode = comSimple;
    def->set_default_value(new ConfigOptionBool(false));

    def = this->add("unify_resonance_check_time", coInt);
    def->label = L("Fast check sweep time per axis");
    def->tooltip = L("Seconds spent sweeping each axis. Min 20 s, max 40 s. Longer is more accurate. 40 s matches Klipper's standard calibration speed.");
    def->sidetext = L("s (20-40)");
    def->min = 20;
    def->max = 40;
    def->mode = comSimple;
    def->set_default_value(new ConfigOptionInt(40));

'''
edit("src/libslic3r/PrintConfig.cpp",
     "    def = this->add(\"machine_start_gcode\", coString);\n",
     RES_DEFS + "    def = this->add(\"machine_start_gcode\", coString);\n",
     "this->add(\"unify_resonance_check\", coBool)")
edit("src/libslic3r/Preset.cpp",
     "static std::vector<std::string> s_Preset_printer_options {\n    \"printer_technology\",\n",
     "static std::vector<std::string> s_Preset_printer_options {\n    \"printer_technology\",\n"
     "    \"unify_resonance_check\", \"unify_resonance_check_time\",\n",
     "\"unify_resonance_check\", \"unify_resonance_check_time\"")
edit("src/libslic3r/Print.cpp",
     "        \"machine_start_gcode\",\n        \"filament_start_gcode\",\n",
     "        \"machine_start_gcode\",\n        \"unify_resonance_check\",\n        \"unify_resonance_check_time\",\n        \"filament_start_gcode\",\n",
     "\"unify_resonance_check_time\",")
edit("src/slic3r/GUI/Tab.cpp",
     "        optgroup->append_single_option_line(\"time_cost\");\n",
     "        optgroup->append_single_option_line(\"time_cost\");\n\n"
     "        // Unify Slicer: Snapmaker U1 resonance fast check (issue #1)\n"
     "        optgroup = page->new_optgroup(L(\"Resonance fast check (Unify)\"), \"param_cooling_fan\");\n"
     "        optgroup->append_single_option_line(\"unify_resonance_check\");\n"
     "        optgroup->append_single_option_line(\"unify_resonance_check_time\");\n",
     "append_single_option_line(\"unify_resonance_check\")")
edit("src/slic3r/GUI/Tab.cpp",
     "\"adaptive_bed_mesh_margin\", \"thumbnails\"})\n          toggle_line(el, !is_BBL_printer);\n",
     "\"adaptive_bed_mesh_margin\", \"thumbnails\"})\n          toggle_line(el, !is_BBL_printer);\n"
     "        // Unify Slicer: sweep time only matters when the fast check is on\n"
     "        toggle_line(\"unify_resonance_check_time\", m_config->opt_bool(\"unify_resonance_check\"));\n",
     "toggle_line(\"unify_resonance_check_time\"")
FASTCHECK = r"""# Unify Slicer: optional resonance fast check in the U1 start G-code (issue #1), after the first Z home.
set(_u1_fastcheck "G28 Z I140 J140\\n{if unify_resonance_check}\\n; ===== Unify Slicer: resonance fast check ({unify_resonance_check_time} s per axis) =====\\nM400\\nM107\\nT0 ; accelerometer is on the T0 toolhead\\nM400\\nG4 P1000\\nRESPOND MSG=UNIFY_FASTCHECK_BEGIN\\nSHAPER_CALIBRATE AXIS=X FREQ_START=35 FREQ_END=75 HZ_PER_SEC={40.0 / unify_resonance_check_time} NAME=unify_fast\\nSHAPER_CALIBRATE AXIS=Y FREQ_START=30 FREQ_END=70 HZ_PER_SEC={40.0 / unify_resonance_check_time} NAME=unify_fast\\nRESPOND MSG=UNIFY_FASTCHECK_END\\nM400\\nT{initial_extruder}\\n; ===== end fast check =====\\n{endif}")
file(GLOB _u1_machines_fc LIST_DIRECTORIES false "${DST}/Snapmaker/machine/Snapmaker U1 (*nozzle).json")
foreach(_mf IN LISTS _u1_machines_fc)
    file(READ "${_mf}" _mj)
    string(FIND "${_mj}" "UNIFY_FASTCHECK_BEGIN" _has_fc)
    if(_has_fc EQUAL -1)
        string(REPLACE "G28 Z I140 J140" "${_u1_fastcheck}" _mj "${_mj}")
        file(WRITE "${_mf}" "${_mj}")
    endif()
endforeach()
message(STATUS "Unify Slicer: resonance fast check added to Snapmaker U1 start G-code")

"""
edit("cmake/SyncSnapmakerProfiles.cmake", anchor, FASTCHECK + anchor, "Unify Slicer: optional resonance fast check")

# Unify Slicer (issue #10): show all seven U1 build plates (incl. Cool Steel Plate) by default.
BEDTYPES = r"""# Unify Slicer: all build plates for the Snapmaker U1 (support_multi_bed_types on).
file(GLOB _u1_machines_bt LIST_DIRECTORIES false "${DST}/Snapmaker/machine/Snapmaker U1 (*nozzle).json" "${DST}/Snapmaker/machine/fdm_U1.json")
foreach(_mf IN LISTS _u1_machines_bt)
    file(READ "${_mf}" _mj)
    string(JSON _mj SET "${_mj}" "support_multi_bed_types" "\"1\"")
    file(WRITE "${_mf}" "${_mj}")
endforeach()
message(STATUS "Unify Slicer: all build plate types enabled for Snapmaker U1")

"""
edit("cmake/SyncSnapmakerProfiles.cmake", anchor, BEDTYPES + anchor, "Unify Slicer: all build plates")

# ---------------------------------------------------------------------------------------------
# Unify Slicer: build stamp + splash screen
# ---------------------------------------------------------------------------------------------
import subprocess, datetime


def _git(*args):
    try:
        return subprocess.check_output(["git", "-C", str(ROOT)] + list(args), text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


_build_no  = _git("rev-list", "--count", "HEAD") or "0"
_build_sha = _git("rev-parse", "--short", "HEAD") or "local"
_build_dt  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
(ROOT / "src/slic3r/GUI/UnifyBuildInfo.hpp").write_text(
    "#pragma once\n// Generated by unify/apply_unify.py at build time - do not edit.\n"
    f'#define UNIFY_BUILD_NUMBER "{_build_no}"\n'
    f'#define UNIFY_BUILD_STAMP "Build {_build_no} ({_build_dt}, {_build_sha})"\n', encoding="utf-8")
print(f"  * build stamp: Build {_build_no} ({_build_dt}, {_build_sha})")

edit("src/slic3r/GUI/GUI_App.cpp", '#include "GUI_App.hpp"\n', '#include "GUI_App.hpp"\n#include "UnifyBuildInfo.hpp"\n', '#include "UnifyBuildInfo.hpp"')
edit("src/slic3r/GUI/GUI_App.cpp",
     '            title    = "Snapmaker Orca";\n            version  = wxString::Format("V%s %s", Snapmaker_VERSION, _L("Release"));\n',
     '            title    = "Unify Slicer"; // Unify Slicer: splash title\n            version  = wxString::Format("Build %s", UNIFY_BUILD_NUMBER);\n',
     'Unify Slicer: splash title')
edit("src/slic3r/GUI/AboutDialog.cpp", '#include "AboutDialog.hpp"\n', '#include "AboutDialog.hpp"\n#include "UnifyBuildInfo.hpp"\n', '#include "UnifyBuildInfo.hpp"')
edit("src/slic3r/GUI/AboutDialog.cpp",
     '    auto version_string = _L("Snapmaker Orca ") + " " + std::string(Snapmaker_VERSION);\n',
     '    wxString version_string = wxString("Unify Slicer  ") + wxString(UNIFY_BUILD_STAMP); // Unify Slicer: build stamp\n',
     'Unify Slicer: build stamp')
edit("src/slic3r/GUI/AboutDialog.cpp",
     'wxString::Format("Based on Orca Slicer")',
     'wxString::Format("Based on Snapmaker Orca %s and Orca Slicer", Snapmaker_VERSION)',
     'Based on Snapmaker Orca %s and Orca Slicer')

# ---------------------------------------------------------------------------------------------
# Unify Slicer phase 2, #2: overhang speed by angle (10 or 5 degree table) + auto-fill
# ---------------------------------------------------------------------------------------------
_OH10 = [0, 0, 0, 45, 30, 15, 10, 10, 10]
_OH5  = [0, 0, 0, 0, 0, 0, 45, 45, 30, 30, 15, 15, 10, 10, 10, 10, 10, 10]
_OH_ROW_KEYS = [f"unify_ohs10_r{i}" for i in range(1, 10)] + [f"unify_ohs5_r{i}" for i in range(1, 19)]
_OH_KEYS = ["unify_overhang_angle_mode", "unify_overhang_autofill"] + _OH_ROW_KEYS
_OH_FIL_KEYS = ["unify_overhang_auto_start_angle", "unify_overhang_auto_max_speed", "unify_overhang_auto_min_speed"]

edit("src/libslic3r/PrintConfig.hpp",
     "    AlternateEveryN,\n    Count,\n};",
     "    AlternateEveryN,\n    Count,\n};\n\n"
     "// Unify Slicer: overhang speed by angle (issue #2)\nenum class UnifyOverhangMode\n{\n    Off,\n    Step10,\n    Step5,\n};",
     "enum class UnifyOverhangMode")
edit("src/libslic3r/PrintConfig.hpp",
     "    ((ConfigOptionBool,                wall_direction_holes))\n",
     "    ((ConfigOptionBool,                wall_direction_holes))\n"
     "    // Unify Slicer: overhang speed by angle (issue #2)\n"
     "    ((ConfigOptionEnum<UnifyOverhangMode>, unify_overhang_angle_mode))\n"
     "    ((ConfigOptionBool,                unify_overhang_autofill))\n"
     + "".join(f"    ((ConfigOptionFloat,               {k}))\n" for k in _OH_ROW_KEYS),
     "unify_overhang_angle_mode))")
edit("src/libslic3r/PrintConfig.hpp",
     "    ((ConfigOptionInts,               overhang_fan_speed))\n",
     "    ((ConfigOptionInts,               overhang_fan_speed))\n"
     "    // Unify Slicer: overhang speed auto-fill inputs (filament, issue #2)\n"
     + "".join(f"    ((ConfigOptionFloats,             {k}))\n" for k in _OH_FIL_KEYS),
     "unify_overhang_auto_start_angle))")
edit("src/libslic3r/PrintConfig.cpp",
     "CONFIG_OPTION_ENUM_DEFINE_STATIC_MAPS(WallDirection)\n",
     "CONFIG_OPTION_ENUM_DEFINE_STATIC_MAPS(WallDirection)\n\n"
     "// Unify Slicer: overhang speed by angle (issue #2)\n"
     "static t_config_enum_values s_keys_map_UnifyOverhangMode{\n"
     "    { \"off\",    int(UnifyOverhangMode::Off) },\n"
     "    { \"step10\", int(UnifyOverhangMode::Step10) },\n"
     "    { \"step5\",  int(UnifyOverhangMode::Step5) },\n"
     "};\n"
     "CONFIG_OPTION_ENUM_DEFINE_STATIC_MAPS(UnifyOverhangMode)\n",
     "s_keys_map_UnifyOverhangMode")

_oh_defs = r'''
    // Unify Slicer: overhang speed by angle (issue #2)
    def = this->add("unify_overhang_angle_mode", coEnum);
    def->label = L("Overhang speed by angle");
    def->category = L("Speed");
    def->tooltip = L("Off uses the overhang % speeds above. 10 or 5 degree steps use a speed table by overhang angle (0 = vertical wall, 90 = flat). Angles steeper than about 64 degrees at 0.20 mm layers print as bridges.");
    def->enum_keys_map = &ConfigOptionEnum<UnifyOverhangMode>::get_enum_values();
    def->enum_values.push_back("off");
    def->enum_values.push_back("step10");
    def->enum_values.push_back("step5");
    def->enum_labels.push_back(L("Off (overhang % speeds)"));
    def->enum_labels.push_back(L("10 degree steps"));
    def->enum_labels.push_back(L("5 degree steps"));
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionEnum<UnifyOverhangMode>(UnifyOverhangMode::Off));

    def = this->add("unify_overhang_autofill", coBool);
    def->label = L("Auto-fill overhang speeds");
    def->category = L("Speed");
    def->tooltip = L("Works out every row from the filament's auto-fill values (Filament > Cooling), the outer wall speed, layer height and line width, so the table is right for every file. Turn off to use the rows below; the button copies the auto values into the rows first.");
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionBool(true));
'''
for _step, _vals in ((10, _OH10), (5, _OH5)):
    for _i, _v in enumerate(_vals, start=1):
        _a0, _a1 = (_i - 1) * _step, _i * _step
        _oh_defs += (
            f'\n    def = this->add("unify_ohs{_step}_r{_i}", coFloat);\n'
            f'    def->label = "{_a0}-{_a1}\\u00B0";\n'
            f'    def->full_label = L("Overhang speed") + std::string(" {_a0}-{_a1}\\u00B0");\n'
            f'    def->category = L("Speed");\n'
            f'    def->tooltip = L("Speed for overhangs in this angle range. 0 = use the normal wall speed. Steeper rows are never printed faster than shallower ones.");\n'
            f'    def->sidetext = L("mm/s");\n'
            f'    def->min = 0;\n'
            f'    def->max = 1000;\n'
            f'    def->mode = comAdvanced;\n'
            f'    def->set_default_value(new ConfigOptionFloat({_v}));\n')
edit("src/libslic3r/PrintConfig.cpp",
     "    def->tooltip = L(\"Walls around holes follow the wall direction. When off they stay counter-clockwise.\");\n"
     "    def->mode = comAdvanced;\n    def->set_default_value(new ConfigOptionBool(true));\n",
     "    def->tooltip = L(\"Walls around holes follow the wall direction. When off they stay counter-clockwise.\");\n"
     "    def->mode = comAdvanced;\n    def->set_default_value(new ConfigOptionBool(true));\n" + _oh_defs,
     "this->add(\"unify_overhang_angle_mode\", coEnum)")
_oh_fil_defs = r'''    // Unify Slicer: overhang speed auto-fill inputs (filament, issue #2)
    def = this->add("unify_overhang_auto_start_angle", coFloats);
    def->label = L("Overhang auto-fill: slow down from");
    def->tooltip = L("Overhangs shallower than this angle (from vertical) print at normal wall speed. Min 10, max 60.");
    def->sidetext = L("° (10-60)");
    def->min = 10;
    def->max = 60;
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionFloats{ 30. });

    def = this->add("unify_overhang_auto_max_speed", coFloats);
    def->label = L("Overhang auto-fill: first slowed speed");
    def->tooltip = L("Speed of the first slowed-down overhang row. Never faster than the outer wall speed. Min 10, max 500.");
    def->sidetext = L("mm/s (10-500)");
    def->min = 10;
    def->max = 500;
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionFloats{ 60. });

    def = this->add("unify_overhang_auto_min_speed", coFloats);
    def->label = L("Overhang auto-fill: steepest speed");
    def->tooltip = L("Speed of the steepest overhang rows. Min 5, max 30.");
    def->sidetext = L("mm/s (5-30)");
    def->min = 5;
    def->max = 30;
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionFloats{ 10. });

'''
edit("src/libslic3r/PrintConfig.cpp",
     "    // Unify Slicer: Snapmaker U1 resonance fast check (issue #1)\n    def = this->add(\"unify_resonance_check\", coBool);\n",
     _oh_fil_defs + "    // Unify Slicer: Snapmaker U1 resonance fast check (issue #1)\n    def = this->add(\"unify_resonance_check\", coBool);\n",
     "this->add(\"unify_overhang_auto_start_angle\", coFloats)")
edit("src/libslic3r/Preset.cpp",
     "    \"wall_direction_alternate_layers\", \"wall_direction_start_cw\", \"wall_direction_outer\", \"wall_direction_inner\", \"wall_direction_holes\",",
     "    \"wall_direction_alternate_layers\", \"wall_direction_start_cw\", \"wall_direction_outer\", \"wall_direction_inner\", \"wall_direction_holes\",\n    "
     + ", ".join(f'"{k}"' for k in _OH_KEYS) + ",",
     '"unify_overhang_angle_mode", "unify_overhang_autofill"')
edit("src/libslic3r/Preset.cpp",
     "static std::vector<std::string> s_Preset_filament_options {\n",
     "static std::vector<std::string> s_Preset_filament_options {\n    " + ", ".join(f'"{k}"' for k in _OH_FIL_KEYS) + ", // Unify Slicer\n",
     '"unify_overhang_auto_start_angle", "unify_overhang_auto_max_speed"')
edit("src/libslic3r/PrintObject.cpp",
     "            || opt_key == \"overhang_1_4_speed\"\n",
     "            || opt_key == \"overhang_1_4_speed\"\n" + "".join(f"            || opt_key == \"{k}\"\n" for k in _OH_KEYS),
     "opt_key == \"unify_overhang_angle_mode\"")
edit("src/libslic3r/Print.cpp",
     "        \"overhang_fan_speed\",\n",
     "        \"overhang_fan_speed\",\n" + "".join(f"        \"{k}\",\n" for k in _OH_FIL_KEYS),
     "\"unify_overhang_auto_start_angle\",")
edit("src/libslic3r/GCode.cpp", '#include "PrintConfig.hpp"\n', '#include "PrintConfig.hpp"\n#include "UnifyOverhang.hpp"\n', '#include "UnifyOverhang.hpp"')
_GC_OH = r'''
        // Unify Slicer: overhang speed by angle (issue #2)
        if (m_config.unify_overhang_angle_mode.value != UnifyOverhangMode::Off) {
            const bool fine   = m_config.unify_overhang_angle_mode.value == UnifyOverhangMode::Step5;
            const int  rows_n = fine ? unify_overhang::ROWS_FINE : unify_overhang::ROWS_COARSE;
            std::vector<double> rows(rows_n, 0.);
            if (m_config.unify_overhang_autofill.value) {
                rows = unify_overhang::auto_rows(rows_n, EXTRUDER_CONFIG(unify_overhang_auto_start_angle), EXTRUDER_CONFIG(unify_overhang_auto_max_speed),
                                                 EXTRUDER_CONFIG(unify_overhang_auto_min_speed), ref_speed, path.height, path.width);
            } else {
                for (int i = 0; i < rows_n; ++i) {
                    const std::string key = std::string(fine ? "unify_ohs5_r" : "unify_ohs10_r") + std::to_string(i + 1);
                    if (const ConfigOptionFloat *opt = m_config.option<ConfigOptionFloat>(key))
                        rows[i] = opt->value;
                }
            }
            std::vector<double> unify_ov, unify_sp;
            unify_overhang::build_levels(rows, ref_speed, path.height, path.width, unify_ov, unify_sp);
            if (!unify_ov.empty()) {
                overhang_overlap_levels.values = unify_ov;
                dynamic_overhang_speeds.values.clear();
                for (double s : unify_sp)
                    dynamic_overhang_speeds.values.push_back(FloatOrPercent{ s, false });
            }
        }
'''
edit("src/libslic3r/GCode.cpp",
     "\n        new_points = m_extrusion_quality_estimator.estimate_extrusion_quality(path, overhang_overlap_levels, dynamic_overhang_speeds,",
     _GC_OH + "\n        new_points = m_extrusion_quality_estimator.estimate_extrusion_quality(path, overhang_overlap_levels, dynamic_overhang_speeds,",
     "Unify Slicer: overhang speed by angle (issue #2)")
_TAB_OH = r'''        // Unify Slicer: overhang speed by angle (issue #2), in its own groups so the copy button
        // (a full-width line, which an options group always puts last) sits right under Auto-fill (issue #8)
        auto unify_oh_og = page->new_optgroup(L("Overhang speed by angle"));
        unify_oh_og->append_single_option_line("unify_overhang_angle_mode");
        unify_oh_og->append_single_option_line("unify_overhang_autofill");
        {
            Line fill_line = { "", "" };
            fill_line.full_width = 1;
            fill_line.widget = [this](wxWindow* parent) {
                auto* btn = new wxButton(parent, wxID_ANY, _L("Copy auto-fill values into the table"));
                btn->SetToolTip(_L("Fills every row from the auto-fill formula and turns auto-fill off, so you can adjust single rows."));
                btn->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) {
                    DynamicPrintConfig new_conf = *m_config;
                    const DynamicPrintConfig& fil = wxGetApp().preset_bundle->filaments.get_edited_preset().config;
                    auto fval = [&fil](const char* key, double def) {
                        const ConfigOptionFloats* o = fil.option<ConfigOptionFloats>(key);
                        return (o != nullptr && !o->values.empty()) ? o->values.front() : def;
                    };
                    double ref = 0.;
                    if (const ConfigOptionFloats* o = m_config->option<ConfigOptionFloats>("outer_wall_speed"); o != nullptr && !o->values.empty())
                        ref = o->values.front();
                    double lh = 0.2;
                    if (const ConfigOptionFloat* o = m_config->option<ConfigOptionFloat>("layer_height"); o != nullptr && o->value > 0.)
                        lh = o->value;
                    double w = 0.42;
                    if (const ConfigOptionFloatOrPercent* o = m_config->option<ConfigOptionFloatOrPercent>("outer_wall_line_width"); o != nullptr && o->value > 0.)
                        w = o->percent ? o->value * 0.004 : o->value;
                    for (int n : { unify_overhang::ROWS_COARSE, unify_overhang::ROWS_FINE }) {
                        const std::vector<double> rows = unify_overhang::auto_rows(n, fval("unify_overhang_auto_start_angle", 30.),
                            fval("unify_overhang_auto_max_speed", 60.), fval("unify_overhang_auto_min_speed", 10.), ref, lh, w);
                        for (int i = 0; i < n; ++i)
                            new_conf.set_key_value(std::string(n == unify_overhang::ROWS_COARSE ? "unify_ohs10_r" : "unify_ohs5_r") + std::to_string(i + 1),
                                                   new ConfigOptionFloat(rows[i]));
                    }
                    new_conf.set_key_value("unify_overhang_autofill", new ConfigOptionBool(false));
                    load_config(new_conf);
                });
                auto* sizer = new wxBoxSizer(wxHORIZONTAL);
                sizer->Add(btn, 0, wxALL, 2);
                return sizer;
            };
            unify_oh_og->append_line(fill_line);
        }
        auto unify_oh_rows = page->new_optgroup(L("Overhang speed table"));
        for (int i = 1; i <= unify_overhang::ROWS_COARSE; ++i)
            unify_oh_rows->append_single_option_line("unify_ohs10_r" + std::to_string(i));
        for (int i = 1; i <= unify_overhang::ROWS_FINE; ++i)
            unify_oh_rows->append_single_option_line("unify_ohs5_r" + std::to_string(i));
'''
edit("src/slic3r/GUI/Tab.cpp", '#include "Tab.hpp"\n', '#include "Tab.hpp"\n#include "libslic3r/UnifyOverhang.hpp"\n#include <wx/button.h>\n', '#include "libslic3r/UnifyOverhang.hpp"')
edit("src/slic3r/GUI/Tab.cpp",
     "        line.append_option(optgroup->get_option(\"overhang_totally_speed\"));\n        optgroup->append_line(line);\n",
     "        line.append_option(optgroup->get_option(\"overhang_totally_speed\"));\n        optgroup->append_line(line);\n" + _TAB_OH,
     "append_single_option_line(\"unify_overhang_angle_mode\")")
edit("src/slic3r/GUI/Tab.cpp",
     "        optgroup->append_single_option_line(\"overhang_fan_speed\");\n",
     "        optgroup->append_single_option_line(\"overhang_fan_speed\");\n"
     "        // Unify Slicer: overhang speed auto-fill inputs (issue #2)\n"
     + "".join(f"        optgroup->append_single_option_line(\"{k}\");\n" for k in _OH_FIL_KEYS),
     "append_single_option_line(\"unify_overhang_auto_start_angle\")")
_CM_OH = r'''
    {   // Unify Slicer: overhang speed by angle (issue #2)
        const UnifyOverhangMode oh_mode  = config->opt_enum<UnifyOverhangMode>("unify_overhang_angle_mode");
        const bool              oh_on    = oh_mode != UnifyOverhangMode::Off;
        const bool              oh_auto  = config->opt_bool("unify_overhang_autofill");
        toggle_line("unify_overhang_autofill", oh_on);
        for (int i = 1; i <= 9; ++i) {
            const std::string k = "unify_ohs10_r" + std::to_string(i);
            toggle_line(k, oh_mode == UnifyOverhangMode::Step10);
            toggle_field(k, !oh_auto);
        }
        for (int i = 1; i <= 18; ++i) {
            const std::string k = "unify_ohs5_r" + std::to_string(i);
            toggle_line(k, oh_mode == UnifyOverhangMode::Step5);
            toggle_field(k, !oh_auto);
        }
        for (auto el : {"overhang_1_4_speed", "overhang_2_4_speed", "overhang_3_4_speed", "overhang_4_4_speed", "overhang_totally_speed"})
            toggle_field(el, !oh_on);
    }
'''
edit("src/slic3r/GUI/ConfigManipulation.cpp",
     "    toggle_field(\"wall_direction\", !has_spiral_vase);\n",
     "    toggle_field(\"wall_direction\", !has_spiral_vase);\n" + _CM_OH,
     "Unify Slicer: overhang speed by angle (issue #2)")

# ---------------------------------------------------------------------------------------------
# Unify Slicer phase 2, #1: resonance check results (console watcher + dialogs)
# ---------------------------------------------------------------------------------------------
edit("src/libslic3r/PrintConfig.hpp",
     "    ((ConfigOptionInt,                 unify_resonance_check_time))\n",
     "    ((ConfigOptionInt,                 unify_resonance_check_time))\n"
     "    ((ConfigOptionString,              unify_printer_host))\n"
     "    ((ConfigOptionBool,                unify_resonance_show_ok))\n"
     "    ((ConfigOptionBool,                unify_resonance_warn))\n",
     "unify_printer_host))")
_RES2_DEFS = r'''    // Unify Slicer: resonance check results (issue #1, phase 2)
    def = this->add("unify_printer_host", coString);
    def->label = L("Printer address (for check results)");
    def->tooltip = L("IP address or hostname of the printer - the same one you use for Mainsail or Fluidd, e.g. 192.168.1.50. Unify reads the printer console to show the resonance check results. Leave empty to turn result monitoring off.");
    def->mode = comSimple;
    def->set_default_value(new ConfigOptionString(""));

    def = this->add("unify_resonance_show_ok", coBool);
    def->label = L("Show resonance check result on every print");
    def->tooltip = L("Shows a short notice with the input shaping chosen for the print, closing by itself after 10 s.");
    def->mode = comSimple;
    def->set_default_value(new ConfigOptionBool(true));

    def = this->add("unify_resonance_warn", coBool);
    def->label = L("Warn if resonance looks abnormal");
    def->tooltip = L("Shows a warning with Pause, Cancel print and Continue when the result looks wrong. Continues by itself after 15 s. Only works while Unify Slicer is open and can reach the printer.");
    def->mode = comSimple;
    def->set_default_value(new ConfigOptionBool(true));

'''
edit("src/libslic3r/PrintConfig.cpp",
     "    def = this->add(\"unify_resonance_check_time\", coInt);\n",
     _RES2_DEFS + "    def = this->add(\"unify_resonance_check_time\", coInt);\n",
     "this->add(\"unify_printer_host\", coString)")
edit("src/libslic3r/Preset.cpp",
     "    \"unify_resonance_check\", \"unify_resonance_check_time\",\n",
     "    \"unify_resonance_check\", \"unify_resonance_check_time\", \"unify_printer_host\", \"unify_resonance_show_ok\", \"unify_resonance_warn\",\n",
     "\"unify_printer_host\", \"unify_resonance_show_ok\"")
edit("src/libslic3r/Print.cpp",
     "        \"unify_resonance_check_time\",\n",
     "        \"unify_resonance_check_time\",\n        \"unify_printer_host\",\n        \"unify_resonance_show_ok\",\n        \"unify_resonance_warn\",\n",
     "\"unify_resonance_warn\",")
edit("src/slic3r/GUI/Tab.cpp",
     "        optgroup->append_single_option_line(\"unify_resonance_check_time\");\n",
     "        optgroup->append_single_option_line(\"unify_resonance_check_time\");\n"
     "        optgroup->append_single_option_line(\"unify_printer_host\");\n"
     "        {   // Unify Slicer: Test connection (issue #1)\n"
     "            Line test_line = { \"\", \"\" };\n"
     "            test_line.full_width = 1; // widget-only lines must be full width (no option attached)\n"
     "            test_line.widget = [this](wxWindow* parent) {\n"
     "                auto* btn = new wxButton(parent, wxID_ANY, _L(\"Test connection\"));\n"
     "                btn->SetToolTip(_L(\"Checks that Unify can reach the printer at this address.\"));\n"
     "                btn->Bind(wxEVT_BUTTON, [this, btn](wxCommandEvent&) {\n"
     "                    unify_resonance_test_connection(m_config->opt_string(\"unify_printer_host\"), btn);\n"
     "                });\n"
     "                auto* sizer = new wxBoxSizer(wxHORIZONTAL);\n"
     "                sizer->Add(btn, 0, wxALL, 2);\n"
     "                return sizer;\n"
     "            };\n"
     "            optgroup->append_line(test_line);\n"
     "        }\n"
     "        optgroup->append_single_option_line(\"unify_resonance_show_ok\");\n"
     "        optgroup->append_single_option_line(\"unify_resonance_warn\");\n",
     "append_single_option_line(\"unify_printer_host\")")
edit("src/slic3r/GUI/Tab.cpp",
     "        toggle_line(\"unify_resonance_check_time\", m_config->opt_bool(\"unify_resonance_check\"));\n",
     "        toggle_line(\"unify_resonance_check_time\", m_config->opt_bool(\"unify_resonance_check\"));\n"
     "        // Unify Slicer: printer address and result options stay visible (watching works for any G-code)\n",
     "printer address and result options stay visible")
edit("src/slic3r/CMakeLists.txt", "    GUI/UnifyCalibration.cpp\n",
     "    GUI/UnifyCalibration.cpp\n    GUI/UnifyResonance.hpp\n    GUI/UnifyResonance.cpp\n    GUI/UnifyBuildInfo.hpp\n", "UnifyResonance.cpp")
edit("src/slic3r/GUI/MainFrame.cpp", '#include "UnifyCalibration.hpp"\n',
     '#include "UnifyCalibration.hpp"\n#include "UnifyResonance.hpp"\n', '#include "UnifyResonance.hpp"')
edit("src/slic3r/GUI/Tab.cpp", '#include "libslic3r/UnifyOverhang.hpp"\n',
     '#include "libslic3r/UnifyOverhang.hpp"\n#include "UnifyResonance.hpp"\n', '#include "UnifyResonance.hpp"')
edit("src/slic3r/GUI/MainFrame.cpp",
     "    // help\n    append_menu_item(m_topbar->GetCalibMenu(), wxID_ANY, _L(\"Tutorial\")",
     "    // Unify Slicer: resonance check log (top bar)\n"
     "    unify_resonance_monitor_start();\n"
     "    append_menu_item(m_topbar->GetCalibMenu(), wxID_ANY, _L(\"Resonance check log (Unify)\"), _L(\"Show recent resonance fast check results\"),\n"
     "        [](wxCommandEvent&) { unify_resonance_show_log(); }, \"\", nullptr,\n"
     "        []() { return true; }, this);\n\n"
     "    // help\n    append_menu_item(m_topbar->GetCalibMenu(), wxID_ANY, _L(\"Tutorial\")",
     "Unify Slicer: resonance check log (top bar)")
edit("src/slic3r/GUI/MainFrame.cpp",
     "    m_menubar->Append(calib_menu,wxString::Format(\"&%s\", _L(\"Calibration\")));\n",
     "    // Unify Slicer: resonance check log (menu bar)\n"
     "    unify_resonance_monitor_start();\n"
     "    append_menu_item(calib_menu, wxID_ANY, _L(\"Resonance check log (Unify)\"), _L(\"Show recent resonance fast check results\"),\n"
     "        [](wxCommandEvent&) { unify_resonance_show_log(); }, \"\", nullptr,\n"
     "        []() { return true; }, this);\n\n"
     "    m_menubar->Append(calib_menu,wxString::Format(\"&%s\", _L(\"Calibration\")));\n",
     "Unify Slicer: resonance check log (menu bar)")

# ---------------------------------------------------------------------------------------------
# Unify Slicer phase 3, #7: auto adaptive layer height for overhangs only
# ---------------------------------------------------------------------------------------------
_OL_KEYS = ["unify_overhang_layers", "unify_overhang_layers_min"]
edit("src/libslic3r/PrintConfig.hpp",
     "    ((ConfigOptionFloat,               layer_height))\n    ((ConfigOptionFloat,               mmu_segmented_region_max_width))\n",
     "    ((ConfigOptionFloat,               layer_height))\n"
     "    // Unify Slicer: thinner layers at overhangs (issue #7)\n"
     "    ((ConfigOptionBool,                unify_overhang_layers))\n"
     "    ((ConfigOptionFloat,               unify_overhang_layers_min))\n"
     "    ((ConfigOptionFloat,               mmu_segmented_region_max_width))\n",
     "unify_overhang_layers))")
edit("src/libslic3r/PrintConfig.cpp",
     "    def = this->add(\"printable_height\", coFloat);\n",
     r"""    // Unify Slicer: auto adaptive layer height for overhangs only (issue #7)
    def = this->add("unify_overhang_layers", coBool);
    def->label = L("Thinner layers at overhangs");
    def->category = L("Quality");
    def->tooltip = L("Automatically prints thinner layers where the model has overhangs (40 degrees from vertical and steeper), "
                     "down to the minimum below at about 70 degrees, and the normal layer height everywhere else. Flat ceilings and "
                     "bridges, and very small overhangs, are left alone. The height ramps in and out over a few layers. "
                     "Objects with a manually edited variable layer height or height range modifiers keep their own layers. "
                     "Not used with a prime tower and more than one object.");
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionBool(false));

    def = this->add("unify_overhang_layers_min", coFloat);
    def->label = L("Thinnest overhang layer");
    def->category = L("Quality");
    def->tooltip = L("Thinnest layer used at steep overhangs. The thickest is always the layer height above. "
                     "It never goes below a safe floor: the larger of the printer's Min layer height and 20% of the nozzle "
                     "diameter (0.08 mm on a 0.4 mm nozzle). Lower values are raised to that floor when slicing.");
    def->sidetext = "mm";
    def->min = 0.04;
    def->max = 1.;
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionFloat(0.12));

    def = this->add("printable_height", coFloat);
""",
     "this->add(\"unify_overhang_layers\", coBool)")
edit("src/libslic3r/Preset.cpp",
     "    \"layer_height\", \"initial_layer_print_height\", \"wall_loops\",",
     "    \"layer_height\", \"initial_layer_print_height\", \"unify_overhang_layers\", \"unify_overhang_layers_min\", \"wall_loops\",",
     "\"unify_overhang_layers\", \"unify_overhang_layers_min\"")
edit("src/libslic3r/PrintObject.cpp",
     "               opt_key == \"layer_height\"\n            || opt_key == \"dithering_z_step_size\"\n",
     "               opt_key == \"layer_height\"\n            || opt_key == \"unify_overhang_layers\"\n            || opt_key == \"unify_overhang_layers_min\"\n            || opt_key == \"dithering_z_step_size\"\n",
     "opt_key == \"unify_overhang_layers\"")
edit("src/libslic3r/PrintObject.cpp", '#include "Print.hpp"\n', '#include "Print.hpp"\n#include "UnifyOverhangLayers.hpp"\n', '#include "UnifyOverhangLayers.hpp"')
edit("src/libslic3r/PrintObject.cpp",
     "        layer_height_profile = layer_height_profile_from_ranges(slicing_parameters, *ranges_to_use);\n        // The layer height profile is already compressed.\n        updated = true;\n",
     "        layer_height_profile = layer_height_profile_from_ranges(slicing_parameters, *ranges_to_use);\n"
     + r"""        // Unify Slicer: thinner layers at overhangs (issue #7). Only when the object has no manual profile
        // (handled above) and no height range modifiers.
        if (!has_dithering_ranges && model_object.layer_config_ranges.empty() && print_object != nullptr &&
            print_object->config().unify_overhang_layers.value && print_object->print() != nullptr) {
            const Print &print = *print_object->print();
            if (!(print.has_wipe_tower() && print.objects().size() > 1)) {
                const PrintConfig &pc    = print.config();
                double             floor = unify_overhang_layers::FLOOR_ABS_MM;
                for (size_t i = 0; i < pc.nozzle_diameter.values.size(); ++i)
                    floor = std::max(floor, unify_overhang_layers::safe_floor(pc.min_layer_height.get_at(i), pc.nozzle_diameter.get_at(i)));
                const double hmax = slicing_parameters.layer_height;
                const double hmin = std::max({ print_object->config().unify_overhang_layers_min.value, floor, slicing_parameters.min_layer_height });
                std::vector<unify_overhang_layers::Mesh> meshes;
                for (const ModelVolume *v : model_object.volumes)
                    if (v->is_model_part())
                        meshes.push_back({ &v->mesh().its, print_object->trafo() * v->get_matrix() });
                std::vector<coordf_t> unify_profile = unify_overhang_layers::make_profile(slicing_parameters, meshes, hmin, hmax);
                if (!unify_profile.empty())
                    layer_height_profile = std::move(unify_profile);
            }
        }
        // The layer height profile is already compressed.
        updated = true;
""",
     "thinner layers at overhangs (issue #7). Only when")
edit("src/slic3r/GUI/Tab.cpp",
     "        optgroup->append_single_option_line(\"initial_layer_print_height\",\"quality_settings_layer_height\");\n",
     "        optgroup->append_single_option_line(\"initial_layer_print_height\",\"quality_settings_layer_height\");\n"
     "        // Unify Slicer: thinner layers at overhangs (issue #7)\n"
     "        optgroup->append_single_option_line(\"unify_overhang_layers\");\n"
     "        optgroup->append_single_option_line(\"unify_overhang_layers_min\");\n",
     "append_single_option_line(\"unify_overhang_layers\")")
edit("src/slic3r/GUI/ConfigManipulation.cpp",
     "    {   // Unify Slicer: overhang speed by angle (issue #2)\n",
     "    // Unify Slicer: thinner layers at overhangs (issue #7)\n"
     "    toggle_line(\"unify_overhang_layers_min\", config->opt_bool(\"unify_overhang_layers\"));\n"
     "    {   // Unify Slicer: overhang speed by angle (issue #2)\n",
     "toggle_line(\"unify_overhang_layers_min\"")


# Unify Slicer phase 3 bridge work lives in its own file (keeps this one stable).
_p3 = ROOT / "unify" / "apply_unify_phase3.py"
if _p3.exists():
    exec(compile(_p3.read_text(encoding="utf-8"), str(_p3), "exec"))

print("Done")
