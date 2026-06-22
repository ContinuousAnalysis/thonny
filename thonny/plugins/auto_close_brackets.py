"""
2
Auto-close brackets and quotes for Thonny's editor.

Typing an opening bracket or quote inserts the matching closing character and
parks the cursor between them, with the behaviours that make this tolerable
rather than annoying:

  * type-over   : typing ")" or a quote when the same character is already in
                  front of the cursor steps over it instead of duplicating it
  * pair delete : Backspace inside an empty "()" removes both characters
  * wrap        : with a selection, typing "(" / a quote surrounds it
  * quote-aware : quotes are not auto-closed straight after a word character
                  (so don't, f"", b'' behave) or inside an existing string/comment

Disabled by default so the out-of-the-box beginner experience is unchanged.
The toggle lives in Tools => Options (see general_config_page.py).

How the key handling works (important, and why it differs from a naive version):
Thonny's editor (EnhancedText in tktextext.py) binds <BackSpace> to
perform_smart_backspace, which ALWAYS returns "break". A normally-bound handler
added afterwards would never run for Backspace. So instead of adding bindings
to the widget's own instance tag, we prepend a private bindtag
("AutoCloseBrackets") to each editor text widget. Tk processes bindtags in
order, so our handlers run BEFORE perform_smart_backspace / _on_key_press / the
default insertion. We return "break" only when we actually handle the key, and
return None otherwise so Thonny's normal behaviour proceeds untouched.

For a core contribution this file lives at: thonny/plugins/auto_close_brackets.py
"""

from thonny import get_workbench

OPTION_NAME = "edit.auto_close_brackets"
BINDTAG = "AutoCloseBrackets"

# opener -> closer (brackets only)
BRACKETS = {"(": ")", "[": "]", "{": "}"}
QUOTES = {'"', "'"}
# any opener or quote -> its closer (used for wrapping and pair-deletion)
PAIR = {**BRACKETS, '"': '"', "'": "'"}
CLOSERS = set(BRACKETS.values())

WORD_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")

# Tags Thonny applies to string / comment regions (see base_syntax_themes.py).
STRING_OR_COMMENT_TAGS = {"string", "string3", "open_string", "open_string3", "comment"}


def _enabled():
    try:
        return get_workbench().get_option(OPTION_NAME)
    except Exception:
        return False


def _char_after(text):
    return text.get("insert", "insert+1c")


def _char_before(text):
    return text.get("insert-1c", "insert")


def _has_selection(text):
    return bool(text.tag_ranges("sel"))


def _in_string_or_comment(text):
    return any(t in STRING_OR_COMMENT_TAGS for t in text.tag_names("insert-1c"))


def _wrap_selection(text, opener, closer):
    start = text.index("sel.first")
    selected = text.get(start, "sel.last")
    text.edit_separator()
    text.delete(start, "sel.last")
    text.insert(start, opener + selected + closer)
    # keep the original text selected, now sitting inside the new pair
    inner_end = "%s+%dc" % (start, len(selected) + 1)
    text.tag_remove("sel", "1.0", "end")
    text.tag_add("sel", "%s+1c" % start, inner_end)
    text.mark_set("insert", inner_end)
    return "break"


def _handle_opener(text, opener):
    if _has_selection(text):
        return _wrap_selection(text, opener, BRACKETS[opener])
    text.insert("insert", opener + BRACKETS[opener])
    text.mark_set("insert", "insert-1c")
    return "break"


def _handle_quote(text, quote):
    if _has_selection(text):
        return _wrap_selection(text, quote, quote)
    # step over an identical quote we likely inserted ourselves
    if _char_after(text) == quote:
        text.mark_set("insert", "insert+1c")
        return "break"
    # right after a word char: apostrophe in a word, or a string prefix (f, r, b)
    if _char_before(text) in WORD_CHARS:
        return None
    # avoid a stray quote inside an existing string or comment
    if _in_string_or_comment(text):
        return None
    text.insert("insert", quote + quote)
    text.mark_set("insert", "insert-1c")
    return "break"


def _handle_closer(text, closer):
    # step over an existing closer instead of inserting a duplicate
    if _char_after(text) == closer:
        text.mark_set("insert", "insert+1c")
        return "break"
    return None


def _on_key(event):
    if not _enabled():
        return None

    text = event.widget
    ch = event.char
    if not ch or len(ch) != 1:
        return None

    if ch in BRACKETS:
        return _handle_opener(text, ch)
    if ch in QUOTES:
        return _handle_quote(text, ch)
    if ch in CLOSERS:
        return _handle_closer(text, ch)
    return None


def _on_backspace(event):
    if not _enabled():
        return None

    text = event.widget
    if _has_selection(text):
        return None
    prev = _char_before(text)
    if prev in PAIR and _char_after(text) == PAIR[prev]:
        text.edit_separator()
        text.delete("insert-1c", "insert+1c")
        return "break"
    return None  # let perform_smart_backspace handle the normal case


def _on_editor_text_created(event):
    text = event.text_widget
    # Prepend our private tag so our handlers run before the editor's own
    # instance/class bindings (and so Backspace reaches us before
    # perform_smart_backspace, which always returns "break").
    if BINDTAG not in text.bindtags():
        text.bindtags((BINDTAG,) + text.bindtags())


def load_plugin():
    get_workbench().set_default(OPTION_NAME, False)
    # Class-level bindings on our private tag (registered once).
    get_workbench().bind_class(BINDTAG, "<Key>", _on_key, True)
    get_workbench().bind_class(BINDTAG, "<BackSpace>", _on_backspace, True)
    # Attach the tag to every editor text widget as it is created.
    get_workbench().bind("EditorTextCreated", _on_editor_text_created, True)
