#ifndef slic3r_UnifyResonance_hpp_
#define slic3r_UnifyResonance_hpp_

// Unify Slicer: Snapmaker U1 resonance fast check results (issue #1, phase 2).
// Watches the printer console through Moonraker for the UNIFY_FASTCHECK_BEGIN/END markers that the
// fast-check block in the U1 start G-code emits, parses the input shaper results, and shows either a
// short "OK" notice or a warning dialog with Pause / Cancel print / Continue and a 15 s auto-continue.

#include <map>
#include <string>
#include <vector>

class wxWindow;

namespace Slic3r { namespace GUI {

// Starts the background console watcher (safe to call more than once).
void unify_resonance_monitor_start();
// Shows the log of recent resonance checks.
void unify_resonance_show_log();
// Checks that Moonraker answers at the given address and shows the result (issue #1).
void unify_resonance_test_connection(const std::string &host, wxWindow *parent);

namespace unify_res {

// Hard-coded limits (issue #1)
constexpr double X_SWEEP_START = 35.0, X_SWEEP_END = 75.0; // Hz, must match the start G-code block
constexpr double Y_SWEEP_START = 30.0, Y_SWEEP_END = 70.0;
constexpr double EDGE_HZ             = 2.0;    // peak within 2 Hz of the sweep start/end
constexpr double MAX_VIBRATION_PCT   = 5.0;    // remaining vibration with the recommended shaper
constexpr double MIN_MAX_ACCEL       = 5000.0; // mm/s^2
constexpr double SHIFT_PCT           = 15.0;   // change vs. baseline median
constexpr int    BASELINE_KEEP       = 5;      // normal results kept per axis
constexpr int    BASELINE_MIN        = 3;      // results needed before the shift rule applies
constexpr int    WARN_TIMEOUT_S      = 15;     // abnormal dialog auto-continues after this
constexpr int    OK_NOTICE_S         = 10;     // OK notice closes after this
constexpr int    LOG_KEEP            = 30;

struct Fit
{
    double freq      = 0.;
    double vib       = -1.;
    double max_accel = -1.;
};

struct AxisResult
{
    std::map<std::string, Fit> fits;
    bool        has_rec  = false;
    std::string rec_type;
    double      rec_freq = 0.;
    bool        has_sel  = false;
    std::string sel_type;
    double      sel_freq = 0.;
    bool        rejected = false; // firmware said "frequency out of range, using default"
    double      fallback_freq = 0.;
};

struct CheckResult
{
    AxisResult x, y;
};

struct Baseline
{
    std::vector<double> x, y;
};

struct Evaluation
{
    bool                     abnormal = false;
    std::vector<std::string> summary;  // one line per axis (measured + applied)
    std::vector<std::string> warnings; // empty when normal
};

CheckResult parse(const std::vector<std::string> &lines);
Evaluation  evaluate(const CheckResult &r, const Baseline &baseline, int sweep_time_s);
std::string short_summary(const CheckResult &r); // "X mzv @ 57.2 Hz, Y mzv @ 49.2 Hz"

} // namespace unify_res

}} // namespace Slic3r::GUI

#endif
