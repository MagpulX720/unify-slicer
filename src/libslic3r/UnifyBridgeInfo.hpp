#ifndef slic3r_UnifyBridgeInfo_hpp_
#define slic3r_UnifyBridgeInfo_hpp_

// Unify Slicer (issue #3, phase 3): what was decided for one external bridge area, kept on the layer region
// so the Preview "Bridge check" window and the long / unanchored bridge warning can show it.

#include <vector>

namespace Slic3r {

struct UnifyBridgeInfo
{
    double print_z        = 0.; // layer top, mm
    double x              = 0.; // centre of the bridge area, mm (object coordinates)
    double y              = 0.;
    double angle_deg      = 0.; // direction of the bridge lines, 0..180, CCW from +X
    double span_mm        = 0.; // longest unsupported line
    double anchored       = 1.; // share of lines with both ends resting on solid below (0..1)
    double area_mm2       = 0.;
    bool   custom_angle   = false; // angle set by the user (bridge_angle), not auto
    bool   flagged        = false; // longer than the warning span or not fully anchored
};

using UnifyBridgeInfos = std::vector<UnifyBridgeInfo>;

} // namespace Slic3r

#endif
