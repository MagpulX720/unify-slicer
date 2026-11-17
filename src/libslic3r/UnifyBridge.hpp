#ifndef slic3r_UnifyBridge_hpp_
#define slic3r_UnifyBridge_hpp_

// Unify Slicer (issue #3, phase 3): smarter automatic bridge direction.
// For each bridge area, try every 5 degrees and keep the direction where every bridge line lands on
// solid material at both ends with the shortest longest unsupported span. If no direction
// anchors every line, the one anchoring the most lines wins and the area is flagged.

#include "BoundingBox.hpp"
#include "ClipperUtils.hpp"
#include "ExPolygon.hpp"
#include "Line.hpp"
#include "UnifyBridgeInfo.hpp"

#include <cmath>
#include <vector>

namespace Slic3r {
namespace unify_bridge {

constexpr int    AUTO_STEP_DEG   = 5;
constexpr double MIN_ANCHOR_MM   = 2.0;  // check up to 2 mm past each line end for solid below ...
constexpr double ANCHOR_LINES    = 1.5;  // ... but no further than 1.5 line widths (thin walls are still anchors)
constexpr double WARN_SPAN_MM    = 40.0; // warn above this longest span
constexpr double FULL_ANCHORED   = 0.97; // share of anchored lines that counts as "every line" (edge noise)
constexpr double SPAN_TIE_MM     = 0.5;  // spans this close count as equal

struct Eval
{
    bool   valid    = false;
    double angle    = 0.;  // radians, [0, PI)
    double span     = 0.;  // mm, longest line over the bridge
    double anchored = 0.;  // share of lines anchored at both ends
    double anchored_len = 0.; // total anchored length, mm (tie-break)
};

class Finder
{
public:
    Finder(const ExPolygons &bridge, const ExPolygons &lower, coord_t spacing)
        : m_bridge(bridge), m_lower(lower), m_spacing(std::max<coord_t>(spacing, coord_t(scale_(0.1))))
    {
        m_clip = offset(m_bridge, 0.5f * float(m_spacing));
        for (const ExPolygon &e : m_lower)
            m_lower_bb.emplace_back(get_extents(e));
    }

    bool usable() const { return !m_bridge.empty() && !m_lower.empty() && !m_clip.empty(); }

    Eval evaluate(double angle) const
    {
        Eval r;
        r.angle = normalize(angle);
        const double s = std::sin(r.angle), c = std::cos(r.angle);
        BoundingBox  bbox = get_extents_rotated(m_clip, -r.angle);
        Lines        lines;
        for (coord_t y = bbox.min.y() + m_spacing / 2; y <= bbox.max.y(); y += m_spacing)
            lines.emplace_back(Point(coord_t(std::round(c * bbox.min.x() - s * y)), coord_t(std::round(c * y + s * bbox.min.x()))),
                               Point(coord_t(std::round(c * bbox.max.x() - s * y)), coord_t(std::round(c * y + s * bbox.max.x()))));
        const Lines clipped = intersection_ln(lines, m_clip);
        size_t      n = 0, n_anchored = 0;
        const Vec2d dir(c, s);
        const double anchor = std::min(double(scale_(MIN_ANCHOR_MM)), ANCHOR_LINES * double(m_spacing));
        for (const Line &l : clipped) {
            const double len = l.length();
            if (len < double(m_spacing))
                continue;
            ++n;
            r.span = std::max(r.span, unscale<double>(len));
            // which way does this clipped piece run?
            Vec2d d = (l.b - l.a).cast<double>();
            d /= d.norm();
            if (d.dot(dir) < 0.)
                d = -d;
            const Vec2d a = l.a.cast<double>(), b = l.b.cast<double>();
            const Vec2d lo = (l.b - l.a).cast<double>().dot(dir) >= 0. ? a : b; // start along dir
            const Vec2d hi = (l.b - l.a).cast<double>().dot(dir) >= 0. ? b : a;
            if (solid(lo - d * (0.5 * anchor)) && solid(lo - d * anchor) && solid(hi + d * (0.5 * anchor)) && solid(hi + d * anchor)) {
                ++n_anchored;
                r.anchored_len += unscale<double>(len);
            }
        }
        if (n == 0)
            return r;
        r.valid    = true;
        r.anchored = double(n_anchored) / double(n);
        return r;
    }

    // Best direction; `prefer` (radians) breaks ties, normally Orca's own pick.
    Eval best(double prefer) const
    {
        Eval best;
        if (!usable())
            return best;
        std::vector<Eval> all;
        for (int deg = 0; deg < 180; deg += AUTO_STEP_DEG)
            if (Eval e = evaluate(double(deg) * M_PI / 180.); e.valid)
                all.push_back(e);
        if (Eval e = evaluate(prefer); e.valid)
            all.push_back(e);
        if (all.empty())
            return best;
        bool any_full = false;
        for (const Eval &e : all)
            any_full |= e.anchored >= FULL_ANCHORED;
        auto better = [any_full, prefer](const Eval &a, const Eval &b) {
            // a better than b?
            if (!any_full && std::abs(a.anchored - b.anchored) > 0.02)
                return a.anchored > b.anchored;
            if (any_full && (a.anchored >= FULL_ANCHORED) != (b.anchored >= FULL_ANCHORED))
                return a.anchored >= FULL_ANCHORED;
            if (std::abs(a.span - b.span) > SPAN_TIE_MM)
                return a.span < b.span;
            if (std::abs(a.anchored_len - b.anchored_len) > 1.)
                return a.anchored_len > b.anchored_len;
            return angle_diff(a.angle, prefer) < angle_diff(b.angle, prefer);
        };
        best = all.front();
        for (const Eval &e : all)
            if (better(e, best))
                best = e;
        return best;
    }

    static double normalize(double a)
    {
        a = std::fmod(a, M_PI);
        if (a < 0.)
            a += M_PI;
        if (a >= M_PI - 1e-9)
            a = 0.;
        return a;
    }
    static double angle_diff(double a, double b)
    {
        double d = std::abs(normalize(a) - normalize(b));
        return std::min(d, M_PI - d);
    }

private:
    bool solid(const Vec2d &p) const
    {
        const Point pt(coord_t(std::round(p.x())), coord_t(std::round(p.y())));
        for (size_t i = 0; i < m_lower.size(); ++i)
            if (m_lower_bb[i].contains(pt) && m_lower[i].contains(pt))
                return true;
        return false;
    }

    const ExPolygons        &m_bridge;
    const ExPolygons        &m_lower;
    coord_t                  m_spacing;
    Polygons                 m_clip;
    std::vector<BoundingBox> m_lower_bb;
};

inline UnifyBridgeInfo make_info(const ExPolygons &bridge, double print_z, const Eval &e, bool custom)
{
    UnifyBridgeInfo info;
    info.print_z      = print_z;
    info.angle_deg    = e.angle * 180. / M_PI;
    info.span_mm      = e.span;
    info.anchored     = e.anchored;
    info.custom_angle = custom;
    double area = 0.;
    Vec2d  centre(0., 0.);
    for (const ExPolygon &ex : bridge) {
        const double a = std::abs(ex.area());
        area += a;
        centre += a * ex.contour.centroid().cast<double>();
    }
    if (area > 0.)
        centre /= area;
    info.area_mm2 = unscale<double>(unscale<double>(area));
    info.x        = unscale<double>(centre.x());
    info.y        = unscale<double>(centre.y());
    info.flagged  = e.valid && (e.span > WARN_SPAN_MM || e.anchored < FULL_ANCHORED);
    return info;
}

} // namespace unify_bridge
} // namespace Slic3r

#endif
