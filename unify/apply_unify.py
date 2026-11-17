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

print("Done")
