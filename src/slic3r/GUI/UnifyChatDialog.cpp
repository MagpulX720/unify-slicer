#include "UnifyChatDialog.hpp"

#include "GUI_App.hpp"
#include "MainFrame.hpp"
#include "Plater.hpp"
#include "Tab.hpp"
#include "I18N.hpp"
#include "Widgets/WebView.hpp"
#include "slic3r/Utils/Http.hpp"
#include "libslic3r/AppConfig.hpp"
#include "libslic3r/Model.hpp"
#include "libslic3r/PresetBundle.hpp"
#include "libslic3r/Utils.hpp"

#include "nlohmann/json.hpp"
#include <boost/filesystem.hpp>
#include <boost/log/trivial.hpp>
#include <wx/sizer.h>
#include <wx/weakref.h>
#include <algorithm>

namespace Slic3r { namespace GUI {

using json = nlohmann::json;

// dump that never throws on invalid UTF-8 (truncated values, odd HTTP bodies)
static std::string jd(const json &j) { return j.dump(-1, ' ', false, json::error_handler_t::replace); }

UnifyChatDialog *UnifyChatDialog::s_instance = nullptr;

void UnifyChatDialog::show_dialog()
{
    if (s_instance == nullptr)
        s_instance = new UnifyChatDialog();
    s_instance->Show();
    s_instance->Raise();
}

UnifyChatDialog::UnifyChatDialog()
    : wxDialog((wxWindow *) (wxGetApp().mainframe), wxID_ANY, _L("Ask Claude"), wxDefaultPosition, wxDefaultSize,
               wxDEFAULT_DIALOG_STYLE | wxRESIZE_BORDER)
{
    const wxString url = from_u8((boost::filesystem::path(resources_dir()) / "web/unify_chat/index.html").make_preferred().string());
    m_browser = WebView::CreateWebView(this, url);
    if (m_browser == nullptr) {
        BOOST_LOG_TRIVIAL(error) << "UnifyChatDialog: could not create web view";
        return;
    }
    Bind(wxEVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, &UnifyChatDialog::on_script_message, this, m_browser->GetId());

    SetMinSize(FromDIP(wxSize(420, 520)));
    SetSize(FromDIP(wxSize(480, 680)));
    auto *sizer = new wxBoxSizer(wxVERTICAL);
    sizer->Add(m_browser, wxSizerFlags().Expand().Proportion(1));
    SetSizer(sizer);
    CenterOnParent();
    wxGetApp().UpdateDlgDarkUI(this);
}

UnifyChatDialog::~UnifyChatDialog()
{
    if (s_instance == this)
        s_instance = nullptr;
}

void UnifyChatDialog::reply(const std::string &payload)
{
    if (m_browser == nullptr)
        return;
    // payload is JSON text, which is a valid JavaScript literal
    WebView::RunScript(m_browser, wxString::FromUTF8("window.unifyReceive && window.unifyReceive(" + payload + ");"));
}

static void put_config(json &out, const DynamicPrintConfig &cfg, bool skip_long)
{
    for (const std::string &key : cfg.keys()) {
        std::string v;
        try { v = cfg.opt_serialize(key); } catch (...) { continue; }
        if (skip_long && v.size() > 400)
            v = v.substr(0, 400) + "...";
        out[key] = v;
    }
}

std::string UnifyChatDialog::build_context() const
{
    json ctx;
    PresetBundle *pb = wxGetApp().preset_bundle;
    if (pb != nullptr) {
        ctx["printer_preset"]  = pb->printers.get_edited_preset().name;
        ctx["process_preset"]  = pb->prints.get_edited_preset().name;
        json fil = json::array();
        for (const std::string &f : pb->filament_presets) fil.push_back(f);
        ctx["filament_presets"] = fil;
        json p, f, m;
        put_config(p, pb->prints.get_edited_preset().config, true);
        put_config(f, pb->filaments.get_edited_preset().config, true);
        put_config(m, pb->printers.get_edited_preset().config, true);
        ctx["process"]  = p;
        ctx["filament"] = f;
        ctx["printer"]  = m;
        ctx["process_modified"]  = pb->prints.get_edited_preset().is_dirty;
        ctx["filament_modified"] = pb->filaments.get_edited_preset().is_dirty;
    }
    json objs = json::array();
    for (const ModelObject *o : wxGetApp().model().objects) {
        if (o == nullptr || o->instances.empty())
            continue;
        const BoundingBoxf3 bb = o->instance_bounding_box(0);
        const Vec3d sz = bb.size();
        json jo;
        jo["name"] = o->name;
        jo["size_mm"] = json::array({sz.x(), sz.y(), sz.z()});
        jo["parts"] = o->volumes.size();
        jo["instances"] = o->instances.size();
        jo["has_support_paint"] = o->is_fdm_support_painted();
        jo["has_seam_paint"] = o->is_seam_painted();
        jo["has_color_paint"] = o->is_mm_painted();
        objs.push_back(jo);
    }
    ctx["objects"] = objs;
    return jd(ctx);
}

std::string UnifyChatDialog::apply_changes(const std::string &changes_json)
{
    json result = json::object();
    json applied = json::array(), rejected = json::array();
    json changes;
    try { changes = json::parse(changes_json); } catch (...) { return "{\"error\":\"invalid JSON\"}"; }

    const std::pair<const char *, Preset::Type> scopes[] = {{"process", Preset::TYPE_PRINT}, {"print", Preset::TYPE_PRINT}, {"filament", Preset::TYPE_FILAMENT}, {"printer", Preset::TYPE_PRINTER}};
    for (const auto &scope : scopes) {
        const std::string name = scope.first;
        if (!changes.contains(name) || !changes[name].is_object())
            continue;
        Tab *tab = wxGetApp().get_tab(scope.second);
        if (tab == nullptr || tab->get_config() == nullptr)
            continue;
        DynamicPrintConfig cfg = *tab->get_config();
        for (auto it = changes[name].begin(); it != changes[name].end(); ++it) {
            const std::string key = it.key();
            std::string value;
            if (it.value().is_string()) value = it.value().get<std::string>();
            else if (it.value().is_boolean()) value = it.value().get<bool>() ? "1" : "0";
            else value = jd(it.value());
            const ConfigOption *cur = cfg.option(key);
            if (cur == nullptr) { rejected.push_back(key); continue; }
            // A single value for a per-extruder / per-filament vector is applied to every element.
            if (cur->is_vector() && value.find(',') == std::string::npos) {
                const size_t n = std::max<size_t>(1, static_cast<const ConfigOptionVectorBase *>(cur)->size());
                std::string joined;
                for (size_t i = 0; i < n; ++i) joined += (i ? "," : "") + value;
                value = joined;
            }
            try {
                cfg.set_deserialize_strict(key, value);
                applied.push_back(name + "." + key + " = " + value);
            } catch (const std::exception &e) {
                rejected.push_back(key + " (" + e.what() + ")");
            }
        }
        tab->load_config(cfg);
    }
    result["applied"]  = applied;
    result["rejected"] = rejected;
    return jd(result);
}

void UnifyChatDialog::on_script_message(wxWebViewEvent &evt)
{
    json msg;
    try { msg = json::parse(evt.GetString().ToUTF8().data()); } catch (...) { return; }
    if (!msg.is_object())
        return;
    const std::string cmd = msg.value("cmd", std::string());
    const int id = msg.value("id", 0);
    AppConfig *ac = wxGetApp().app_config;

    json out;
    out["id"] = id;
    if (cmd == "get_settings") {
        out["type"] = "settings";
        out["api_key"] = ac->get("unify_chat_api_key");
        out["model"] = ac->get("unify_chat_model");
        reply(jd(out));
    } else if (cmd == "save_settings") {
        ac->set("unify_chat_api_key", msg.value("api_key", std::string()));
        ac->set("unify_chat_model", msg.value("model", std::string()));
        ac->save();
        out["type"] = "saved";
        reply(jd(out));
    } else if (cmd == "get_context") {
        out["type"] = "context";
        out["context"] = build_context();
        reply(jd(out));
    } else if (cmd == "apply") {
        out["type"] = "applied";
        out["result"] = apply_changes(msg.value("changes", std::string("{}")));
        reply(jd(out));
    } else if (cmd == "send") {
        const std::string key  = ac->get("unify_chat_api_key");
        const std::string body = msg.value("body", std::string("{}"));
        if (key.empty()) {
            out["type"] = "error";
            out["message"] = "Add your Anthropic API key first (gear button).";
            reply(jd(out));
            return;
        }
        wxWeakRef<UnifyChatDialog> self(this);
        Http::post("https://api.anthropic.com/v1/messages")
            .header("content-type", "application/json")
            .header("x-api-key", key)
            .header("anthropic-version", "2023-06-01")
            .timeout_max(180)
            .set_post_body(body)
            .on_complete([self, id](std::string resp, unsigned status) {
                wxGetApp().CallAfter([self, id, resp, status]() {
                    if (!self) return;
                    json r;
                    r["id"] = id; r["type"] = "response"; r["status"] = status; r["body"] = resp;
                    self->reply(jd(r));
                });
            })
            .on_error([self, id](std::string resp, std::string error, unsigned status) {
                wxGetApp().CallAfter([self, id, resp, error, status]() {
                    if (!self) return;
                    json r;
                    r["id"] = id; r["type"] = "error"; r["status"] = status; r["message"] = error; r["body"] = resp;
                    self->reply(jd(r));
                });
            })
            .perform();
    }
}

}} // namespace Slic3r::GUI
