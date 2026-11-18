# Unify Slicer phase 3, issue #3: smarter automatic bridge direction.
# (The long / unanchored bridge warning and the Preview "Bridge check" window were removed - back to Orca's default.)
# Run from apply_unify.py (uses its edit() helper); idempotent like the rest.

# --- option: smarter auto direction (region, default on) ---
edit("src/libslic3r/PrintConfig.hpp",
     "    ((ConfigOptionFloat,                bridge_angle))\n",
     "    ((ConfigOptionFloat,                bridge_angle))\n"
     "    // Unify Slicer: smarter automatic bridge direction (issue #3)\n"
     "    ((ConfigOptionBool,                 unify_bridge_smart_direction))\n",
     "unify_bridge_smart_direction))")
edit("src/libslic3r/PrintConfig.cpp",
     "    def = this->add(\"bridge_density\", coPercent);\n",
     r"""    // Unify Slicer: smarter automatic bridge direction (issue #3)
    def = this->add("unify_bridge_smart_direction", coBool);
    def->label = L("Smarter bridge direction");
    def->category = L("Strength");
    def->tooltip = L("When the bridge direction is automatic (0), Unify tries every 5 degrees for each bridge area and picks the "
                     "direction where every bridge line rests on solid material at both ends with the shortest span. "
                     "Turn off to use Orca's own automatic direction.");
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionBool(true));

    def = this->add("bridge_density", coPercent);
""",
     "this->add(\"unify_bridge_smart_direction\", coBool)")
edit("src/libslic3r/Preset.cpp",
     "\"bridge_angle\",\"internal_bridge_angle\",",
     "\"bridge_angle\",\"internal_bridge_angle\",\"unify_bridge_smart_direction\",",
     "\"unify_bridge_smart_direction\"")
edit("src/libslic3r/PrintObject.cpp",
     "            || opt_key == \"bridge_angle\"\n",
     "            || opt_key == \"bridge_angle\"\n            || opt_key == \"unify_bridge_smart_direction\"\n",
     "opt_key == \"unify_bridge_smart_direction\"")
edit("src/slic3r/GUI/Tab.cpp",
     "        optgroup->append_single_option_line(\"bridge_angle\", \"strength_settings_advanced#bridge-infill-direction\");\n",
     "        optgroup->append_single_option_line(\"bridge_angle\", \"strength_settings_advanced#bridge-infill-direction\");\n"
     "        optgroup->append_single_option_line(\"unify_bridge_smart_direction\"); // Unify Slicer (issue #3)\n",
     "append_single_option_line(\"unify_bridge_smart_direction\")")

# --- smarter direction in the active process_external_surfaces() ---
edit("src/libslic3r/LayerRegion.cpp", '#include "SVG.hpp"\n', '#include "SVG.hpp"\n#include "UnifyBridge.hpp"\n', '#include "UnifyBridge.hpp"')
edit("src/libslic3r/LayerRegion.cpp",
     """                else {
                    auto [bridging_dir, unsupported_dist] = detect_bridging_direction(to_polygons(initial), to_polygons(lower_layer->lslices));
                    bridges[idx_last].bridge_angle = PI + std::atan2(bridging_dir.y(), bridging_dir.x());
                }
""",
     """                else {
                    auto [bridging_dir, unsupported_dist] = detect_bridging_direction(to_polygons(initial), to_polygons(lower_layer->lslices));
                    bridges[idx_last].bridge_angle = PI + std::atan2(bridging_dir.y(), bridging_dir.x());
                    // Unify Slicer: smarter auto direction per bridge area (issue #3)
                    if (lower_layer != nullptr && this->region().config().unify_bridge_smart_direction.value) {
                        unify_bridge::Finder finder(initial, lower_layer->lslices, this->bridging_flow(frInfill, object_config.thick_bridges).scaled_spacing());
                        if (const unify_bridge::Eval ev = finder.best(bridges[idx_last].bridge_angle); ev.valid)
                            bridges[idx_last].bridge_angle = ev.angle;
                    }
                }
""",
     "Unify Slicer: smarter auto direction per bridge area")
