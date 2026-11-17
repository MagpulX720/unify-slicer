#ifndef slic3r_UnifyOverhangLayers_hpp_
#define slic3r_UnifyOverhangLayers_hpp_

// Unify Slicer: auto adaptive layer height for overhangs only (issue #7).
// Builds a layer height profile that stays at the process layer height everywhere except in the Z bands
// where the model has overhangs. There the layers get thinner as the overhang gets steeper, down to a
// user minimum that never goes below a hard-coded safe floor. Flat ceilings / bridges and tiny overhangs
// are ignored, and the height ramps in and out over a few layers.

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
constexpr double BRIDGE_DEG      = 80.0; // flatter than this = bridge / ceiling: ignored
constexpr double RAMP_LAYERS     = 3.0;  // layers to ramp in and out
constexpr double MIN_AREA_MM2    = 4.0;  // overhang area needed inside the window to count
constexpr double WINDOW_MM       = 0.5;  // +- window for the area test
constexpr double FLOOR_NOZZLE    = 0.20; // safe floor = 20 % of the nozzle diameter ...
constexpr double FLOOR_ABS_MM    = 0.04; // ... and never below this
constexpr double BIN_MM          = 0.02; // Z resolution of the analysis
constexpr int    LEVELS          = 24;   // quantised target heights

// Safe minimum layer height: the larger of the printer's min layer height and 20 % of the nozzle.
inline double safe_floor(double printer_min_layer_height, double nozzle_diameter)
{
    return std::max({ printer_min_layer_height, FLOOR_NOZZLE * nozzle_diameter, FLOOR_ABS_MM });
}

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
    // ramp in / out: limit how fast the height may change along Z
    const double ramp_len = RAMP_LAYERS * 0.5 * (hmin + hmax);
    const double step     = (hmax - hmin) / std::max(ramp_len, 1e-6) * BIN_MM;
    for (int i = 1; i < nbins; ++i)
        out[i] = std::min(out[i], out[i - 1] + step);
    for (int i = nbins - 2; i >= 0; --i)
        out[i] = std::min(out[i], out[i + 1] + step);
    return out;
}

// Layer height profile in Orca's [z0, h0, z1, h1, ...] format. Empty when no layer needs thinning.
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

    auto push = [&profile](double z, double h) {
        if (profile.size() >= 2 && std::abs(profile[profile.size() - 2] - z) < 1e-9 && std::abs(profile.back() - h) < 1e-9)
            return;
        // merge a third point of the same height
        if (profile.size() >= 4 && std::abs(profile.back() - h) < 1e-9 && std::abs(profile[profile.size() - 3] - h) < 1e-9) {
            profile[profile.size() - 2] = z;
            return;
        }
        profile.push_back(z);
        profile.push_back(h);
    };
    double z = 0.;
    if (sp.first_object_layer_height_fixed()) {
        push(0., sp.first_object_layer_height);
        push(sp.first_object_layer_height, sp.first_object_layer_height);
        z = sp.first_object_layer_height;
    }
    const int nbins = int(bins.size());
    for (int i = 0; i < nbins; ++i) {
        const double zc = std::min(height, (double(i) + 0.5) * BIN_MM);
        if (zc <= z + 1e-9)
            continue;
        push(zc, bins[i]);
    }
    push(height, bins.back());
    return profile;
}

} // namespace unify_overhang_layers
} // namespace Slic3r

#endif
