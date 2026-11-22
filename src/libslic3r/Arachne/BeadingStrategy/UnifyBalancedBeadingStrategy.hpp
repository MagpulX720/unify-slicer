// Unify Slicer: "Balanced" beading for the Adaptive wall generator.
// Classic's discipline with Arachne's coverage:
//  - the two beads touching the model surface keep the outer-wall width (like Classic) whenever an inner bead exists;
//  - leftover space is shared equally by the inner beads, and a new inner bead is only added once it can be at least
//    add_threshold x the inner width wide, so no sub-printable hair lines (Arachne can make 0.1 mm lines);
//  - with no room for an inner bead, the two surface beads share the space (at most ~add_threshold/2 wider each).
#pragma once
#include "libslic3r/Arachne/BeadingStrategy/BeadingStrategy.hpp"

namespace Slic3r::Arachne {

class UnifyBalancedBeadingStrategy : public BeadingStrategy
{
public:
    UnifyBalancedBeadingStrategy(coord_t optimal_width_outer, coord_t optimal_width_inner, double add_threshold, double split_middle_threshold,
                                 double minimum_variable_line_ratio, BeadingStrategyPtr parent)
        : BeadingStrategy(*parent), parent(std::move(parent)), wo(optimal_width_outer), wi(optimal_width_inner),
          add(add_threshold), split(split_middle_threshold), min_ratio(minimum_variable_line_ratio)
    { name = "UnifyBalancedBeadingStrategy"; }

    coord_t getOptimalThickness(coord_t n) const override
    { return n <= 0 ? 0 : n == 1 ? wo : 2 * wo + (n - 2) * wi; }

    coord_t getTransitionThickness(coord_t n) const override
    {
        if (n <= 0) return coord_t(min_ratio * wo);
        if (n == 1) return coord_t((1. + split) * wo);
        return 2 * wo + coord_t((double(n - 2) + add) * wi);
    }

    coord_t getOptimalBeadCount(coord_t t) const override
    {
        if (t < coord_t(min_ratio * wo)) return 0;
        if (t < coord_t((1. + split) * wo)) return 1;
        const double inner = std::max(0., double(t - 2 * wo));
        return 2 + coord_t(std::floor(inner / double(wi) + (1. - add)));
    }

    coord_t getTransitioningLength(coord_t n) const override { return parent->getTransitioningLength(n); }
    float   getTransitionAnchorPos(coord_t n) const override { return parent->getTransitionAnchorPos(n); }

    Beading compute(coord_t t, coord_t n) const override
    {
        Beading b; b.total_thickness = t; b.left_over = 0;
        auto push = [&b](coord_t w) {
            b.toolpath_locations.push_back(b.bead_widths.empty() ? w / 2 : b.toolpath_locations.back() + (b.bead_widths.back() + w) / 2);
            b.bead_widths.push_back(w); };
        if (n <= 0) { b.left_over = t; return b; }
        if (n == 1) { push(t); return b; }
        if (n == 2) {
            // Keep both surface beads at the outer-wall width while the gap between them is small enough to close up when
            // the beads squash (gap_ok); only beyond that do they share the extra width.
            const coord_t extra = t > 2 * wo + gap_ok ? t - 2 * wo - gap_ok : 0;
            const coord_t w = t <= 2 * wo ? t / 2 : wo + extra / 2;
            push(w); push(t > 2 * wo ? w : t - w); b.left_over = t - 2 * w; return b; }
        const coord_t k = n - 2, inner = t - 2 * wo;
        if (inner < k * coord_t(0.5 * wi)) {               // inside a transition: fall back to equal widths
            coord_t acc = 0; for (coord_t i = 0; i < n; ++i) { coord_t w = i == n - 1 ? t - acc : t / n; push(w); acc += w; } return b; }
        push(wo);
        coord_t acc = 0; for (coord_t i = 0; i < k; ++i) { coord_t w = i == k - 1 ? inner - acc : inner / k; push(w); acc += w; }
        push(wo);
        return b;
    }

private:
    BeadingStrategyPtr parent;
    coord_t wo, wi;
public:
    coord_t gap_ok = 0;
private:
    double add, split, min_ratio;
};

} // namespace Slic3r::Arachne
