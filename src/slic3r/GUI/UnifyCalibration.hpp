#ifndef slic3r_UnifyCalibration_hpp_
#define slic3r_UnifyCalibration_hpp_

// Unify Slicer: calibration tests that are not part of Orca / Snapmaker Orca.
//
// Wall direction test (issue #4): six identical 20 x 20 x 30 mm towers with a
// 10 mm through-hole, a 45 degree overhang ledge and a front tab carrying 1-6
// dots. Each tower gets its own per-object wall direction settings:
//   1 Auto                         4 Alternate every layer, all walls
//   2 Counter-clockwise            5 Alternate every layer, inner walls only
//   3 Clockwise                    6 Alternate every 3 layers, all walls
// The meshes are generated in code (no resource files needed).

#include <array>
#include <string>
#include <vector>

namespace Slic3r { namespace GUI {

class Plater;

// Builds the test plate in a new project. Called from Calibration menu.
void unify_calib_wall_direction(Plater *plater);

namespace unify_walltest {

using Triangle = std::array<std::array<float, 3>, 3>;

constexpr int    VARIANT_COUNT   = 6;
constexpr double TOWER_SIZE      = 20.0; // mm, outer square
constexpr double TOWER_HEIGHT    = 30.0; // mm
constexpr double HOLE_DIAMETER   = 10.0; // mm, through-hole
constexpr double LEDGE_Z0        = 14.0; // mm, bottom of the 45 degree ledge
constexpr double LEDGE_REACH     = 10.0; // mm
constexpr int    ALTERNATE_EVERY = 3;    // layers, variant 6

// Triangles of one tower (variant 1..6 = number of dots), outward-facing, mm.
std::vector<Triangle> make_mesh(int variant);

// Writes a binary STL. Returns false on I/O error.
bool write_binary_stl(const std::string &path, const std::vector<Triangle> &tris, const std::string &label);

// Short name used for the object, e.g. "WallDir 4 - Alternate every layer".
std::string variant_name(int variant);

} // namespace unify_walltest

}} // namespace Slic3r::GUI

#endif
