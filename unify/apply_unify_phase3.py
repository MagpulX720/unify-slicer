# Unify Slicer phase 3, issue #3: smarter bridge direction, Bridge check window, long / unanchored bridge warning.
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

# --- PrintObject keeps a copy of the bridge report for the Preview window ---
edit("src/libslic3r/Print.hpp", '#include "Slicing.hpp"\n', '#include "Slicing.hpp"\n#include "UnifyBridgeInfo.hpp"\n', '#include "UnifyBridgeInfo.hpp"')
edit("src/libslic3r/Print.hpp",
     "    const SlicingParameters&    slicing_parameters() const { return m_slicing_params; }\n",
     "    const SlicingParameters&    slicing_parameters() const { return m_slicing_params; }\n"
     "    // Unify Slicer: external bridge areas of all layers, filled after process_external_surfaces() (issue #3)\n"
     "    UnifyBridgeInfos            unify_bridge_report;\n",
     "UnifyBridgeInfos            unify_bridge_report;")

# --- per layer region: what was decided for each bridge area ---
edit("src/libslic3r/Layer.hpp", '#include "SurfaceCollection.hpp"\n',
     '#include "SurfaceCollection.hpp"\n#include "UnifyBridgeInfo.hpp"\n', '#include "UnifyBridgeInfo.hpp"')
edit("src/libslic3r/Layer.hpp",
     "    Polylines          \t\t\tunsupported_bridge_edges;\n",
     "    Polylines          \t\t\tunsupported_bridge_edges;\n"
     "    // Unify Slicer: external bridge areas of this region with direction / span / anchoring (issue #3)\n"
     "    UnifyBridgeInfos            unify_bridges;\n",
     "UnifyBridgeInfos            unify_bridges;")

# --- smarter direction + report in the active process_external_surfaces() ---
edit("src/libslic3r/LayerRegion.cpp", '#include "SVG.hpp"\n', '#include "SVG.hpp"\n#include "UnifyBridge.hpp"\n', '#include "UnifyBridge.hpp"')
edit("src/libslic3r/LayerRegion.cpp",
     "    const double infill_density = this->region().config().sparse_infill_density.value;\n",
     "    const double infill_density = this->region().config().sparse_infill_density.value;\n"
     "    this->unify_bridges.clear(); // Unify Slicer (issue #3)\n",
     "this->unify_bridges.clear();")
edit("src/libslic3r/LayerRegion.cpp",
     """                else {
                    auto [bridging_dir, unsupported_dist] = detect_bridging_direction(to_polygons(initial), to_polygons(lower_layer->lslices));
                    bridges[idx_last].bridge_angle = PI + std::atan2(bridging_dir.y(), bridging_dir.x());
                }
""",
     """                else {
                    auto [bridging_dir, unsupported_dist] = detect_bridging_direction(to_polygons(initial), to_polygons(lower_layer->lslices));
                    bridges[idx_last].bridge_angle = PI + std::atan2(bridging_dir.y(), bridging_dir.x());
                }
                if (lower_layer != nullptr) {
                    // Unify Slicer: smarter auto direction per bridge area + bridge report (issue #3)
                    unify_bridge::Finder finder(initial, lower_layer->lslices, this->bridging_flow(frInfill, object_config.thick_bridges).scaled_spacing());
                    if (finder.usable()) {
                        unify_bridge::Eval ev;
                        if (custom_angle > 0.0)
                            ev = finder.evaluate(custom_angle);
                        else if (this->region().config().unify_bridge_smart_direction.value) {
                            ev = finder.best(bridges[idx_last].bridge_angle);
                            if (ev.valid)
                                bridges[idx_last].bridge_angle = ev.angle;
                        } else
                            ev = finder.evaluate(bridges[idx_last].bridge_angle);
                        if (ev.valid)
                            this->unify_bridges.push_back(unify_bridge::make_info(initial, this->layer()->print_z, ev, custom_angle > 0.0));
                    }
                }
""",
     "Unify Slicer: smarter auto direction per bridge area")

# --- warning after the bridges of all layers are known ---
edit("src/libslic3r/PrintObject.cpp",
     """        BOOST_LOG_TRIVIAL(debug) << "Processing external surfaces for region " << region_id << " in parallel - end";
    }
}
""",
     """        BOOST_LOG_TRIVIAL(debug) << "Processing external surfaces for region " << region_id << " in parallel - end";
    }

    // Unify Slicer: copy of all bridge areas for the Preview "Bridge check" window (issue #3)
    this->unify_bridge_report.clear();
    for (const Layer *layer : m_layers)
        for (const LayerRegion *layerm : layer->regions())
            this->unify_bridge_report.insert(this->unify_bridge_report.end(), layerm->unify_bridges.begin(), layerm->unify_bridges.end());
    BOOST_LOG_TRIVIAL(info) << "Unify bridge report: " << this->model_object()->name << " bridges=" << this->unify_bridge_report.size();

    // Unify Slicer: long / unanchored bridge warning (issue #3). Not shown with supports on (they may hold the bridge).
    if (!this->has_support_material()) {
        size_t n_flagged = 0;
        double first_z   = -1.;
        for (const Layer *layer : m_layers)
            for (const LayerRegion *layerm : layer->regions())
                for (const UnifyBridgeInfo &b : layerm->unify_bridges)
                    if (b.flagged && b.area_mm2 >= 5.) {
                        if (n_flagged == 0)
                            first_z = b.print_z;
                        ++n_flagged;
                    }
        if (n_flagged > 0) {
            std::string msg = Slic3r::format(L("%1%: %2% bridge areas are longer than %3% mm or not anchored at both ends (first at Z %4% mm). "
                                               "Open the Preview: the Bridge check window lists them (or use Calibration > Bridge check (Unify))."),
                                             this->model_object()->name, n_flagged, int(unify_bridge::WARN_SPAN_MM), Slic3r::float_to_string_decimal_point(first_z, 2));
            this->active_step_add_warning(PrintStateBase::WarningLevel::NON_CRITICAL, msg);
        }
    }
}
""",
     "Unify Slicer: long / unanchored bridge warning (issue #3)")
edit("src/libslic3r/PrintObject.cpp", '#include "UnifyOverhangLayers.hpp"\n',
     '#include "UnifyOverhangLayers.hpp"\n#include "UnifyBridge.hpp"\n', '#include "UnifyBridge.hpp"')

# --- Preview: Bridge check window ---
edit("src/slic3r/CMakeLists.txt", "    GUI/UnifyCalibration.cpp\n",
     "    GUI/UnifyCalibration.cpp\n    GUI/UnifyBridgeCheck.hpp\n    GUI/UnifyBridgeCheck.cpp\n", "UnifyBridgeCheck.cpp")
edit("src/slic3r/GUI/GLCanvas3D.cpp", '#include "GLCanvas3D.hpp"\n',
     '#include "GLCanvas3D.hpp"\n#include "UnifyBridgeCheck.hpp"\n', '#include "UnifyBridgeCheck.hpp"')
edit("src/slic3r/GUI/GLCanvas3D.cpp",
     "    m_gcode_viewer.render(canvas_width, canvas_height, SLIDER_RIGHT_MARGIN * GCODE_VIEWER_SLIDER_SCALE);\n",
     "    m_gcode_viewer.render(canvas_width, canvas_height, SLIDER_RIGHT_MARGIN * GCODE_VIEWER_SLIDER_SCALE);\n"
     "    // Unify Slicer: Bridge check window (issue #3)\n"
     "    unify_bridge_check_render(m_gcode_viewer.get_layers_slider(), m_gcode_viewer.get_layers_zs());\n",
     "unify_bridge_check_render(")

# --- Calibration > Bridge check (Unify): reopen the window and switch to Preview ---
edit("src/slic3r/GUI/MainFrame.cpp", '#include "UnifyResonance.hpp"\n',
     '#include "UnifyResonance.hpp"\n#include "UnifyBridgeCheck.hpp"\n', '#include "UnifyBridgeCheck.hpp"')
edit("src/slic3r/GUI/MainFrame.cpp",
     "    // Unify Slicer: resonance check log (top bar)\n",
     "    // Unify Slicer: bridge check (top bar)\n"
     "    append_menu_item(m_topbar->GetCalibMenu(), wxID_ANY, _L(\"Bridge check (Unify)\"), _L(\"Show the bridge list in the Preview\"),\n"
     "        [this](wxCommandEvent&) { unify_bridge_check_show(); select_tab(size_t(tpPreview)); }, \"\", nullptr,\n"
     "        []() { return true; }, this);\n"
     "    // Unify Slicer: resonance check log (top bar)\n",
     "Unify Slicer: bridge check (top bar)")
edit("src/slic3r/GUI/MainFrame.cpp",
     "    // Unify Slicer: resonance check log (menu bar)\n",
     "    // Unify Slicer: bridge check (menu bar)\n"
     "    append_menu_item(calib_menu, wxID_ANY, _L(\"Bridge check (Unify)\"), _L(\"Show the bridge list in the Preview\"),\n"
     "        [this](wxCommandEvent&) { unify_bridge_check_show(); select_tab(size_t(tpPreview)); }, \"\", nullptr,\n"
     "        []() { return true; }, this);\n"
     "    // Unify Slicer: resonance check log (menu bar)\n",
     "Unify Slicer: bridge check (menu bar)")
