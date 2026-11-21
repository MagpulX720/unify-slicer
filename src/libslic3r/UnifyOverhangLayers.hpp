#ifndef slic3r_UnifyOverhangLayers_hpp_
#define slic3r_UnifyOverhangLayers_hpp_

// Unify Slicer: auto adaptive layer height for overhangs only (issue #7).
// Builds a layer height profile that stays at the process layer height everywhere except in the Z bands
// where the model has overhangs. There the layers get thinner as the overhang gets steeper, down to the
// printer's min layer height for the nozzle (Auto) or a thinnest layer the user picks (Manual, never below
// the printer's minimum). Flat ceilings / bridges (88 deg and flatter) and tiny overhangs are ignored. Every change of layer
// height goes through at least two in-between layers, and a step down is finished before the overhang starts.

#include <deque>

#include "Slicing.hpp"
#include "TriangleMesh.hpp"

#include <algorithm>
#include <cmath>
#include <utility>
#include <vector>

namespace Slic3r {
namespace unify_overhang_layers {

// Hard-coded behaviour (issue #7)
constexpr double START_DEG       = 40.0; // thinning starts at this overhang angle (0 = vertical wall)
constexpr double FULL_DEG        = 70.0; // minimum layer height reached here
constexpr double BRIDGE_DEG      = 88.0; // flatter than this = flat bridge / ceiling: ignored (80-85 deg overhangs still get the thinnest layers)
constexpr int    MIN_STEPS       = 2;    // at least this many in-between layers for every height change
constexpr double MAX_STEP_MM     = 0.04; // ... and more when one step would change the height by more than this
constexpr double MIN_AREA_MM2    = 4.0;  // overhang area needed inside the window to count
constexpr double WINDOW_MM       = 0.5;  // +- window for the area test
constexpr double BIN_MM          = 0.02; // Z resolution of the analysis
constexpr int    LEVELS          = 24;   // quantised target heights

// Overhang angle in degrees from vertical for a facet normal (0 = vertical wall, 90 = flat ceiling).
inline double overhang_deg(const Vec3d &n)
{
    const double len = n.norm();
    if (len <= 0.)
        return 0.;
    const double nz = -n.z() / len;
    return nz <= 0. ? 0. : std::asin(std::min(1., nz)) * 180. / M_PI;
}

// Target layer height for an overhang of angle `deg`, or hmax when it doesn't need thinning.
inline double target_height(double deg, double hmin, double hmax)
{
    if (deg < START_DEG || deg >= BRIDGE_DEG)
        return hmax;
    const double t = std::clamp((deg - START_DEG) / (FULL_DEG - START_DEG), 0., 1.);
    return hmax - t * (hmax - hmin);
}

struct Mesh
{
    const indexed_triangle_set *its = nullptr;
    Transform3d                 trafo = Transform3d::Identity(); // to print coordinates (Z = 0 at the bed)
};

// Per-bin target layer height (bins of BIN_MM starting at z = 0) for an object of height `height`.
inline std::vector<double> bin_targets(const std::vector<Mesh> &meshes, double height, double z_scale, double hmin, double hmax)
{
    const int nbins = std::max(1, int(std::ceil(height / BIN_MM)));
    std::vector<float> acc(size_t(nbins) * LEVELS, 0.f); // area per bin per level
    auto level_of = [hmin, hmax](double h) {
        return std::clamp(int(std::floor((h - hmin) / (hmax - hmin) * (LEVELS - 1) + 1e-9)), 0, LEVELS - 1);
    };
    for (const Mesh &m : meshes) {
        if (m.its == nullptr)
            continue;
        for (const stl_triangle_vertex_indices &f : m.its->indices) {
            const Vec3d a = m.trafo * m.its->vertices[f[0]].cast<double>();
            const Vec3d b = m.trafo * m.its->vertices[f[1]].cast<double>();
            const Vec3d c = m.trafo * m.its->vertices[f[2]].cast<double>();
            const Vec3d n = (b - a).cross(c - a);
            const double area = 0.5 * n.norm();
            if (area <= 0.)
                continue;
            const double h = target_height(overhang_deg(n), hmin, hmax);
            if (h >= hmax - 1e-6)
                continue;
            const int    lvl = level_of(h);
            const double z0  = std::min({ a.z(), b.z(), c.z() }) / z_scale;
            const double z1  = std::max({ a.z(), b.z(), c.z() }) / z_scale;
            if (z1 < 0. || z0 > height)
                continue;
            const int b0 = std::clamp(int(std::floor(std::max(0., z0) / BIN_MM)), 0, nbins - 1);
            const int b1 = std::clamp(int(std::floor(std::min(height, z1) / BIN_MM)), 0, nbins - 1);
            const float share = float(area / double(b1 - b0 + 1));
            for (int i = b0; i <= b1; ++i)
                acc[size_t(i) * LEVELS + lvl] += share;
        }
    }
    // cumulative over levels: acc[i][l] = area needing level <= l
    for (int i = 0; i < nbins; ++i)
        for (int l = 1; l < LEVELS; ++l)
            acc[size_t(i) * LEVELS + l] += acc[size_t(i) * LEVELS + l - 1];
    // windowed sum along Z via prefix sums, per level
    const int w = std::max(0, int(std::round(WINDOW_MM / BIN_MM)));
    std::vector<double> prefix(size_t(nbins + 1) * LEVELS, 0.);
    for (int i = 0; i < nbins; ++i)
        for (int l = 0; l < LEVELS; ++l)
            prefix[size_t(i + 1) * LEVELS + l] = prefix[size_t(i) * LEVELS + l] + acc[size_t(i) * LEVELS + l];
    std::vector<double> out(nbins, hmax);
    for (int i = 0; i < nbins; ++i) {
        const int lo = std::max(0, i - w), hi = std::min(nbins, i + w + 1);
        for (int l = 0; l < LEVELS; ++l) {
            const double sum = prefix[size_t(hi) * LEVELS + l] - prefix[size_t(lo) * LEVELS + l];
            if (sum >= MIN_AREA_MM2) {
                out[i] = hmin + (hmax - hmin) * double(l) / double(LEVELS - 1);
                break;
            }
        }
    }
    return out;
}

// In-between heights for going from `from` to `to`: at least MIN_STEPS, more if one step would exceed MAX_STEP_MM.
inline std::vector<double> step_heights(double from, double to)
{
    const int n = std::max(MIN_STEPS, int(std::ceil(std::abs(to - from) / MAX_STEP_MM - 1e-9)) - 1);
    std::vector<double> out;
    for (int i = 1; i <= n; ++i)
        out.push_back(from + (to - from) * double(i) / double(n + 1));
    return out;
}

// Plans the actual layers: [z_bottom, height] pairs from z = start up to `height`, following the per-bin targets.
inline std::vector<std::pair<double, double>> plan_layers(const std::vector<double> &bins, double start, double height, double hmin, double hmax)
{
    const int nbins = int(bins.size());
    auto bin_of = [nbins](double z) { return std::clamp(int(std::floor(z / BIN_MM + 1e-9)), 0, nbins - 1); };
    // thinnest target over [z0, z1)
    auto min_t = [&](double z0, double z1) {
        double m = hmax;
        for (int b = bin_of(z0), e = bin_of(std::max(z0, z1 - 1e-9)); b <= e; ++b)
            m = std::min(m, bins[b]);
        return std::clamp(m, hmin, hmax);
    };
    auto sum = [](const std::vector<double> &v) { double s = 0.; for (double x : v) s += x; return s; };

    std::vector<std::pair<double, double>> layers;
    std::deque<double> queue;   // in-between layers still to print
    double z = start, h = hmax; // h = height we are at (or heading to once the queue is empty)
    while (z < height - 1e-6) {
        double hl;
        if (!queue.empty()) {
            hl = queue.front();
            queue.pop_front();
        } else {
            // Step down: find the first Z above that needs thinner layers than h.
            int    b_r = -1;
            for (int b = bin_of(z); b < nbins; ++b)
                if (std::clamp(bins[b], hmin, hmax) < h - 1e-6) { b_r = b; break; }
            bool started = false;
            if (b_r >= 0) {
                const double z_r    = double(b_r) * BIN_MM;
                const double target = std::clamp(bins[b_r], hmin, hmax);
                const std::vector<double> steps = step_heights(h, target);
                // start so the last in-between layer ends at or before z_r; if there's no room, start now
                if (z + h > z_r - sum(steps) - 1e-9) {
                    queue.assign(steps.begin(), steps.end());
                    h = target;
                    hl = queue.front();
                    queue.pop_front();
                    started = true;
                }
            }
            if (!started) {
                // Step up after the overhang: the highest height the next layers can use, reached in steps.
                double up = hmax;
                for (int it = 0; it < 8 && up > h + 1e-6; ++it) {
                    const double span = sum(step_heights(h, up)) + up;
                    const double lim  = min_t(z, z + span);
                    if (lim >= up - 1e-6) break;
                    up = lim;
                }
                if (up > h + 1e-6) {
                    const std::vector<double> steps = step_heights(h, up);
                    queue.assign(steps.begin(), steps.end());
                    h  = up;
                    hl = queue.front();
                    queue.pop_front();
                } else
                    hl = std::min(h, min_t(z, z + h)); // stay (never thicker than the model allows here)
            }
        }
        hl = std::clamp(hl, hmin, hmax);
        layers.emplace_back(z, hl);
        z += hl;
    }
    return layers;
}

// Layer height profile in Orca's [z0, h0, z1, h1, ...] format: each planned layer is a flat step, so Orca prints
// exactly the planned heights. Empty when no layer needs thinning.
inline std::vector<coordf_t> make_profile(const SlicingParameters &sp, const std::vector<Mesh> &meshes, double hmin, double hmax)
{
    std::vector<coordf_t> profile;
    const double height = sp.object_print_z_uncompensated_height();
    if (!(hmax > hmin + 1e-6) || height <= 0.)
        return profile;
    const double z_scale = sp.object_shrinkage_compensation_z > 0. ? sp.object_shrinkage_compensation_z : 1.;
    const std::vector<double> bins = bin_targets(meshes, height, z_scale, hmin, hmax);
    if (std::all_of(bins.begin(), bins.end(), [hmax](double h) { return h >= hmax - 1e-6; }))
        return profile;

    constexpr double EPS = 1e-4;
    double start = 0.;
    if (sp.first_object_layer_height_fixed()) {
        start = sp.first_object_layer_height;
        profile.insert(profile.end(), { 0., start, start - EPS, start });
    }
    for (const auto &[z, h] : plan_layers(bins, start, height, hmin, hmax)) {
        const double top = std::min(height, z + h);
        if (top - EPS > z)
            profile.insert(profile.end(), { z, h, top - EPS, h });
    }
    const double h_last = profile.empty() ? hmax : profile.back();
    if (profile.empty() || profile[profile.size() - 2] < height)
        profile.insert(profile.end(), { height, h_last });
    return profile;
}

} // namespace unify_overhang_layers
} // namespace Slic3r

#endif
