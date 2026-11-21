#include "UnifyResonanceLog.hpp"

#include "GUI_App.hpp"
#include "MainFrame.hpp"
#include "I18N.hpp"
#include "libslic3r/Utils.hpp"

#include <boost/filesystem.hpp>
#include <boost/log/trivial.hpp>
#include <boost/nowide/fstream.hpp>
#include <ctime>
#include <wx/button.h>
#include <wx/dialog.h>
#include <wx/hyperlink.h>
#include <wx/sizer.h>
#include <wx/stattext.h>
#include <wx/utils.h>

namespace Slic3r { namespace GUI {

namespace {

std::string csv_field(const std::string &s)
{
    std::string out = "\"";
    for (char c : s) {
        if (c == '"')
            out += "\"\"";
        else if (c == '\n' || c == '\r')
            out += ' ';
        else
            out += c;
    }
    return out + "\"";
}

void ensure_file(const std::string &path)
{
    if (boost::filesystem::exists(path))
        return;
    boost::nowide::ofstream f(path, std::ios::binary);
    // UTF-8 byte order mark so Excel shows symbols like mm/s² correctly
    f << "\xEF\xBB\xBF" << "Date,Printer,Result,Details\r\n";
}

} // namespace

std::string unify_resonance_csv_path() { return (boost::filesystem::path(data_dir()) / "resonance_log.csv").string(); }

void unify_resonance_csv_append(const std::string &printer, const std::string &entry)
{
    try {
        const std::string path = unify_resonance_csv_path();
        ensure_file(path);
        std::time_t t = std::time(nullptr);
        char        date[32];
        std::strftime(date, sizeof(date), "%Y-%m-%d %H:%M:%S", std::localtime(&t));
        // "OK: X mzv @ 45.0 Hz, ..." -> Result "OK", Details "X mzv @ 45.0 Hz, ..."
        std::string  result = "Note", details = entry;
        const size_t colon  = entry.find(": ");
        if (colon != std::string::npos && colon < 60) {
            result  = entry.substr(0, colon);
            details = entry.substr(colon + 2);
        }
        boost::nowide::ofstream f(path, std::ios::binary | std::ios::app);
        f << csv_field(date) << ',' << csv_field(printer) << ',' << csv_field(result) << ',' << csv_field(details) << "\r\n";
    } catch (const std::exception &e) {
        BOOST_LOG_TRIVIAL(warning) << "Unify resonance log file: " << e.what();
    }
}

void unify_resonance_show_log_dialog(const wxString &status, const wxString &recent)
{
    wxWindow *parent = wxGetApp().mainframe;
    wxDialog  dlg(parent, wxID_ANY, _L("Resonance check log (Unify)"), wxDefaultPosition, wxDefaultSize, wxDEFAULT_DIALOG_STYLE);
    auto     *top = new wxBoxSizer(wxVERTICAL);

    auto *st = new wxStaticText(&dlg, wxID_ANY, status);
    st->Wrap(dlg.FromDIP(560));
    top->Add(st, 0, wxALL | wxEXPAND, dlg.FromDIP(12));

    auto *head = new wxStaticText(&dlg, wxID_ANY, _L("Last 3 results (newest first):"));
    head->SetFont(head->GetFont().Bold());
    top->Add(head, 0, wxLEFT | wxRIGHT, dlg.FromDIP(12));
    auto *body = new wxStaticText(&dlg, wxID_ANY, recent);
    body->Wrap(dlg.FromDIP(560));
    top->Add(body, 0, wxALL | wxEXPAND, dlg.FromDIP(12));

    const std::string path = unify_resonance_csv_path();
    const bool        have = boost::filesystem::exists(path);
    if (have) {
        auto *link = new wxHyperlinkCtrl(&dlg, wxID_ANY, _L("Open the full log (resonance_log.csv)"), wxString::FromUTF8("file://" + path));
        link->SetToolTip(wxString::FromUTF8(path.c_str()));
        link->Bind(wxEVT_HYPERLINK, [path](wxHyperlinkEvent &) { wxLaunchDefaultApplication(wxString::FromUTF8(path.c_str())); });
        top->Add(link, 0, wxLEFT | wxRIGHT | wxBOTTOM, dlg.FromDIP(12));
    } else {
        top->Add(new wxStaticText(&dlg, wxID_ANY, _L("The full log file is created after the first logged check.")), 0,
                 wxLEFT | wxRIGHT | wxBOTTOM, dlg.FromDIP(12));
    }

    auto *buttons = new wxBoxSizer(wxHORIZONTAL);
    buttons->AddStretchSpacer();
    buttons->Add(new wxButton(&dlg, wxID_OK, _L("OK")), 0);
    top->Add(buttons, 0, wxALL | wxEXPAND, dlg.FromDIP(12));
    dlg.SetSizerAndFit(top);
    dlg.CentreOnParent();
    dlg.ShowModal();
}

}} // namespace Slic3r::GUI
