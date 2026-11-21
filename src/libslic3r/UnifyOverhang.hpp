#ifndef slic3r_UnifyOverhang_hpp_
#define slic3r_UnifyOverhang_hpp_

// Unify Slicer: overhang speed by angle (issue #2).
// A table of speeds per overhang angle (10 or 5 degree rows, 0-90 degrees from vertical)
// replaces Orca's four overhang-% bands. Rows can be auto-filled from three filament values.
// Header-only so both the slicer (GCode.cpp) and the settings UI (Tab.cpp) use the same math.

#include <algorithm>
#include <cmath>
#include <vector>

namespace Slic3r { namespace unify_overhang {

constexpr int    ROWS_COARSE       = 9;    // 10 degree rows
constexpr int    ROWS_FINE         = 18;   // 5 degree rows
constexpr double ANGLE_MAX         = 90.0; // degrees from vertical
constexpr double SPEED_MIN_NONZERO = 5.0;  // mm/s; a row value of 0 means "normal wall speed"

inline double deg2rad(double d) { return d * 3.14159265358979323846 / 180.0; }
inline double rad2deg(double r) { return r * 180.0 / 3.14159265358979323846; }

// Angle at which the overhang reaches 100 % of the line width (steeper = bridge).
inline double bridge_angle_deg(double layer_h, double width)
{
    if (layer_h <= 0. || width <= 0.)
        return ANGLE_MAX;
    return rad2deg(std::atan(width / layer_h));
}

inline double round5(double v) { return std::round(v / 5.0) * 5.0; }

// Auto-fill speed for the row ending at edge_deg. 0 = normal wall speed.
inline double auto_speed(double edge_deg, double start_deg, double max_speed, double min_speed,
                         double ref_speed, double layer_h, double width)
{
    if (edge_deg <= start_deg + 1e-9)
        return 0.;
    double vcap = max_speed;
    if (ref_speed > 0.)
        vcap = std::min(vcap, ref_speed);
    const double vmin = std::min(min_speed, vcap);
    const double tb   = bridge_angle_deg(layer_h, width);
    double       t    = tb > start_deg ? (edge_deg - start_deg) / (tb - start_deg) : 1.;
    t                 = std::min(1., std::max(0., t));
    return std::max(SPEED_MIN_NONZERO, round5(vmin + (vcap - vmin) * (1. - t)));
}

// Auto-filled table with `rows` rows (9 or 18).
inline std::vector<double> auto_rows(int rows, double start_deg, double max_speed, double min_speed,
                                     double ref_speed, double layer_h, double width)
{
    std::vector<double> out(std::max(rows, 0), 0.);
    const double        step = ANGLE_MAX / std::max(rows, 1);
    for (int i = 0; i < rows; ++i)
        out[i] = auto_speed((i + 1) * step, start_deg, max_speed, min_speed, ref_speed, layer_h, width);
    return out;
}

// Turns a speed table into the overlap levels (% of the line width resting on the layer below)
// and absolute speeds used by Orca's extrusion quality estimator. Each row's speed covers its
// whole angle range; speeds never get faster as the angle gets steeper.
inline void build_levels(const std::vector<double> &rows, double ref_speed, double layer_h, double width,
                         std::vector<double> &overlaps, std::vector<double> &speeds)
{
    overlaps.clear();
    speeds.clear();
    const int n = int(rows.size());
    if (n == 0 || ref_speed <= 0. || layer_h <= 0. || width <= 0.)
        return;
    const double step = ANGLE_MAX / n;
    const double eps  = 0.01; // degrees, keeps row boundaries as steps
    auto overlap_at = [&](double deg) {
        if (deg >= ANGLE_MAX - 1e-9)
            return 0.;
        const double d = layer_h * std::tan(deg2rad(deg));
        return std::max(0., 100. * (1. - d / width));
    };
    double cur = ref_speed;
    for (int i = 0; i < n; ++i) {
        const double v = rows[i];
        cur            = std::min(cur, v <= 0. ? ref_speed : std::max(v, SPEED_MIN_NONZERO));
        const double a0 = i * step + (i == 0 ? 0. : eps);
        const double a1 = (i + 1) * step;
        const double o0 = overlap_at(a0), o1 = overlap_at(a1);
        overlaps.push_back(o0);
        speeds.push_back(cur);
        overlaps.push_back(o1);
        speeds.push_back(cur);
        if (o1 <= 0.)
            break; // everything steeper prints as a bridge
    }
}

}} // namespace Slic3r::unify_overhang

#endif
