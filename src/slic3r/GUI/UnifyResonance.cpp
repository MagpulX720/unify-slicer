#include "UnifyResonance.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <regex>

#ifndef UNIFY_RESONANCE_STANDALONE
#include "GUI_App.hpp"
#include "MainFrame.hpp"
#include "I18N.hpp"
#include "libslic3r/AppConfig.hpp"
#include "libslic3r/PresetBundle.hpp"
#include "slic3r/Utils/Http.hpp"

#include "nlohmann/json.hpp"
#include <boost/log/trivial.hpp>
#include <atomic>
#include <ctime>
#include <functional>
#include <thread>
#include <wx/button.h>
#include <wx/checkbox.h>
#include <wx/dialog.h>
#include <wx/msgdlg.h>
#include <wx/sizer.h>
#include <wx/stattext.h>
#include <wx/timer.h>
#include <wx/utils.h>
#include <wx/weakref.h>
#endif

namespace Slic3r { namespace GUI {

namespace unify_res {

static std::string num(const char *f, double a)
{
    char buf[64];
    std::snprintf(buf, sizeof(buf), f, a);
    return buf;
}

CheckResult parse(const std::vector<std::string> &lines)
{
    static const std::regex re_axis(R"(best input shaper parameters for ([xy]) axis)");
    static const std::regex re_fit(R"(Fitted shaper '(\w+)' frequency = ([0-9.]+) Hz \(vibrations = ([0-9.]+)%)");
    static const std::regex re_acc(R"(smoothing with '(\w+)', suggested max_accel <= ([0-9.]+))");
    static const std::regex re_rec(R"(Recommended shaper_type_([xy]) = (\w+), shaper_freq_[xy] = ([0-9.]+) Hz)");
    static const std::regex re_rej(R"(Input shaper ([xy]) frequency out of range, using default: ([0-9.]+) Hz)");
    static const std::regex re_sel(R"(Selected shaper_type_([xy]) = (\w+), shaper_freq_[xy] = ([0-9.]+) Hz)");

    CheckResult r;
    AxisResult *cur = nullptr;
    auto axis = [&r](const std::string &a) { return a == "x" ? &r.x : &r.y; };
    for (const std::string &line : lines) {
        std::smatch m;
        if (std::regex_search(line, m, re_axis)) {
            cur = axis(m[1]);
        } else if (std::regex_search(line, m, re_fit)) {
            if (cur) {
                Fit &f = cur->fits[m[1]];
                f.freq = std::stod(m[2]);
                f.vib  = std::stod(m[3]);
            }
        } else if (std::regex_search(line, m, re_acc)) {
            if (cur)
                cur->fits[m[1]].max_accel = std::stod(m[2]);
        } else if (std::regex_search(line, m, re_rec)) {
            AxisResult *a = axis(m[1]);
            a->has_rec  = true;
            a->rec_type = m[2];
            a->rec_freq = std::stod(m[3]);
        } else if (std::regex_search(line, m, re_rej)) {
            AxisResult *a    = axis(m[1]);
            a->rejected      = true;
            a->fallback_freq = std::stod(m[2]);
        } else if (std::regex_search(line, m, re_sel)) {
            AxisResult *a = axis(m[1]);
            a->has_sel  = true;
            a->sel_type = m[2];
            a->sel_freq = std::stod(m[3]);
        }
    }
    return r;
}

static double median(std::vector<double> v)
{
    std::sort(v.begin(), v.end());
    const size_t n = v.size();
    return n == 0 ? 0. : (n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]));
}

static void eval_axis(const char *name, const AxisResult &a, double s0, double s1, const std::vector<double> &base,
                      double hz_per_sec, Evaluation &e)
{
    const std::string N = name;
    if (!a.has_rec && !a.has_sel) {
        e.summary.push_back(N + ": no result");
        e.warnings.push_back(N + " axis: the check didn't report a result. The check may have failed; the printer kept its saved values.");
        e.abnormal = true;
        return;
    }
    Fit f;
    auto it = a.fits.find(a.rec_type);
    if (it != a.fits.end())
        f = it->second;

    std::string line = N + ": " + a.rec_type + " @ " + num("%.1f", a.rec_freq) + " Hz";
    std::string extra;
    if (f.vib >= 0.)
        extra += "vibrations " + num("%.1f", f.vib) + " %";
    if (f.max_accel >= 0.)
        extra += (extra.empty() ? "" : ", ") + std::string("max accel ") + num("%.0f", f.max_accel) + " mm/s\xC2\xB2";
    if (!extra.empty())
        line += " (" + extra + ")";
    line += ", swept " + num("%.0f", s0) + "-" + num("%.0f", s1) + " Hz @ " + num("%.2f", hz_per_sec) + " Hz/s";
    if (a.has_sel && (a.rejected || std::abs(a.sel_freq - a.rec_freq) > 0.05 || a.sel_type != a.rec_type))
        line += "\n     applied: " + a.sel_type + " @ " + num("%.1f", a.sel_freq) + " Hz" + (a.rejected ? " (printer's saved value)" : "");
    e.summary.push_back(line);

    if (a.rejected) {
        e.warnings.push_back(N + " measured " + num("%.1f", a.rec_freq) + " Hz, but this printer's [input_shaper] range doesn't allow it, so it used its saved " +
                             num("%.1f", a.fallback_freq) + " Hz. Belt tension or the toolhead may have changed since calibration.");
        e.abnormal = true;
    }
    if (a.has_rec && (a.rec_freq <= s0 + EDGE_HZ || a.rec_freq >= s1 - EDGE_HZ)) {
        e.warnings.push_back(N + " axis resonance (" + num("%.1f", a.rec_freq) +
                             " Hz) is at the edge of the test range, so the result may be wrong. Run a full input shaper calibration.");
        e.abnormal = true;
    }
    if (f.vib > MAX_VIBRATION_PCT) {
        e.warnings.push_back(N + " axis still shows " + num("%.1f", f.vib) + " % vibration after shaping. Something may be loose or rattling.");
        e.abnormal = true;
    }
    if (f.max_accel >= 0. && f.max_accel < MIN_MAX_ACCEL) {
        e.warnings.push_back(N + " axis shaping limits acceleration to " + num("%.0f", f.max_accel) +
                             " mm/s\xC2\xB2. Prints may show ringing or run slower.");
        e.abnormal = true;
    }
    if (a.has_rec && int(base.size()) >= BASELINE_MIN) {
        const double med = median(base);
        if (med > 0. && std::abs(a.rec_freq - med) / med * 100. > SHIFT_PCT) {
            e.warnings.push_back(N + " axis resonance moved from " + num("%.1f", med) + " Hz to " + num("%.1f", a.rec_freq) +
                                 " Hz since your recent checks. Belts may have loosened.");
            e.abnormal = true;
        }
    }
}

Evaluation evaluate(const CheckResult &r, const Baseline &b, int sweep_time_s)
{
    Evaluation   e;
    const double t = std::max(1, sweep_time_s);
    eval_axis("X", r.x, X_SWEEP_START, X_SWEEP_END, b.x, (X_SWEEP_END - X_SWEEP_START) / t, e);
    eval_axis("Y", r.y, Y_SWEEP_START, Y_SWEEP_END, b.y, (Y_SWEEP_END - Y_SWEEP_START) / t, e);
    return e;
}

std::string short_summary(const CheckResult &r)
{
    auto one = [](const char *n, const AxisResult &a) {
        if (!a.has_rec && !a.has_sel)
            return std::string(n) + " no result";
        const std::string type = a.has_sel ? a.sel_type : a.rec_type;
        const double      freq = a.has_sel ? a.sel_freq : a.rec_freq;
        return std::string(n) + " " + type + " @ " + num("%.1f", freq) + " Hz";
    };
    return one("X", r.x) + ", " + one("Y", r.y);
}

} // namespace unify_res

#ifndef UNIFY_RESONANCE_STANDALONE

using json = nlohmann::json;

namespace {

const char *CFG_SECTION = "unify_resonance";

std::string base_url(std::string host)
{
    while (!host.empty() && (host.back() == '/' || host.back() == ' '))
        host.pop_back();
    while (!host.empty() && host.front() == ' ')
        host.erase(host.begin());
    if (host.empty())
        return host;
    if (host.find("://") == std::string::npos)
        host = "http://" + host;
    return host;
}

const DynamicPrintConfig *printer_config()
{
    if (wxGetApp().preset_bundle == nullptr)
        return nullptr;
    return &wxGetApp().preset_bundle->printers.get_edited_preset().config;
}

bool cfg_bool(const DynamicPrintConfig *c, const char *key, bool def)
{
    return (c && c->has(key)) ? c->opt_bool(key) : def;
}

std::string cfg_string(const DynamicPrintConfig *c, const char *key)
{
    return (c && c->has(key)) ? c->opt_string(key) : std::string();
}

int cfg_int(const DynamicPrintConfig *c, const char *key, int def)
{
    return (c && c->has(key)) ? c->opt_int(key) : def;
}

json load_json(const std::string &key, json def)
{
    try {
        const std::string s = wxGetApp().app_config->get(CFG_SECTION, key);
        if (!s.empty())
            return json::parse(s);
    } catch (...) {
    }
    return def;
}

void save_json(const std::string &key, const json &j) { wxGetApp().app_config->set(CFG_SECTION, key, j.dump()); }

std::string now_hhmm()
{
    std::time_t t = std::time(nullptr);
    char        buf[32];
    std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M", std::localtime(&t));
    return buf;
}

void add_log(const std::string &entry)
{
    json log = load_json("log", json::array());
    if (!log.is_array())
        log = json::array();
    log.push_back(now_hhmm() + " - " + entry);
    while (int(log.size()) > unify_res::LOG_KEEP)
        log.erase(log.begin());
    save_json("log", log);
    BOOST_LOG_TRIVIAL(info) << "Unify resonance check: " << entry;
}

std::string baseline_key(const std::string &host) { return "baseline_" + host; }

unify_res::Baseline load_baseline(const std::string &host)
{
    unify_res::Baseline b;
    json j = load_json(baseline_key(host), json::object());
    try {
        if (j.contains("x"))
            for (auto &v : j["x"]) b.x.push_back(v.get<double>());
        if (j.contains("y"))
            for (auto &v : j["y"]) b.y.push_back(v.get<double>());
    } catch (...) {
    }
    return b;
}

void save_baseline(const std::string &host, const unify_res::Baseline &b)
{
    json j;
    j["x"] = b.x;
    j["y"] = b.y;
    save_json(baseline_key(host), j);
}

void add_to_baseline(const std::string &host, const unify_res::CheckResult &r, bool reset)
{
    unify_res::Baseline b = reset ? unify_res::Baseline() : load_baseline(host);
    if (r.x.has_rec) b.x.push_back(r.x.rec_freq);
    if (r.y.has_rec) b.y.push_back(r.y.rec_freq);
    while (int(b.x.size()) > unify_res::BASELINE_KEEP) b.x.erase(b.x.begin());
    while (int(b.y.size()) > unify_res::BASELINE_KEEP) b.y.erase(b.y.begin());
    save_baseline(host, b);
}

// POST to Moonraker on a worker thread; `done(ok)` runs on the UI thread.
void post_async(const std::string &url, std::function<void(bool)> done)
{
    std::thread([url, done]() {
        bool ok = false;
        Http::post(url)
            .timeout_connect(3)
            .timeout_max(10)
            .set_post_body(std::string())
            .on_complete([&ok](std::string, unsigned status) { ok = status >= 200 && status < 300; })
            .on_error([](std::string, std::string, unsigned) {})
            .perform_sync();
        if (wxTheApp)
            wxTheApp->CallAfter([done, ok]() { done(ok); });
    }).detach();
}

wxString W(const std::string &s) { return wxString::FromUTF8(s.c_str()); }

class ResonanceDialog : public wxDialog
{
public:
    ResonanceDialog(bool abnormal, const std::string &host_url, const std::string &host_key, const unify_res::CheckResult &res,
                    const unify_res::Evaluation &ev)
        : wxDialog(wxGetApp().mainframe, wxID_ANY,
                   abnormal ? _L("Abnormal resonance detected") : _L("Resonance check OK"), wxDefaultPosition, wxDefaultSize,
                   wxDEFAULT_DIALOG_STYLE | wxSTAY_ON_TOP)
        , m_abnormal(abnormal), m_url(host_url), m_host(host_key), m_res(res)
    {
        auto *top = new wxBoxSizer(wxVERTICAL);

        wxString body = _L("Input shaping used for this print:") + "\n";
        for (const std::string &s : ev.summary) body += "  " + W(s) + "\n";
        if (abnormal) {
            body += "\n" + _L("Warnings:") + "\n";
            for (const std::string &w : ev.warnings) body += W("  \xE2\x80\xA2 " + w) + "\n";
        }
        auto *text = new wxStaticText(this, wxID_ANY, body);
        text->Wrap(FromDIP(560));
        top->Add(text, 0, wxALL | wxEXPAND, FromDIP(12));

        m_status = new wxStaticText(this, wxID_ANY, wxEmptyString);
        top->Add(m_status, 0, wxLEFT | wxRIGHT | wxEXPAND, FromDIP(12));

        auto *buttons = new wxBoxSizer(wxHORIZONTAL);
        if (abnormal) {
            m_reset = new wxCheckBox(this, wxID_ANY, _L("This is normal now (e.g. after maintenance) - reset my baseline"));
            top->Add(m_reset, 0, wxALL, FromDIP(12));
            m_pause    = new wxButton(this, wxID_ANY, _L("Pause"));
            m_cancel   = new wxButton(this, wxID_ANY, _L("Cancel print"));
            m_continue = new wxButton(this, wxID_ANY, wxEmptyString);
            buttons->Add(m_pause, 0, wxRIGHT, FromDIP(8));
            buttons->Add(m_cancel, 0, wxRIGHT, FromDIP(8));
            buttons->AddStretchSpacer();
            buttons->Add(m_continue, 0);
            m_pause->Bind(wxEVT_BUTTON, [this](wxCommandEvent &) { on_pause_or_resume(); });
            m_cancel->Bind(wxEVT_BUTTON, [this](wxCommandEvent &) { on_cancel(); });
            m_continue->Bind(wxEVT_BUTTON, [this](wxCommandEvent &) { finish_continue(false); });
            m_reset->Bind(wxEVT_CHECKBOX, [this](wxCommandEvent &) { stop_countdown(); });
            m_seconds = unify_res::WARN_TIMEOUT_S;
        } else {
            m_continue = new wxButton(this, wxID_OK, wxEmptyString);
            buttons->AddStretchSpacer();
            buttons->Add(m_continue, 0);
            m_continue->Bind(wxEVT_BUTTON, [this](wxCommandEvent &) { close_ok(); });
            m_seconds = unify_res::OK_NOTICE_S;
        }
        top->Add(buttons, 0, wxALL | wxEXPAND, FromDIP(12));
        SetSizerAndFit(top);
        CentreOnParent();

        Bind(wxEVT_CLOSE_WINDOW, [this](wxCloseEvent &) {
            if (m_abnormal) finish_continue(false);
            else close_ok();
        });
        m_timer.SetOwner(this);
        Bind(wxEVT_TIMER, [this](wxTimerEvent &) { on_tick(); });
        update_continue_label();
        m_timer.Start(1000);
    }

private:
    void update_continue_label()
    {
        const wxString base = m_abnormal ? _L("Continue") : _L("OK");
        m_continue->SetLabel(m_counting ? wxString::Format("%s (%d)", base, m_seconds) : base);
        if (m_abnormal && m_counting)
            m_status->SetLabel(wxString::Format(_L("Continuing automatically in %d s..."), m_seconds));
        Layout();
    }

    void stop_countdown()
    {
        m_counting = false;
        m_timer.Stop();
        if (m_abnormal && m_status->GetLabel().StartsWith(_L("Continuing")))
            m_status->SetLabel(wxEmptyString);
        update_continue_label();
    }

    void on_tick()
    {
        if (!m_counting) return;
        if (--m_seconds <= 0) {
            m_counting = false;
            m_timer.Stop();
            if (m_abnormal) {
                add_log("Auto-continued after " + std::to_string(unify_res::WARN_TIMEOUT_S) + " s (no response): " + unify_res::short_summary(m_res));
                m_done = true;
                Destroy();
            } else {
                close_ok();
            }
            return;
        }
        update_continue_label();
    }

    void close_ok()
    {
        if (m_done) return;
        m_done = true;
        m_timer.Stop();
        Destroy();
    }

    void finish_continue(bool)
    {
        if (m_done) return;
        m_done = true;
        m_timer.Stop();
        const bool reset = m_reset && m_reset->GetValue();
        if (reset)
            add_to_baseline(m_host, m_res, true);
        add_log(std::string(reset ? "Continued and reset baseline: " : "Continued (accepted warning): ") + unify_res::short_summary(m_res));
        Destroy();
    }

    void set_error()
    {
        m_status->SetLabel(_L("Couldn't reach the printer - use the printer's screen to pause or cancel."));
        Layout();
        Fit();
    }

    void on_pause_or_resume()
    {
        stop_countdown();
        const bool resume = m_paused;
        m_pause->Disable();
        wxWeakRef<ResonanceDialog> self(this);
        post_async(m_url + (resume ? "/printer/print/resume" : "/printer/print/pause"), [self, resume](bool ok) {
            if (!self) return;
            self->m_pause->Enable();
            if (!ok) { self->set_error(); return; }
            add_log(std::string(resume ? "Resumed" : "Paused") + " after resonance warning: " + unify_res::short_summary(self->m_res));
            if (resume) {
                self->m_done = true;
                self->Destroy();
                return;
            }
            self->m_paused = true;
            self->m_pause->SetLabel(_L("Resume"));
            self->m_status->SetLabel(_L("Print paused. Check the printer, then Resume or Cancel print."));
            self->Layout();
            self->Fit();
        });
    }

    void on_cancel()
    {
        stop_countdown();
        wxMessageDialog confirm(this, _L("Cancel this print? This can't be undone."), _L("Cancel print"), wxYES_NO | wxNO_DEFAULT | wxICON_WARNING);
        if (confirm.ShowModal() != wxID_YES)
            return;
        m_cancel->Disable();
        wxWeakRef<ResonanceDialog> self(this);
        post_async(m_url + "/printer/print/cancel", [self](bool ok) {
            if (!self) return;
            self->m_cancel->Enable();
            if (!ok) { self->set_error(); return; }
            add_log("Cancelled print after resonance warning: " + unify_res::short_summary(self->m_res));
            self->m_done = true;
            self->Destroy();
        });
    }

    bool         m_abnormal;
    std::string  m_url, m_host;
    unify_res::CheckResult m_res;
    wxTimer      m_timer;
    int          m_seconds  = 0;
    bool         m_counting = true;
    bool         m_paused   = false;
    bool         m_done     = false;
    wxStaticText *m_status  = nullptr;
    wxCheckBox   *m_reset   = nullptr;
    wxButton     *m_pause = nullptr, *m_cancel = nullptr, *m_continue = nullptr;
};

class ResonanceMonitor : public wxEvtHandler
{
public:
    ResonanceMonitor()
    {
        m_timer.SetOwner(this);
        Bind(wxEVT_TIMER, [this](wxTimerEvent &) { on_timer(); });
        m_timer.Start(3000);
    }

private:
    void on_timer()
    {
        if (m_busy) return;
        const DynamicPrintConfig *pc = printer_config();
        const bool enabled = cfg_bool(pc, "unify_resonance_check", false) &&
                             (cfg_bool(pc, "unify_resonance_warn", true) || cfg_bool(pc, "unify_resonance_show_ok", true));
        const std::string host = cfg_string(pc, "unify_printer_host");
        if (!enabled || base_url(host).empty())
            return;
        if (host != m_host) { // printer changed: start fresh
            m_host       = host;
            m_last_time  = -1.;
            m_collecting = false;
            m_buf.clear();
        }
        m_busy                = true;
        const std::string url = base_url(host) + "/server/gcode_store?count=100";
        std::thread([this, url]() {
            std::string body;
            bool        ok = false;
            Http::get(url)
                .timeout_connect(3)
                .timeout_max(6)
                .on_complete([&](std::string b, unsigned status) { body = std::move(b); ok = status == 200; })
                .on_error([](std::string, std::string, unsigned) {})
                .perform_sync();
            if (wxTheApp)
                wxTheApp->CallAfter([this, ok, body]() { on_poll(ok, body); });
        }).detach();
    }

    void on_poll(bool ok, const std::string &body)
    {
        m_busy = false;
        if (!ok) return;
        json j;
        try { j = json::parse(body); } catch (...) { return; }
        if (!j.contains("result") || !j["result"].contains("gcode_store")) return;
        const json &store = j["result"]["gcode_store"];
        const bool first  = m_last_time < 0.;
        double     newest = m_last_time;
        if (!store.is_array()) return;
        for (const json &item : store) {
            if (!item.is_object() || !item.contains("time") || !item["time"].is_number() || !item.contains("message") || !item["message"].is_string())
                continue;
            const double t = item.value("time", 0.);
            if (t <= m_last_time) continue;
            newest = std::max(newest, t);
            if (first) continue; // don't replay checks that ran before Unify started watching
            const std::string msg = item.value("message", std::string());
            size_t start = 0;
            while (start <= msg.size()) {
                size_t nl = msg.find('\n', start);
                handle_line(msg.substr(start, nl == std::string::npos ? std::string::npos : nl - start));
                if (nl == std::string::npos) break;
                start = nl + 1;
            }
        }
        m_last_time = std::max(newest, first ? 0. : m_last_time);
    }

    void handle_line(const std::string &line)
    {
        if (line.find("UNIFY_FASTCHECK_BEGIN") != std::string::npos) {
            m_collecting = true;
            m_buf.clear();
        } else if (line.find("UNIFY_FASTCHECK_END") != std::string::npos) {
            if (m_collecting) finish();
            m_collecting = false;
        } else if (m_collecting) {
            m_buf.push_back(line);
        }
    }

    void finish()
    {
        const DynamicPrintConfig *pc = printer_config();
        const unify_res::CheckResult res  = unify_res::parse(m_buf);
        const unify_res::Baseline    base = load_baseline(m_host);
        const unify_res::Evaluation  ev   = unify_res::evaluate(res, base, cfg_int(pc, "unify_resonance_check_time", 40));
        m_buf.clear();
        add_log(std::string(ev.abnormal ? "Abnormal: " : "OK: ") + unify_res::short_summary(res));
        if (!ev.abnormal)
            add_to_baseline(m_host, res, false);
        const bool show = ev.abnormal ? cfg_bool(pc, "unify_resonance_warn", true) : cfg_bool(pc, "unify_resonance_show_ok", true);
        if (!show || wxGetApp().mainframe == nullptr)
            return;
        auto *dlg = new ResonanceDialog(ev.abnormal, base_url(m_host), m_host, res, ev);
        dlg->Show();
        dlg->Raise();
        if (ev.abnormal) {
            dlg->RequestUserAttention(wxUSER_ATTENTION_ERROR);
            wxBell();
        }
    }

    wxTimer                  m_timer;
    std::atomic<bool>        m_busy{false};
    std::string              m_host;
    double                   m_last_time  = -1.;
    bool                     m_collecting = false;
    std::vector<std::string> m_buf;
};

} // namespace

void unify_resonance_monitor_start()
{
    static ResonanceMonitor *s_monitor = nullptr; // lives for the whole app session
    if (s_monitor == nullptr)
        s_monitor = new ResonanceMonitor();
}

void unify_resonance_show_log()
{
    json     log = load_json("log", json::array());
    wxString text;
    if (log.is_array())
        for (auto it = log.rbegin(); it != log.rend(); ++it)
            if (it->is_string()) text += W(it->get<std::string>()) + "\n";
    if (text.empty())
        text = _L("No resonance checks have been logged yet. Turn on the resonance fast check and set the printer address in Printer settings > Basic information.");
    wxMessageBox(text, _L("Resonance check log (Unify)"), wxOK | wxICON_INFORMATION, wxGetApp().mainframe);
}

#endif // UNIFY_RESONANCE_STANDALONE

}} // namespace Slic3r::GUI
