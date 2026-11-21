# Unify Slicer: Overhang layer height - transition layers (Nov 21). Runs from apply_unify_phase3.py.
# Every change of layer height steps through in-between ("transition") layers.
#   - Auto (default): 3 transition layers, more when one step would change the height by more than 0.04 mm.
#   - Manual: the number the user sets (0 = jump straight to the new height, max 10).
# Either way the slicer checks it fits: when there isn't enough room before an overhang starts, it uses as many
# transition layers as fit (down to 0) so the overhang still starts at its thin layer height.

print("Applying Overhang layer height transition layers")
_H = "src/libslic3r/UnifyOverhangLayers.hpp"

edit(_H, "constexpr int    MIN_STEPS       = 2;    // at least this many in-between layers for every height change\n",
     "constexpr int    MIN_STEPS       = 3;    // Auto: at least this many in-between layers for every height change\n"
     "constexpr int    MAX_USER_STEPS  = 10;   // Manual: most transition layers a user can set\n",
     "MAX_USER_STEPS")

edit(_H,
     "inline std::vector<double> step_heights(double from, double to)\n{\n"
     "    const int n = std::max(MIN_STEPS, int(std::ceil(std::abs(to - from) / MAX_STEP_MM - 1e-9)) - 1);\n",
     "// Unify Slicer: `steps` in-between layers; `add_for_big_jumps` (Auto) adds more when one step would exceed MAX_STEP_MM.\n"
     "inline std::vector<double> step_heights(double from, double to, int steps = MIN_STEPS, bool add_for_big_jumps = true)\n{\n"
     "    const int extra = add_for_big_jumps ? int(std::ceil(std::abs(to - from) / MAX_STEP_MM - 1e-9)) - 1 : 0;\n"
     "    const int n     = std::max(std::clamp(steps, 0, MAX_USER_STEPS), extra);\n",
     "bool add_for_big_jumps = true)")

edit(_H,
     "inline std::vector<std::pair<double, double>> plan_layers(const std::vector<double> &bins, double start, double height, double hmin, double hmax)\n{\n",
     "inline std::vector<std::pair<double, double>> plan_layers(const std::vector<double> &bins, double start, double height, double hmin, double hmax,\n"
     "                                                          int steps = MIN_STEPS, bool manual_steps = false)\n{\n",
     "int steps = MIN_STEPS, bool manual_steps = false)")

# step down: use the chosen number of transition layers, or as many as fit before the overhang starts
edit(_H,
     "                const std::vector<double> steps = step_heights(h, target);\n"
     "                // start so the last in-between layer ends at or before z_r; if there's no room, start now\n"
     "                if (z + h > z_r - sum(steps) - 1e-9) {\n"
     "                    queue.assign(steps.begin(), steps.end());\n",
     "                std::vector<double> tsteps = step_heights(h, target, steps, !manual_steps);\n"
     "                // start so the last in-between layer ends at or before z_r; if there's no room, start now\n"
     "                if (z + h > z_r - sum(tsteps) - 1e-9) {\n"
     "                    // Unify Slicer: feasibility - fewer transition layers when they don't fit before the overhang\n"
     "                    while (!tsteps.empty() && z + sum(tsteps) > z_r + 1e-9)\n"
     "                        tsteps = step_heights(h, target, int(tsteps.size()) - 1, false);\n"
     "                    if (tsteps.empty())\n"
     "                        tsteps.push_back(target); // no room at all: go straight to the overhang height\n"
     "                    queue.assign(tsteps.begin(), tsteps.end());\n",
     "feasibility - fewer transition layers when they don't fit")

# step up after the overhang: same number of transition layers
edit(_H,
     "                    const double span = sum(step_heights(h, up)) + up;\n",
     "                    const double span = sum(step_heights(h, up, steps, !manual_steps)) + up;\n",
     "sum(step_heights(h, up, steps, !manual_steps))")
edit(_H,
     "                if (up > h + 1e-6) {\n"
     "                    const std::vector<double> steps = step_heights(h, up);\n"
     "                    queue.assign(steps.begin(), steps.end());\n",
     "                if (up > h + 1e-6) {\n"
     "                    std::vector<double> usteps = step_heights(h, up, steps, !manual_steps);\n"
     "                    if (usteps.empty())\n"
     "                        usteps.push_back(up); // 0 transition layers: straight back up\n"
     "                    queue.assign(usteps.begin(), usteps.end());\n",
     "0 transition layers: straight back up")

edit(_H,
     "inline std::vector<coordf_t> make_profile(const SlicingParameters &sp, const std::vector<Mesh> &meshes, double hmin, double hmax)\n",
     "inline std::vector<coordf_t> make_profile(const SlicingParameters &sp, const std::vector<Mesh> &meshes, double hmin, double hmax,\n"
     "                                          int steps = MIN_STEPS, bool manual_steps = false)\n",
     "const std::vector<Mesh> &meshes, double hmin, double hmax,\n")
edit(_H, "    for (const auto &[z, h] : plan_layers(bins, start, height, hmin, hmax)) {\n",
     "    for (const auto &[z, h] : plan_layers(bins, start, height, hmin, hmax, steps, manual_steps)) {\n",
     "plan_layers(bins, start, height, hmin, hmax, steps, manual_steps)")

# settings
edit("src/libslic3r/PrintConfig.hpp",
     "    ((ConfigOptionFloat,               unify_overhang_layers_min))\n",
     "    ((ConfigOptionFloat,               unify_overhang_layers_min))\n"
     "    ((ConfigOptionBool,                unify_overhang_layers_manual_steps))\n"
     "    ((ConfigOptionInt,                 unify_overhang_layers_steps))\n",
     "unify_overhang_layers_steps))")
edit("src/libslic3r/PrintConfig.cpp",
     "    def->set_default_value(new ConfigOptionFloat(0.12));\n\n    def = this->add(\"printable_height\", coFloat);\n",
     "    def->set_default_value(new ConfigOptionFloat(0.12));\n\n"
     r"""    // Unify Slicer: Overhang layer height - transition layers
    def = this->add("unify_overhang_layers_manual_steps", coBool);
    def->label = L("Set transition layers manually");
    def->category = L("Quality");
    def->tooltip = L("Transition layers are the in-between layers used every time the layer height changes. "
                     "Off (Auto): 3 transition layers, and more when one step would change the height by more than 0.04 mm. "
                     "On: use the number below. Either way, when there isn't enough room before an overhang starts, "
                     "Unify uses as many as fit (down to none) so the overhang still starts at its thin layer height.");
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionBool(false));

    def = this->add("unify_overhang_layers_steps", coInt);
    def->label = L("Transition layers");
    def->category = L("Quality");
    def->tooltip = L("Number of in-between layers for each change of layer height when set manually. "
                     "0 = jump straight to the new height. Min 0, max 10. Fewer are used where they don't fit.");
    def->sidetext = L("layers");
    def->min = 0;
    def->max = 10;
    def->mode = comAdvanced;
    def->set_default_value(new ConfigOptionInt(3));

    def = this->add("printable_height", coFloat);
""",
     "this->add(\"unify_overhang_layers_steps\", coInt)")
edit("src/libslic3r/PrintConfig.cpp",
     "bridges, and very small overhangs, are left alone. Every height change goes through at least two in-between \"\n"
     "                     \"layers, and the step down is finished before the overhang starts. \"",
     "bridges, and very small overhangs, are left alone. Every height change goes through transition layers \"\n"
     "                     \"(3 by default, see below), and the step down is finished before the overhang starts. \"",
     "goes through transition layers")
edit("src/libslic3r/Preset.cpp",
     "\"unify_overhang_layers_min\", \"wall_loops\",",
     "\"unify_overhang_layers_min\", \"unify_overhang_layers_manual_steps\", \"unify_overhang_layers_steps\", \"wall_loops\",",
     "\"unify_overhang_layers_steps\"")
edit("src/libslic3r/PrintObject.cpp",
     "            || opt_key == \"unify_overhang_layers_min\"\n",
     "            || opt_key == \"unify_overhang_layers_min\"\n"
     "            || opt_key == \"unify_overhang_layers_manual_steps\"\n"
     "            || opt_key == \"unify_overhang_layers_steps\"\n",
     "opt_key == \"unify_overhang_layers_steps\"")
edit("src/libslic3r/PrintObject.cpp",
     "                std::vector<coordf_t> unify_profile = unify_overhang_layers::make_profile(slicing_parameters, meshes, hmin, hmax);\n",
     "                const bool manual_steps = print_object->config().unify_overhang_layers_manual_steps.value;\n"
     "                const int  steps        = manual_steps ? print_object->config().unify_overhang_layers_steps.value\n"
     "                                                       : unify_overhang_layers::MIN_STEPS;\n"
     "                std::vector<coordf_t> unify_profile =\n"
     "                    unify_overhang_layers::make_profile(slicing_parameters, meshes, hmin, hmax, steps, manual_steps);\n",
     "make_profile(slicing_parameters, meshes, hmin, hmax, steps, manual_steps)")
edit("src/slic3r/GUI/Tab.cpp",
     "        optgroup->append_single_option_line(\"unify_overhang_layers_min\");\n",
     "        optgroup->append_single_option_line(\"unify_overhang_layers_min\");\n"
     "        optgroup->append_single_option_line(\"unify_overhang_layers_manual_steps\");\n"
     "        optgroup->append_single_option_line(\"unify_overhang_layers_steps\");\n",
     "append_single_option_line(\"unify_overhang_layers_steps\")")
edit("src/slic3r/GUI/ConfigManipulation.cpp",
     "    toggle_line(\"unify_overhang_layers_min\", config->opt_bool(\"unify_overhang_layers\") && config->opt_bool(\"unify_overhang_layers_manual_min\"));\n",
     "    toggle_line(\"unify_overhang_layers_min\", config->opt_bool(\"unify_overhang_layers\") && config->opt_bool(\"unify_overhang_layers_manual_min\"));\n"
     "    toggle_line(\"unify_overhang_layers_manual_steps\", config->opt_bool(\"unify_overhang_layers\"));\n"
     "    toggle_line(\"unify_overhang_layers_steps\", config->opt_bool(\"unify_overhang_layers\") && config->opt_bool(\"unify_overhang_layers_manual_steps\"));\n",
     "toggle_line(\"unify_overhang_layers_steps\"")
