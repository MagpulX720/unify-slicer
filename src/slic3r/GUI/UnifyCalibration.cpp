#include "UnifyCalibration.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>

#ifndef UNIFY_WALLTEST_STANDALONE
#include "GUI_App.hpp"
#include "MainFrame.hpp"
#include "Plater.hpp"
#include "I18N.hpp"
#include "libslic3r/Model.hpp"
#include "libslic3r/PrintConfig.hpp"

#include <boost/filesystem.hpp>
#include <boost/log/trivial.hpp>
#include <wx/msgdlg.h>
#endif

namespace Slic3r { namespace GUI {

namespace unify_walltest {

namespace {

constexpr double PI        = 3.14159265358979323846;
constexpr int    N_RING    = 128;  // hole / square ring segments (multiple of 4)
constexpr int    N_DOT     = 32;   // dot cylinder segments
constexpr double TAB_DEPTH = 10.0, TAB_THICK = 1.2;
constexpr double DOT_D = 2.4, DOT_H = 1.2, DOT_PITCH = 3.2;
constexpr double LEDGE_HALF_WIDTH = 6.0;

struct V3 { double x, y, z; };

struct Mesh
{
    std::vector<V3>                 v;
    std::vector<std::array<int, 3>> f;
    int add(double x, double y, double z) { v.push_back({x, y, z}); return int(v.size()) - 1; }
};

void append(std::vector<Triangle> &out, const Mesh &m)
{
    for (const auto &t : m.f) {
        Triangle tri;
        for (int k = 0; k < 3; ++k) {
            const V3 &p = m.v[t[k]];
            tri[k] = {float(p.x), float(p.y), float(p.z)};
        }
        out.push_back(tri);
    }
}

// Square prism with a round through-hole, one watertight shell.
Mesh tower_with_hole()
{
    Mesh m;
    const double h = TOWER_SIZE / 2, r = HOLE_DIAMETER / 2;
    std::vector<int> so_b(N_RING), so_t(N_RING), ci_b(N_RING), ci_t(N_RING);
    std::vector<std::array<double, 2>> sq(N_RING), ci(N_RING);
    for (int i = 0; i < N_RING; ++i) {
        const double a = PI / 4 + 2 * PI * i / N_RING;
        const double c = std::cos(a), s = std::sin(a);
        const double k = h / std::max(std::abs(c), std::abs(s));
        sq[i] = {k * c, k * s};
        ci[i] = {r * c, r * s};
    }
    for (int i = 0; i < N_RING; ++i) so_b[i] = m.add(sq[i][0], sq[i][1], 0);
    for (int i = 0; i < N_RING; ++i) so_t[i] = m.add(sq[i][0], sq[i][1], TOWER_HEIGHT);
    for (int i = 0; i < N_RING; ++i) ci_b[i] = m.add(ci[i][0], ci[i][1], 0);
    for (int i = 0; i < N_RING; ++i) ci_t[i] = m.add(ci[i][0], ci[i][1], TOWER_HEIGHT);
    for (int i = 0; i < N_RING; ++i) {
        const int j = (i + 1) % N_RING;
        m.f.push_back({so_b[i], so_b[j], so_t[j]}); m.f.push_back({so_b[i], so_t[j], so_t[i]}); // outer wall
        m.f.push_back({ci_b[i], ci_t[j], ci_b[j]}); m.f.push_back({ci_b[i], ci_t[i], ci_t[j]}); // hole wall
        m.f.push_back({ci_t[i], so_t[j], ci_t[j]}); m.f.push_back({ci_t[i], so_t[i], so_t[j]}); // top
        m.f.push_back({ci_b[i], ci_b[j], so_b[j]}); m.f.push_back({ci_b[i], so_b[j], so_b[i]}); // bottom
    }
    return m;
}

// 45 degree overhang ledge on the +X face, overlapping the tower by 1 mm.
Mesh ledge()
{
    Mesh m;
    const double h = TOWER_SIZE / 2;
    const double px[3] = {h - 1.0, h + LEDGE_REACH, h - 1.0};
    const double pz[3] = {LEDGE_Z0, LEDGE_Z0 + LEDGE_REACH, LEDGE_Z0 + LEDGE_REACH};
    for (int i = 0; i < 3; ++i) m.add(px[i], -LEDGE_HALF_WIDTH, pz[i]);
    for (int i = 0; i < 3; ++i) m.add(px[i], LEDGE_HALF_WIDTH, pz[i]);
    m.f.push_back({0, 1, 2});
    m.f.push_back({3, 5, 4});
    for (int i = 0; i < 3; ++i) {
        const int j = (i + 1) % 3;
        m.f.push_back({i, 3 + j, j});
        m.f.push_back({i, 3 + i, 3 + j});
    }
    return m;
}

Mesh box(double x0, double y0, double z0, double x1, double y1, double z1)
{
    Mesh m;
    for (double z : {z0, z1})
        for (double y : {y0, y1})
            for (double x : {x0, x1}) m.add(x, y, z);
    const int F[12][3] = {{0, 2, 3}, {0, 3, 1}, {4, 5, 7}, {4, 7, 6}, {0, 1, 5}, {0, 5, 4},
                          {2, 6, 7}, {2, 7, 3}, {0, 4, 6}, {0, 6, 2}, {1, 3, 7}, {1, 7, 5}};
    for (const auto &t : F) m.f.push_back({t[0], t[1], t[2]});
    return m;
}

Mesh cylinder(double cx, double cy, double z0, double z1, double d)
{
    Mesh m;
    const double r = d / 2;
    m.add(cx, cy, z0);
    m.add(cx, cy, z1);
    for (double z : {z0, z1})
        for (int i = 0; i < N_DOT; ++i) {
            const double a = 2 * PI * i / N_DOT;
            m.add(cx + r * std::cos(a), cy + r * std::sin(a), z);
        }
    for (int i = 0; i < N_DOT; ++i) {
        const int j = (i + 1) % N_DOT;
        const int b0 = 2 + i, b1 = 2 + j, t0 = 2 + N_DOT + i, t1 = 2 + N_DOT + j;
        m.f.push_back({0, b1, b0});
        m.f.push_back({1, t0, t1});
        m.f.push_back({b0, b1, t1});
        m.f.push_back({b0, t1, t0});
    }
    return m;
}

} // namespace

std::vector<Triangle> make_mesh(int variant)
{
    const int k = std::max(1, std::min(VARIANT_COUNT, variant));
    const double h = TOWER_SIZE / 2;
    std::vector<Triangle> out;
    append(out, tower_with_hole());
    append(out, ledge());
    // front tab overlaps the tower by 1 mm so the slicer merges them
    append(out, box(-h, -h - TAB_DEPTH, 0, h, -h + 1.0, TAB_THICK));
    const double y  = -h - TAB_DEPTH / 2;
    const double x0 = -(k - 1) * DOT_PITCH / 2;
    for (int i = 0; i < k; ++i)
        append(out, cylinder(x0 + i * DOT_PITCH, y, TAB_THICK - 0.4, TAB_THICK + DOT_H, DOT_D));
    return out;
}

bool write_binary_stl(const std::string &path, const std::vector<Triangle> &tris, const std::string &label)
{
    std::ofstream f(path, std::ios::binary);
    if (!f) return false;
    char header[80];
    std::memset(header, ' ', sizeof(header));
    std::memcpy(header, label.data(), std::min<size_t>(label.size(), sizeof(header)));
    f.write(header, sizeof(header));
    const uint32_t n = uint32_t(tris.size());
    f.write(reinterpret_cast<const char *>(&n), 4);
    for (const Triangle &t : tris) {
        const float ux = t[1][0] - t[0][0], uy = t[1][1] - t[0][1], uz = t[1][2] - t[0][2];
        const float vx = t[2][0] - t[0][0], vy = t[2][1] - t[0][1], vz = t[2][2] - t[0][2];
        float nrm[3] = {uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx};
        const float len = std::sqrt(nrm[0] * nrm[0] + nrm[1] * nrm[1] + nrm[2] * nrm[2]);
        if (len > 0) for (float &c : nrm) c /= len;
        f.write(reinterpret_cast<const char *>(nrm), 12);
        for (const auto &p : t) f.write(reinterpret_cast<const char *>(p.data()), 12);
        const uint16_t attr = 0;
        f.write(reinterpret_cast<const char *>(&attr), 2);
    }
    return bool(f);
}

std::string variant_name(int variant)
{
    switch (variant) {
    case 1: return "WallDir 1 - Auto";
    case 2: return "WallDir 2 - Counter-clockwise";
    case 3: return "WallDir 3 - Clockwise";
    case 4: return "WallDir 4 - Alternate every layer";
    case 5: return "WallDir 5 - Alternate inner walls";
    case 6: return "WallDir 6 - Alternate every 3 layers";
    default: return "WallDir";
    }
}

} // namespace unify_walltest

#ifndef UNIFY_WALLTEST_STANDALONE

namespace {

// Per-object settings for each tower (uses the Unify wall direction options from issue #4).
void apply_variant(ModelObject *obj, int variant)
{
    auto &cfg = obj->config;
    WallDirection dir = WallDirection::Auto;
    switch (variant) {
    case 2: dir = WallDirection::CounterClockwise; break;
    case 3: dir = WallDirection::Clockwise; break;
    case 4:
    case 5: dir = WallDirection::AlternateEveryLayer; break;
    case 6: dir = WallDirection::AlternateEveryN; break;
    default: break;
    }
    cfg.set_key_value("wall_direction", new ConfigOptionEnum<WallDirection>(dir));
    cfg.set_key_value("overhang_reverse", new ConfigOptionBool(false));
    cfg.set_key_value("wall_direction_start_cw", new ConfigOptionBool(false));
    cfg.set_key_value("wall_direction_outer", new ConfigOptionBool(variant != 5)); // 5 = inner walls only
    cfg.set_key_value("wall_direction_inner", new ConfigOptionBool(true));
    cfg.set_key_value("wall_direction_holes", new ConfigOptionBool(true));
    if (variant == 6)
        cfg.set_key_value("wall_direction_alternate_layers", new ConfigOptionInt(unify_walltest::ALTERNATE_EVERY));
}

} // namespace

void unify_calib_wall_direction(Plater *plater)
{
    using namespace unify_walltest;
    namespace fs = boost::filesystem;
    if (plater == nullptr)
        return;

    plater->new_project(false, false, _L("Wall direction test"));
    wxGetApp().mainframe->select_tab(size_t(MainFrame::tp3DEditor));

    // Write the six towers to a temp folder and load them as separate objects.
    boost::system::error_code ec;
    const fs::path dir = fs::temp_directory_path(ec) / "unify_wall_direction_test";
    fs::create_directories(dir, ec);
    std::vector<std::string> files;
    for (int v = 1; v <= VARIANT_COUNT; ++v) {
        const fs::path p = dir / (variant_name(v) + ".stl");
        if (!write_binary_stl(p.string(), make_mesh(v), variant_name(v))) {
            wxMessageBox(_L("Couldn't create the wall direction test models in the temporary folder."),
                         _L("Wall direction test"), wxOK | wxICON_ERROR, wxGetApp().mainframe);
            return;
        }
        files.push_back(p.string());
    }
    plater->load_files(files, LoadStrategy::LoadModel, false);

    std::vector<size_t> changed;
    auto &objects = plater->model().objects;
    for (size_t i = 0; i < objects.size(); ++i) {
        for (int v = 1; v <= VARIANT_COUNT; ++v) {
            if (objects[i]->name.rfind(variant_name(v), 0) == 0) {
                apply_variant(objects[i], v);
                changed.push_back(i);
                break;
            }
        }
    }
    BOOST_LOG_TRIVIAL(info) << "Unify wall direction test: configured " << changed.size() << " objects";
    if (!changed.empty())
        plater->changed_objects(changed);
    plater->arrange();

    wxMessageBox(_L("Six towers were added. The dots on each tower's front tab tell you which setting it uses:\n\n"
                    "1 dot: Auto\n"
                    "2 dots: Counter-clockwise\n"
                    "3 dots: Clockwise\n"
                    "4 dots: Alternate every layer, all walls\n"
                    "5 dots: Alternate every layer, inner walls only\n"
                    "6 dots: Alternate every 3 layers, all walls\n\n"
                    "After printing, compare twist (look down from the top), outer surface texture, the seam, "
                    "the underside of the overhang ledge, and the hole and outer size with calipers (10 mm / 20 mm)."),
                 _L("Wall direction test"), wxOK | wxICON_INFORMATION, wxGetApp().mainframe);
}

#endif // UNIFY_WALLTEST_STANDALONE

}} // namespace Slic3r::GUI
