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

# Ask Claude dialog: sources + Help menu entry
edit("src/slic3r/CMakeLists.txt", "    GUI/WebPreprintDialog.cpp\n",
     "    GUI/WebPreprintDialog.cpp\n    GUI/UnifyChatDialog.hpp\n    GUI/UnifyChatDialog.cpp\n", "UnifyChatDialog.cpp")
edit("src/slic3r/GUI/MainFrame.cpp", '#include "MainFrame.hpp"\n', '#include "MainFrame.hpp"\n#include "UnifyChatDialog.hpp"\n', '#include "UnifyChatDialog.hpp"')
edit("src/slic3r/GUI/MainFrame.cpp", "    wxMenu* helpMenu = new wxMenu();\n",
     "    wxMenu* helpMenu = new wxMenu();\n\n    // Unify Slicer: built-in Claude assistant\n"
     "    append_menu_item(helpMenu, wxID_ANY, _L(\"Ask Claude...\"), _L(\"Chat with Claude about your print and apply suggested settings\"),\n"
     "        [](wxCommandEvent&) { UnifyChatDialog::show_dialog(); });\n    helpMenu->AppendSeparator();\n",
     "UnifyChatDialog::show_dialog")

# Profiles ship inside the app (official Snapmaker set + Unify presets): skip the Snapmaker cloud profile update,
# which would replace the bundled set and remove the Unify presets.
edit("src/slic3r/Utils/PresetUpdater.cpp", "void PresetUpdater::priv::sync_config(bool isAuto_check)\n{\n",
     "void PresetUpdater::priv::sync_config(bool isAuto_check)\n{\n"
     "    // Unify Slicer: bundled profiles are refreshed by each Unify build; cloud profile update disabled.\n"
     "    if (!isAuto_check) GUI::wxGetApp().QueueEvent(new wxCommandEvent(EVT_NO_PRESET_UPDATE));\n    return;\n",
     "Unify Slicer: bundled profiles")

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
print("Done")
