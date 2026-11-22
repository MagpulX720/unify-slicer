// Unify Slicer: Adaptive wall generator (issue #19).
// Arachne makes the walls (thin features fill with one continuous loop); then
//  1. snap_outer_to_classic(): wherever the outer wall is at full width, its path is replaced by the exact Classic offset
//     of the outline (Arachne simplifies curves into flats of up to 0.025 mm; Classic follows them within ~0.0001 mm);
//  2. anchor_open_lines(): a thin feature printed as one open line starts where it joins the part and ends at the tip.
// The Balanced bead rule (no hair-thin lines) is in Arachne/BeadingStrategy/UnifyBalancedBeadingStrategy.hpp.
#pragma once

#include "Arachne/utils/ExtrusionLine.hpp"
#include "BoundingBox.hpp"
#include "Polygon.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

namespace Slic3r::UnifyAdaptive {

struct ProjHit { size_t poly = 0; size_t seg = 0; double t = 0; double param = 0; double dist = 1e30; };

inline ProjHit project(const Polygons &C, const std::vector<std::vector<double>> &cum, const std::vector<BoundingBox> &bbs, const Vec2d &q, double max_dist)
{
    ProjHit best;
    for (size_t pi = 0; pi < C.size(); ++pi) {
        const BoundingBox &bb = bbs[pi];
        if (q.x() < bb.min.x() - max_dist || q.x() > bb.max.x() + max_dist || q.y() < bb.min.y() - max_dist || q.y() > bb.max.y() + max_dist)
            continue;
        const Points &P = C[pi].points;
        for (size_t i = 0; i < P.size(); ++i) {
            const Vec2d a = P[i].cast<double>(), b = P[(i + 1) % P.size()].cast<double>(), d = b - a;
            const double l2 = d.squaredNorm(), t = l2 > 0 ? std::clamp((q - a).dot(d) / l2, 0., 1.) : 0.;
            const double dist = (a + t * d - q).norm();
            if (dist < best.dist) { best.poly = pi; best.seg = i; best.t = t; best.dist = dist; best.param = cum[pi][i] + t * std::sqrt(l2); }
        }
    }
    return best;
}

// C: the Classic outer-wall centreline (outline offset inward by the outer bead's centre distance).
inline void snap_outer_to_classic(std::vector<Arachne::VariableWidthLines> &perimeters, const Polygons &C, coord_t nominal_w)
{
    if (perimeters.empty() || C.empty())
        return;
    const double tol_w    = 0.01 * double(nominal_w);
    const double max_dist = double(scaled<coord_t>(0.03));
    std::vector<std::vector<double>> cum(C.size());
    std::vector<double>              len(C.size());
    std::vector<BoundingBox>         bbs(C.size());
    for (size_t pi = 0; pi < C.size(); ++pi) {
        const Points &P = C[pi].points;
        cum[pi].push_back(0);
        for (size_t i = 0; i < P.size(); ++i)
            cum[pi].push_back(cum[pi].back() + (P[(i + 1) % P.size()] - P[i]).cast<double>().norm());
        len[pi] = cum[pi].back();
        bbs[pi] = BoundingBox(P);
    }
    for (Arachne::VariableWidthLines &lines : perimeters)
        for (Arachne::ExtrusionLine &line : lines) {
            if (line.inset_idx != 0 || !line.is_closed || line.junctions.size() < 3)
                continue;
            std::vector<Arachne::ExtrusionJunction> &J = line.junctions;
            // Arachne closes a loop by repeating the first junction at the end: work on the open form.
            const bool repeated = J.front().p == J.back().p;
            const size_t n = repeated ? J.size() - 1 : J.size();
            if (n < 3)
                continue;
            std::vector<char>    full(n);
            std::vector<ProjHit> h(n);
            for (size_t i = 0; i < n; ++i) {
                h[i]    = project(C, cum, bbs, J[i].p.cast<double>(), max_dist);
                full[i] = std::abs(double(J[i].w - nominal_w)) < tol_w && h[i].dist < max_dist;
            }
            int dir = 0;
            for (size_t i = 0; i < n && !dir; ++i) {
                const size_t k = (i + 1) % n;
                if (full[i] && full[k] && h[i].poly == h[k].poly) {
                    double dp = h[k].param - h[i].param, L = len[h[i].poly];
                    if (dp > L / 2) dp -= L;
                    if (dp < -L / 2) dp += L;
                    if (std::abs(dp) > 1.) dir = dp > 0 ? 1 : -1;
                }
            }
            if (!dir)
                continue;
            const coord_t pidx = J[0].perimeter_index;
            auto cpt = [&](const ProjHit &q) {
                const Points &P = C[q.poly].points;
                const Vec2d a = P[q.seg].cast<double>(), b = P[(q.seg + 1) % P.size()].cast<double>();
                const Vec2d r = a + q.t * (b - a);
                return Arachne::ExtrusionJunction(Point(coord_t(std::round(r.x())), coord_t(std::round(r.y()))), nominal_w, pidx);
            };
            auto between = [&](std::vector<Arachne::ExtrusionJunction> &o, const ProjHit &h0, const ProjHit &h1) {
                const size_t pi = h0.poly; const Points &P = C[pi].points; const size_t m = P.size(); const double L = len[pi];
                double d = dir > 0 ? h1.param - h0.param : h0.param - h1.param;
                if (d < 0) d += L;
                size_t v = dir > 0 ? (h0.seg + 1) % m : h0.seg;
                const double eps = double(scaled<coord_t>(0.002));
                for (size_t guard = 0; guard < m; ++guard) {
                    double dv = dir > 0 ? cum[pi][v] - h0.param : h0.param - cum[pi][v];
                    if (dv < 0) dv += L;
                    if (dv >= d - eps) break;
                    if (dv > eps) o.emplace_back(P[v], nominal_w, pidx);
                    v = dir > 0 ? (v + 1) % m : (v + m - 1) % m;
                }
            };
            auto plen = [](const std::vector<Arachne::ExtrusionJunction> &v, size_t a, size_t b) {
                double l = 0; for (size_t q = a; q < b; ++q) l += (v[q + 1].p - v[q].p).cast<double>().norm(); return l; };

            std::vector<Arachne::ExtrusionJunction> out;
            const bool all = std::all_of(full.begin(), full.end(), [](char f) { return f != 0; }) &&
                             std::all_of(h.begin(), h.end(), [&](const ProjHit &q) { return q.poly == h[0].poly; });
            if (all) {
                out.push_back(cpt(h[0]));
                ProjHit end = h[0];
                end.param -= dir * double(scaled<coord_t>(0.001));
                between(out, h[0], end);
                double la = 0, lc = 0;
                for (size_t q = 0; q < n; ++q) la += (J[(q + 1) % n].p - J[q].p).cast<double>().norm();
                for (size_t q = 0; q < out.size(); ++q) lc += (out[(q + 1) % out.size()].p - out[q].p).cast<double>().norm();
                if (std::abs(lc - la) > 0.03 * la + double(scaled<coord_t>(0.05)))
                    continue;                                   // not the same piece of surface: keep Arachne's loop
            } else {
                size_t s0 = 0;
                for (size_t i = 0; i < n; ++i) if (!full[i]) s0 = (i + 1) % n;
                for (size_t c = 0; c < n;) {
                    const size_t i = (s0 + c) % n;
                    if (!full[i]) { out.push_back(J[i]); ++c; continue; }
                    size_t e = c;
                    while (e + 1 < n && full[(s0 + e + 1) % n] && h[(s0 + e + 1) % n].poly == h[i].poly) ++e;
                    const ProjHit &h0 = h[i], &h1 = h[(s0 + e) % n];
                    std::vector<Arachne::ExtrusionJunction> run;
                    run.push_back(cpt(h0));
                    if (e > c) { between(run, h0, h1); run.push_back(cpt(h1)); }
                    double la = 0;
                    for (size_t q = c; q < e; ++q) la += (J[(s0 + q + 1) % n].p - J[(s0 + q) % n].p).cast<double>().norm();
                    const double lc = plen(run, 0, run.size() - 1);
                    if (std::abs(lc - la) <= 0.03 * la + double(scaled<coord_t>(0.05)))
                        out.insert(out.end(), run.begin(), run.end());
                    else
                        for (size_t q = c; q <= e; ++q) out.push_back(J[(s0 + q) % n]);
                    c = e + 1;
                }
            }
            if (out.size() < 3)
                continue;
            if (repeated)
                out.push_back(out.front());
            J = std::move(out);
        }
}

// Open lines (thin features printed as a single line): start at the end that joins the rest of the part.
inline void anchor_open_lines(std::vector<Arachne::VariableWidthLines> &perimeters)
{
    const double r  = double(scaled<coord_t>(0.8));
    const double r2 = r * r;
    std::vector<std::pair<const Arachne::ExtrusionLine*, BoundingBox>> all;
    for (const Arachne::VariableWidthLines &lines : perimeters)
        for (const Arachne::ExtrusionLine &l : lines) {
            if (l.junctions.empty()) continue;
            BoundingBox bb; for (const auto &j : l.junctions) bb.merge(j.p);
            all.emplace_back(&l, bb);
        }
    auto crowd = [&](const Arachne::ExtrusionLine *self, const Point &q) {
        int n = 0;
        for (const auto &[l, bb] : all) {
            if (l == self || q.x() < bb.min.x() - r || q.x() > bb.max.x() + r || q.y() < bb.min.y() - r || q.y() > bb.max.y() + r)
                continue;
            for (const auto &j : l->junctions)
                if ((j.p - q).cast<double>().squaredNorm() < r2) { ++n; break; }
        }
        return n;
    };
    for (Arachne::VariableWidthLines &lines : perimeters)
        for (Arachne::ExtrusionLine &l : lines)
            if (!l.is_closed && l.inset_idx == 0 && l.junctions.size() >= 2 &&
                crowd(&l, l.junctions.back().p) > crowd(&l, l.junctions.front().p))
                std::reverse(l.junctions.begin(), l.junctions.end());
}

} // namespace Slic3r::UnifyAdaptive
