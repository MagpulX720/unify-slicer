#include "UnifyBridgeCheck.hpp"

#include "GUI_App.hpp"
#include "I18N.hpp"
#include "IMSlider.hpp"
#include "ImGuiWrapper.hpp"
#include "Plater.hpp"

#include "libslic3r/Layer.hpp"
#include "libslic3r/Print.hpp"
#include "libslic3r/UnifyBridge.hpp"

#include <imgui/imgui.h>
#include <boost/log/trivial.hpp>

#include <algorithm>
#include <cstdio>
#include <string>

namespace Slic3r { namespace GUI {

namespace {

struct Row
{
    std::string     object;
    UnifyBridgeInfo info;
};

bool   g_hidden    = false; // closed by the user for the current slicing result
size_t g_signature = 0;     // changes with every new slicing result
int    g_selected  = -1;

constexpr double MIN_LIST_AREA_MM2 = 2.0; // don't list specks

void jump_to(IMSlider *slider, const std::vector<double> &zs, double z)
{
    if (slider == nullptr || zs.empty() || slider->GetMaxValue() <= slider->GetMinValue())
        return;
    auto it  = std::lower_bound(zs.begin(), zs.end(), z - 1e-4);
    int  idx = it == zs.end() ? int(zs.size()) - 1 : int(it - zs.begin());
    idx      = std::clamp(idx, slider->GetMinValue(), slider->GetMaxValue());
    slider->SetHigherValue(idx); // marks the slider dirty; GLCanvas3D updates the view
}

} // namespace

void unify_bridge_check_show() { g_hidden = false; }

void unify_bridge_check_render(IMSlider *layers_slider, const std::vector<double> &layers_zs)
{
    Plater *plater = wxGetApp().plater();
    if (plater == nullptr)
        return;
    const Print &print = plater->fff_print();

    std::vector<Row> rows;
    size_t           flagged = 0, n_objects = 0, n_done = 0;
    for (const PrintObject *po : print.objects()) {
        ++n_objects;
        // Only read an object's report once its infill preparation has finished (not while re-slicing).
        if (!po->is_step_done(posPrepareInfill))
            continue;
        ++n_done;
        const std::string name = po->model_object() ? po->model_object()->name : std::string();
        for (const UnifyBridgeInfo &b : po->unify_bridge_report) {
            if (b.area_mm2 < MIN_LIST_AREA_MM2)
                continue;
            rows.push_back({ name, b });
            flagged += b.flagged ? 1 : 0;
        }
    }
    {   // log what the window sees whenever it changes (Help > Show Configuration Folder > log)
        static std::string last;
        const std::string now = std::to_string(n_objects) + "/" + std::to_string(n_done) + "/" + std::to_string(rows.size()) + "/" +
                                std::to_string(flagged) + "/" + std::to_string(layers_zs.size()) + "/" + std::to_string(int(g_hidden));
        if (now != last) {
            last = now;
            BOOST_LOG_TRIVIAL(info) << "Unify bridge check: objects/done/rows/flagged/zs/hidden = " << now;
        }
    }
    if (rows.empty())
        return;

    size_t sig = rows.size() * 1000003u + flagged * 7919u + size_t(rows.front().info.print_z * 1000.) + size_t(rows.back().info.span_mm * 100.);
    if (sig != g_signature) {
        g_signature = sig;
        g_hidden    = false;
        g_selected  = -1;
    }
    if (g_hidden)
        return;

    std::stable_sort(rows.begin(), rows.end(), [](const Row &a, const Row &b) {
        if (a.info.flagged != b.info.flagged)
            return a.info.flagged;
        return a.info.print_z < b.info.print_z;
    });

    ImGuiWrapper &imgui = *wxGetApp().imgui();
    const float   em    = imgui.scaled(1.f);
    // Top left, below the plate thumbnail (the legend sits top right).
    ImGui::SetNextWindowPos(ImVec2(1.0f * em, 9.0f * em), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(30.f * em, 16.f * em), ImGuiCond_FirstUseEver);
    // Collapsed when there is nothing to look at, open when something is flagged.
    ImGui::SetNextWindowCollapsed(flagged == 0, ImGuiCond_Appearing);

    char title[160];
    if (flagged > 0)
        std::snprintf(title, sizeof(title), "%s (%zu to check)###unify_bridge_check", _u8L("Bridge check").c_str(), flagged);
    else
        std::snprintf(title, sizeof(title), "%s (%zu)###unify_bridge_check", _u8L("Bridge check").c_str(), rows.size());

    bool open = true;
    if (ImGui::Begin(title, &open, ImGuiWindowFlags_None)) {
        if (flagged > 0) {
            std::string msg = _u8L("Longer than %1% mm or not anchored at both ends are listed first. Click a bridge to show its layer.");
            const std::string span = std::to_string(int(unify_bridge::WARN_SPAN_MM));
            if (auto p = msg.find("%1%"); p != std::string::npos)
                msg.replace(p, 3, span);
            ImGui::TextWrapped("%s", msg.c_str());
        } else
            ImGui::TextWrapped("%s", _u8L("All bridges are anchored and short. Click a bridge to show its layer.").c_str());

        const ImGuiTableFlags tflags = ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY | ImGuiTableFlags_BordersInnerV | ImGuiTableFlags_SizingFixedFit;
        if (ImGui::BeginTable("unify_bridges", 5, tflags, ImVec2(0.f, 0.f))) {
            ImGui::TableSetupScrollFreeze(0, 1);
            ImGui::TableSetupColumn(_u8L("Z (mm)").c_str());
            ImGui::TableSetupColumn(_u8L("Direction").c_str());
            ImGui::TableSetupColumn(_u8L("Longest span").c_str());
            ImGui::TableSetupColumn(_u8L("Anchored").c_str());
            ImGui::TableSetupColumn(_u8L("Object").c_str(), ImGuiTableColumnFlags_WidthStretch);
            ImGui::TableHeadersRow();
            const int max_rows = 500;
            for (int i = 0; i < int(rows.size()) && i < max_rows; ++i) {
                const UnifyBridgeInfo &b = rows[i].info;
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                char z[32];
                std::snprintf(z, sizeof(z), "%.2f##ub%d", b.print_z, i);
                if (b.flagged)
                    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(1.0f, 0.62f, 0.25f, 1.0f));
                if (ImGui::Selectable(z, g_selected == i, ImGuiSelectableFlags_SpanAllColumns)) {
                    g_selected = i;
                    jump_to(layers_slider, layers_zs, b.print_z);
                }
                ImGui::TableSetColumnIndex(1);
                ImGui::Text("%.0f\xC2\xB0%s", b.angle_deg, b.custom_angle ? " (set)" : "");
                ImGui::TableSetColumnIndex(2);
                ImGui::Text("%.1f mm", b.span_mm);
                ImGui::TableSetColumnIndex(3);
                ImGui::Text("%.0f %%", b.anchored * 100.);
                ImGui::TableSetColumnIndex(4);
                ImGui::TextUnformatted(rows[i].object.c_str());
                if (b.flagged)
                    ImGui::PopStyleColor();
            }
            ImGui::EndTable();
        }
    }
    ImGui::End();
    if (!open)
        g_hidden = true;
}

}} // namespace Slic3r::GUI
