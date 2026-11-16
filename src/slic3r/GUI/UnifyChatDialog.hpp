#ifndef slic3r_UnifyChatDialog_hpp_
#define slic3r_UnifyChatDialog_hpp_

// Unify Slicer: built-in "Ask Claude" assistant.
// A wxWebView hosts resources/web/unify_chat/index.html. The page asks the
// app for the live slicer context, sends chat requests through the app's own
// HTTPS client (Anthropic Messages API, user's API key) and can apply setting
// changes Claude proposes to the print / filament / printer tabs.

#include <wx/dialog.h>
#include <wx/webview.h>
#include <string>

namespace Slic3r { namespace GUI {

class UnifyChatDialog : public wxDialog
{
public:
    static void show_dialog();
    ~UnifyChatDialog() override;

private:
    UnifyChatDialog();
    void on_script_message(wxWebViewEvent &evt);
    void reply(const std::string &json);
    std::string build_context() const;
    std::string apply_changes(const std::string &changes_json);

    wxWebView *m_browser{nullptr};
    static UnifyChatDialog *s_instance;
};

}} // namespace Slic3r::GUI

#endif
