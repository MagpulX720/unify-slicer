#ifndef slic3r_GUI_UnifyResonanceLog_hpp_
#define slic3r_GUI_UnifyResonanceLog_hpp_

// Unify Slicer: resonance check log file (CSV, opens in Numbers, Excel, Google Sheets or any text editor)
// and the Calibration > Resonance check log window (last 3 results + link to the full log).

#include <string>
#include <wx/string.h>

namespace Slic3r { namespace GUI {

// Full path of the log file: <Unify settings folder>/resonance_log.csv
std::string unify_resonance_csv_path();
// Adds one line to the log file (creates it with a header row the first time).
void unify_resonance_csv_append(const std::string &printer, const std::string &entry);
// Window shown from Calibration > Resonance check log (Unify).
void unify_resonance_show_log_dialog(const wxString &status, const wxString &recent);

}} // namespace Slic3r::GUI

#endif
