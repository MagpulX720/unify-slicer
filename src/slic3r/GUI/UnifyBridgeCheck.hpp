#ifndef slic3r_UnifyBridgeCheck_hpp_
#define slic3r_UnifyBridgeCheck_hpp_

// Unify Slicer (issue #3, phase 3): "Bridge check" window in the Preview.
// Lists every external bridge area of the sliced plate with its direction, longest span and whether every
// line is anchored, puts long / unanchored bridges first, and jumps the layer slider to a bridge when its
// row is clicked.

#include <vector>

namespace Slic3r { namespace GUI {

class IMSlider;

// Called from GLCanvas3D::_render_gcode() while ImGui is in a frame.
void unify_bridge_check_render(IMSlider *layers_slider, const std::vector<double> &layers_zs);
// Show the window again after it was closed (View menu).
void unify_bridge_check_show();

}} // namespace Slic3r::GUI

#endif
