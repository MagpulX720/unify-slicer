# Unify Slicer: Adaptive wall generator (issue #19), a third choice next to Classic and Arachne.
# Arachne core + Balanced bead rule (no hair-thin lines) + finer simplification + outer wall snapped to the exact
# Classic offset wherever it is at full width + thin single lines start at the joint.
# New files (in the repo): src/libslic3r/UnifyAdaptiveWalls.hpp, src/libslic3r/Arachne/BeadingStrategy/UnifyBalancedBeadingStrategy.hpp
# Runs from apply_unify_phase3.py (uses its edit() helper).

print("Applying Unify Adaptive wall generator (issue #19)")

# --- the option -------------------------------------------------------------------------------------------------
edit("src/libslic3r/PrintConfig.hpp",
     "    // \"A framework for adaptive width control of dense contour-parallel toolpaths in fused deposition modeling\" ported from Cura.\n    Arachne\n",
     "    // \"A framework for adaptive width control of dense contour-parallel toolpaths in fused deposition modeling\" ported from Cura.\n    Arachne,\n"
     "    // Unify Slicer: Arachne walls with Classic's exact outer surface (issue #19)\n    Adaptive\n",
     "Unify Slicer: Arachne walls with Classic's exact outer surface (issue #19)")
edit("src/libslic3r/PrintConfig.cpp",
     "    { \"arachne\", int(PerimeterGeneratorType::Arachne) }\n",
     "    { \"arachne\", int(PerimeterGeneratorType::Arachne) },\n    { \"adaptive\", int(PerimeterGeneratorType::Adaptive) } // Unify Slicer (issue #19)\n",
     "{ \"adaptive\", int(PerimeterGeneratorType::Adaptive) }")
edit("src/libslic3r/PrintConfig.cpp",
     "        \"Arachne engine produces walls with variable extrusion width.\");\n",
     "        \"Arachne engine produces walls with variable extrusion width. \"\n"
     "        \"Adaptive (Unify) uses Arachne for thin features but keeps Classic's exact outer wall wherever it is at full width, \"\n"
     "        \"never prints hair-thin lines, and starts thin single-line features at the joint instead of the tip.\");\n",
     "Adaptive (Unify) uses Arachne for thin features")
edit("src/libslic3r/PrintConfig.cpp",
     "    def->enum_labels.push_back(L(\"Arachne\"));\n",
     "    def->enum_labels.push_back(L(\"Arachne\"));\n"
     "    def->enum_values.push_back(\"adaptive\"); // Unify Slicer (issue #19)\n"
     "    def->enum_labels.push_back(L(\"Adaptive\"));\n",
     "def->enum_values.push_back(\"adaptive\");")

# Adaptive runs the Arachne path; Arachne-only settings and checks apply to it too
edit("src/libslic3r/LayerRegion.cpp",
     "    if (this->layer()->object()->config().wall_generator.value == PerimeterGeneratorType::Arachne && !spiral_mode)\n",
     "    if (this->layer()->object()->config().wall_generator.value != PerimeterGeneratorType::Classic && !spiral_mode) // Unify: Arachne or Adaptive\n",
     "PerimeterGeneratorType::Classic && !spiral_mode) // Unify: Arachne or Adaptive")
edit("src/slic3r/GUI/ConfigManipulation.cpp",
     "    bool have_arachne = config->opt_enum<PerimeterGeneratorType>(\"wall_generator\") == PerimeterGeneratorType::Arachne;\n"
     "    if (config->opt_enum<FuzzySkinMode>(\"fuzzy_skin_mode\")",
     "    bool have_arachne = config->opt_enum<PerimeterGeneratorType>(\"wall_generator\") != PerimeterGeneratorType::Classic; // Unify: Arachne or Adaptive\n"
     "    if (config->opt_enum<FuzzySkinMode>(\"fuzzy_skin_mode\")",
     "!= PerimeterGeneratorType::Classic; // Unify: Arachne or Adaptive\n    if (config->opt_enum<FuzzySkinMode>")
edit("src/slic3r/GUI/ConfigManipulation.cpp",
     "    bool have_arachne = config->opt_enum<PerimeterGeneratorType>(\"wall_generator\") == PerimeterGeneratorType::Arachne;\n"
     "    for (auto el : { \"wall_transition_length\"",
     "    bool have_arachne = config->opt_enum<PerimeterGeneratorType>(\"wall_generator\") != PerimeterGeneratorType::Classic; // Unify: Arachne or Adaptive\n"
     "    for (auto el : { \"wall_transition_length\"",
     "!= PerimeterGeneratorType::Classic; // Unify: Arachne or Adaptive\n    for (auto el : {")

# --- Arachne parameters: Balanced bead rule and finer simplification for Adaptive ---------------------------------
edit("src/libslic3r/Arachne/WallToolPaths.hpp",
     "    bool    is_top_or_bottom_layer;\n};\n",
     "    bool    is_top_or_bottom_layer;\n    bool    unify_adaptive = false; // Unify Slicer: Adaptive wall generator (issue #19)\n};\n",
     "bool    unify_adaptive = false;")
edit("src/libslic3r/Arachne/WallToolPaths.cpp",
     "        input_params.wall_distribution_count = print_object_config.wall_distribution_count.value;\n",
     "        input_params.wall_distribution_count = print_object_config.wall_distribution_count.value;\n"
     "        input_params.unify_adaptive = print_object_config.wall_generator.value == PerimeterGeneratorType::Adaptive; // Unify (issue #19)\n",
     "input_params.unify_adaptive = print_object_config.wall_generator.value")
edit("src/libslic3r/Arachne/WallToolPaths.cpp",
     "    const coord_t smallest_segment = Slic3r::Arachne::meshfix_maximum_resolution();\n"
     "    const coord_t allowed_distance = Slic3r::Arachne::meshfix_maximum_deviation();\n",
     "    // Unify Slicer: Adaptive keeps more of the outline's detail (0.1 mm / 0.005 mm instead of 0.5 mm / 0.025 mm)\n"
     "    const coord_t smallest_segment = m_params.unify_adaptive ? scaled<coord_t>(0.1) : Slic3r::Arachne::meshfix_maximum_resolution();\n"
     "    const coord_t allowed_distance = m_params.unify_adaptive ? scaled<coord_t>(0.005) : Slic3r::Arachne::meshfix_maximum_deviation();\n"
     "    s_unify_fine_simplify = m_params.unify_adaptive; // read by the static simplifyToolPaths()\n",
     "Unify Slicer: Adaptive keeps more of the outline's detail")
edit("src/libslic3r/Arachne/WallToolPaths.cpp",
     "const std::vector<VariableWidthLines> &WallToolPaths::generate()\n",
     "// Unify Slicer: set by generate() for the static simplifyToolPaths() that it calls on the same thread (issue #19)\n"
     "static thread_local bool s_unify_fine_simplify = false;\n\n"
     "const std::vector<VariableWidthLines> &WallToolPaths::generate()\n",
     "static thread_local bool s_unify_fine_simplify = false;")
edit("src/libslic3r/Arachne/WallToolPaths.cpp",
     "        const int64_t maximum_resolution = Slic3r::Arachne::meshfix_maximum_resolution();\n"
     "        const int64_t maximum_deviation = Slic3r::Arachne::meshfix_maximum_deviation();\n",
     "        const int64_t maximum_resolution = s_unify_fine_simplify ? scaled<coord_t>(0.1) : Slic3r::Arachne::meshfix_maximum_resolution(); // Unify (issue #19)\n"
     "        const int64_t maximum_deviation = s_unify_fine_simplify ? scaled<coord_t>(0.005) : Slic3r::Arachne::meshfix_maximum_deviation();\n",
     "scaled<coord_t>(0.1) : Slic3r::Arachne::meshfix_maximum_resolution(); // Unify (issue #19)")
edit("src/libslic3r/Arachne/WallToolPaths.cpp",
     "            wall_0_inset,\n            wall_distribution_count\n        );\n",
     "            wall_0_inset,\n            wall_distribution_count,\n            0.5,\n            m_params.unify_adaptive // Unify Slicer: Balanced bead rule (issue #19)\n        );\n",
     "m_params.unify_adaptive // Unify Slicer: Balanced bead rule (issue #19)")
edit("src/libslic3r/Arachne/BeadingStrategy/BeadingStrategyFactory.hpp",
     "        double minimum_variable_line_width = 0.5\n    );\n",
     "        double minimum_variable_line_width = 0.5,\n        bool unify_balanced = false // Unify Slicer (issue #19)\n    );\n",
     "bool unify_balanced = false // Unify Slicer (issue #19)")
edit("src/libslic3r/Arachne/BeadingStrategy/BeadingStrategyFactory.cpp",
     "                                                        const double  minimum_variable_line_ratio)\n",
     "                                                        const double  minimum_variable_line_ratio,\n"
     "                                                        const bool    unify_balanced)\n",
     "const bool    unify_balanced)")
edit("src/libslic3r/Arachne/BeadingStrategy/BeadingStrategyFactory.cpp",
     "#include \"OuterWallInsetBeadingStrategy.hpp\"\n",
     "#include \"OuterWallInsetBeadingStrategy.hpp\"\n#include \"UnifyBalancedBeadingStrategy.hpp\"\n",
     "#include \"UnifyBalancedBeadingStrategy.hpp\"")
edit("src/libslic3r/Arachne/BeadingStrategy/BeadingStrategyFactory.cpp",
     "    ret = std::make_unique<RedistributeBeadingStrategy>(preferred_bead_width_outer, minimum_variable_line_ratio, std::move(ret));\n",
     "    if (unify_balanced) // Unify Slicer: Balanced bead rule, no hair-thin lines (issue #19)\n"
     "        ret = std::make_unique<UnifyBalancedBeadingStrategy>(preferred_bead_width_outer, preferred_bead_width_inner, 0.6,\n"
     "                                                             wall_split_middle_threshold, minimum_variable_line_ratio, std::move(ret));\n"
     "    else\n"
     "        ret = std::make_unique<RedistributeBeadingStrategy>(preferred_bead_width_outer, minimum_variable_line_ratio, std::move(ret));\n",
     "Unify Slicer: Balanced bead rule, no hair-thin lines")

# --- outer wall snap + anchored starts ------------------------------------------------------------------------
edit("src/libslic3r/PerimeterGenerator.cpp",
     "#include \"PerimeterGenerator.hpp\"\n",
     "#include \"PerimeterGenerator.hpp\"\n#include \"UnifyAdaptiveWalls.hpp\"\n",
     "#include \"UnifyAdaptiveWalls.hpp\"")
edit("src/libslic3r/PerimeterGenerator.cpp",
     "        std::vector<Arachne::VariableWidthLines>   perimeters = wallToolPaths.getToolPaths();\n",
     "        std::vector<Arachne::VariableWidthLines>   perimeters = wallToolPaths.getToolPaths();\n"
     "        // Unify Slicer: Adaptive wall generator - exact Classic outer surface, thin lines start at the joint (issue #19)\n"
     "        if (object_config->wall_generator.value == PerimeterGeneratorType::Adaptive) {\n"
     "            UnifyAdaptive::snap_outer_to_classic(perimeters, to_polygons(offset_ex(last, -float(bead_width_0 / 2 + wall_0_inset))), bead_width_0);\n"
     "            UnifyAdaptive::anchor_open_lines(perimeters);\n"
     "        }\n",
     "UnifyAdaptive::snap_outer_to_classic(perimeters")
edit("src/libslic3r/PerimeterGenerator.cpp",
     "                if (!extrusion->is_closed) {\n                    // Especially for open extrusion,",
     "                // Unify Slicer: Adaptive already chose the start of open lines (at the joint), keep it\n"
     "                if (!extrusion->is_closed && perimeter_generator.object_config->wall_generator.value != PerimeterGeneratorType::Adaptive) {\n"
     "                    // Especially for open extrusion,",
     "Adaptive already chose the start of open lines")
edit("src/libslic3r/PerimeterGenerator.cpp",
     "                extrusion_coll.append(ExtrusionMultiPath(std::move(multi_path)));\n            }\n        }\n    }\n\n    return extrusion_coll;\n",
     "                if (perimeter_generator.object_config->wall_generator.value == PerimeterGeneratorType::Adaptive)\n"
     "                    multi_path.set_reverse(); // Unify Slicer: keep the joint-first direction (issue #19)\n"
     "                extrusion_coll.append(ExtrusionMultiPath(std::move(multi_path)));\n            }\n        }\n    }\n\n    return extrusion_coll;\n",
     "keep the joint-first direction (issue #19)")
