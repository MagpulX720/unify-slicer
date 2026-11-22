# Unify Slicer: Overhang speed by angle removed (Nov 22, owner's call: overkill). Runs from apply_unify_phase3.py.
# The settings page groups, the filament auto-fill inputs and the slicing step come out; overhang speeds go back to
# Orca's own overhang % speeds. The setting keys stay defined (hidden) so presets and 3MFs that hold them still load.
import re

print("Removing Overhang speed by angle")
_t = ROOT / "src/slic3r/GUI/Tab.cpp"
_s = _t.read_text(encoding="utf-8")
_a = _s.find("        // Unify Slicer: overhang speed by angle (issue #2), in its own groups")
_end_marker = "            unify_oh_rows->append_single_option_line(\"unify_ohs10_r\" + std::to_string(i));\n"
_b = _s.find(_end_marker)
if _a != -1 and _b != -1:
    _s = _s[:_a] + _s[_b + len(_end_marker):]
    print("  - src/slic3r/GUI/Tab.cpp (process page)")
elif "unify_oh_og" in _s:
    sys.exit("ERROR: could not remove the Overhang speed by angle groups from Tab.cpp")
_old = ("        // Unify Slicer: overhang speed auto-fill inputs (issue #2)\n"
        "        optgroup->append_single_option_line(\"unify_overhang_auto_start_angle\");\n"
        "        optgroup->append_single_option_line(\"unify_overhang_auto_max_speed\");\n"
        "        optgroup->append_single_option_line(\"unify_overhang_auto_min_speed\");\n")
if _old in _s:
    _s = _s.replace(_old, "", 1)
    print("  - src/slic3r/GUI/Tab.cpp (filament page)")
_t.write_text(_s, encoding="utf-8")

edit("src/slic3r/GUI/ConfigManipulation.cpp",
     "        const UnifyOverhangMode oh_mode  = config->opt_enum<UnifyOverhangMode>(\"unify_overhang_angle_mode\");\n"
     "        const bool              oh_on    = oh_mode != UnifyOverhangMode::Off;\n"
     "        const bool              oh_auto  = config->opt_bool(\"unify_overhang_autofill\");\n"
     "        toggle_line(\"unify_overhang_autofill\", oh_on);\n"
     "        for (int i = 1; i <= 9; ++i) {\n"
     "            const std::string k = \"unify_ohs10_r\" + std::to_string(i);\n"
     "            toggle_line(k, oh_mode == UnifyOverhangMode::Step10);\n"
     "            toggle_field(k, !oh_auto);\n"
     "        }\n",
     "        // Unify Slicer: Overhang speed by angle removed (Nov 22)\n",
     "Overhang speed by angle removed (Nov 22)")
edit("src/slic3r/GUI/ConfigManipulation.cpp",
     "        for (auto el : {\"overhang_1_4_speed\", \"overhang_2_4_speed\", \"overhang_3_4_speed\", \"overhang_4_4_speed\", \"overhang_totally_speed\"})\n"
     "            toggle_field(el, !oh_on);\n",
     "        // Orca's overhang % speeds stay editable\n",
     "Orca's overhang % speeds stay editable")
edit("src/libslic3r/GCode.cpp",
     "        if (m_config.unify_overhang_angle_mode.value != UnifyOverhangMode::Off) {\n",
     "        if (false) { // Unify Slicer: Overhang speed by angle removed (Nov 22) - Orca's overhang % speeds are used\n",
     "Overhang speed by angle removed (Nov 22) - Orca")
