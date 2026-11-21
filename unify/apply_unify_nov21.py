# Unify Slicer: Nov 21 changes (issue #12). Runs from apply_unify_phase3.py, before the settings box check.
#   - Cooling slowdown logic (Filament > Cooling): shown in Advanced mode, Consistent surface by default.
#     Snapmaker Orca 2.4.2 already ships PrusaSlicer 2.9.3's logic, but hidden in Developer mode and set to Uniform.
#   - Perimeter transition distance (Consistent surface only): shown in Advanced mode.
#   - Short travel acceleration (Process > Speed > Acceleration, 250 mm/s2, already on): shown in Advanced mode.

print("Applying Unify Slicer Nov 21 changes (Consistent surface, short travel acceleration)")
edit("src/libslic3r/PrintConfig.cpp",
     "    def->mode = comDevelop;\n    def->set_default_value(new ConfigOptionEnumsGeneric { (int)cslUniformCooling });\n",
     "    def->mode = comAdvanced; // Unify Slicer: visible, Consistent surface by default (issue #12)\n"
     "    def->set_default_value(new ConfigOptionEnumsGeneric { (int)cslConsistentSurface });\n",
     "Unify Slicer: visible, Consistent surface by default")
edit("src/libslic3r/PrintConfig.cpp",
     "    def->mode = comDevelop;\n    def->set_default_value(new ConfigOptionFloats { 10.0 });\n",
     "    def->mode = comAdvanced; // Unify Slicer: visible (issue #12)\n    def->set_default_value(new ConfigOptionFloats { 10.0 });\n",
     "Unify Slicer: visible (issue #12)\n    def->set_default_value(new ConfigOptionFloats { 10.0 });")
edit("src/libslic3r/PrintConfig.cpp",
     "    def->mode = comDevelop;\n    def->set_default_value(new ConfigOptionFloats { 250. });\n",
     "    def->mode = comAdvanced; // Unify Slicer: short travel acceleration visible (issue #12)\n    def->set_default_value(new ConfigOptionFloats { 250. });\n",
     "Unify Slicer: short travel acceleration visible")
