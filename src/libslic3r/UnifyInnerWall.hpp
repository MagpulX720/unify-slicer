#ifndef slic3r_UnifyInnerWall_hpp_
#define slic3r_UnifyInnerWall_hpp_

// Unify Slicer: inner wall overhang slowdown.
// Slows the inner wall that borders an overhanging outer wall. For each point of the inner wall the overhang of the
// outer wall next to it is measured as how far this layer's outline sticks out past the layer below
// (distance to the layer below minus distance to this layer's outline), turned into an angle from vertical.
// Header-only; used by GCode.cpp.

#include "AABBTreeLines.hpp"
#include "ExtrusionEntity.hpp"
#include "Layer.hpp"
#include "GCode/ExtrusionProcessor.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

namespace Slic3r { namespace unify_inner_wall {

constexpr double AUTO_MIN_PCT_DEFAULT = 40.0; // Auto mode steepest speed when the user leaves it at 0
constexpr double SPEED_FLOOR         = 5.0;  // mm/s
constexpr double SAMPLE_STEP_MM      = 0.5;  // inner wall is checked every 0.5 mm
constexpr double BORDER_FACTOR       = 1.6;  // only the inner wall within ~1.6 line widths of the outline

inline double rad2deg(double r) { return r * 180.0 / 3.14159265358979323846; }

// % of the outer wall speed for an overhang of `angle` degrees.
// manual: fixed pct. auto: 100 % at the start angle, falling to the steepest % at the bridge angle.
inline double speed_pct(bool manual, double angle, double start, double manual_pct, double auto_min_pct, double bridge_angle)
{
    if (manual)
        return manual_pct;
    const double minp = auto_min_pct > 0. ? auto_min_pct : AUTO_MIN_PCT_DEFAULT;
    const double span = std::max(1.0, bridge_angle - start);
    const double t    = std::clamp((angle - start) / span, 0.0, 1.0);
    return 100.0 - (100.0 - minp) * t;
}

struct LayerCache
{
    const Layer *layer = nullptr;
    double       z     = -1.;
    size_t       n_cur = 0, n_low = 0;
    AABBTreeLines::LinesDistancer<Linef> cur, low;
};

// Caps the speed of the points of an inner wall path. `pts` is the estimator output (may be empty, then the path's
// own points are used). Returns true and replaces `pts` when any point was slowed.
inline bool apply(std::vector<ProcessedPoint> &pts, const ExtrusionPath &path, const Layer &layer, double path_speed,
                  double outer_speed, bool manual, double start_angle, double manual_pct, double auto_min_pct, LayerCache &cache)
{
    if (layer.lower_layer == nullptr || path.polyline.points.size() < 2 || path.height <= 0.f || path.width <= 0.f || outer_speed <= 0.)
        return false;
    if (cache.layer != &layer || std::abs(cache.z - layer.print_z) > 1e-6 || cache.n_cur != layer.lslices.size() ||
        cache.n_low != layer.lower_layer->lslices.size()) {
        cache.cur   = AABBTreeLines::LinesDistancer<Linef>{to_unscaled_linesf(layer.lslices)};
        cache.low   = AABBTreeLines::LinesDistancer<Linef>{to_unscaled_linesf(layer.lower_layer->lslices)};
        cache.layer = &layer;
        cache.z     = layer.print_z;
        cache.n_cur = layer.lslices.size();
        cache.n_low = layer.lower_layer->lslices.size();
    }

    std::vector<ProcessedPoint> base = pts;
    if (base.empty())
        for (const Point &p : path.polyline.points)
            base.push_back(ProcessedPoint{p, float(path_speed), 1.f});
    if (base.size() < 2)
        return false;

    // Sample the path finely so short overhangs are not missed. A segment prints at its start point's speed.
    std::vector<ProcessedPoint> sub;
    sub.reserve(base.size() * 2);
    sub.push_back(base.front());
    for (size_t i = 1; i < base.size(); ++i) {
        const Vec2d  a   = unscaled(base[i - 1].p);
        const Vec2d  b   = unscaled(base[i].p);
        const double len = (b - a).norm();
        const int    n   = std::max(1, int(std::ceil(len / SAMPLE_STEP_MM)));
        for (int k = 1; k < n; ++k) {
            ProcessedPoint q = base[i - 1];
            const Vec2d    m = a + (b - a) * (double(k) / double(n));
            q.p              = Point::new_scale(m.x(), m.y());
            sub.push_back(q);
        }
        sub.push_back(base[i]);
    }

    const double h            = path.height;
    const double w            = path.width;
    const double bridge_angle = rad2deg(std::atan2(w, h));
    bool         changed      = false;
    for (ProcessedPoint &q : sub) {
        const Vec2d pos = unscaled(q.p);
        auto [d_cur, l_cur, x_cur] = cache.cur.distance_from_lines_extra<true>(pos);
        if (d_cur < -BORDER_FACTOR * w)
            continue; // a wall further inside, not the one bordering the outer wall
        auto [d_low, l_low, x_low] = cache.low.distance_from_lines_extra<true>(pos);
        const double stick_out = double(d_low) - double(d_cur); // how far this layer's outline sticks out past the layer below
        if (stick_out <= 0.)
            continue;
        const double angle = rad2deg(std::atan2(stick_out, h));
        if (angle + 1e-6 < start_angle)
            continue;
        const double v = std::max(SPEED_FLOOR, outer_speed * speed_pct(manual, angle, start_angle, manual_pct, auto_min_pct, bridge_angle) / 100.);
        if (v < double(q.speed) - 0.5) {
            q.speed = float(v);
            changed = true;
        }
    }
    if (changed)
        pts = std::move(sub);
    return changed;
}

}} // namespace Slic3r::unify_inner_wall

#endif
