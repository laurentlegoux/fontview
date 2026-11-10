from mpos import Activity, FontManager  
import mpos.ui  
import lvgl as lv  
import os  
  
FULL_RANGES = (  
    (0x20, 0x7F), (0xA0, 0x180), (0x2000, 0x2070),  
    (0x20A0, 0x20D0), (0x2100, 0x2150), (0x2190, 0x2200),  
    (0x2200, 0x2300), (0x2300, 0x2400), (0x2460, 0x2500),  
    (0x25A0, 0x2600), (0x2600, 0x2700), (0x2B00, 0x2C00),  
    (0xF000, 0xF800), (0x1F000, 0x1F100),   # Mahjong, dominoes, playing cards  
    (0x1F300, 0x1F650),   # Misc symbols & pictographs, emoticons  
    (0x1F900, 0x1FA00),   # Supplemental symbols  
)  
PICKER_RANGES = ((0xF000, 0xF800),)  
  
CELL = 48  
TTF_PREVIEW_SIZE = 32  
  
  
class fontview(Activity):  
  
    # ---------- one screen, views swapped in place ----------  
    def onCreate(self):  
        self._screen = lv.obj()  
        self._screen.set_flex_flow(lv.FLEX_FLOW.COLUMN)  
        self._screen.remove_flag(lv.obj.FLAG.SCROLLABLE)  
        self._screen.set_style_pad_all(0, lv.PART.MAIN)  
        self.setContentView(self._screen)  
  
        # Launched by tapping a .ttf in File Manager?  
        path = None  
        intent = self.getIntent()  
        if intent is not None:  
            data = getattr(intent, "data", None)  
            if isinstance(data, str) and data.lower().endswith(".ttf"):  
                path = data  
        if path:  
            self._show_local()      # build local view first so _path_lbl exists  
            self._open_ttf(path)    # then land in the glyph detail view  
        else:  
            self._show_menu()
  
    def onBackPressed(self, screen):  
        if self._view != "menu":  
            self._show_menu()  
            return True  
        return False  
  
    def _show(self, view, builder):  
        self._view = view  
        self._screen.clean()  
        builder()  
  
    def _header(self, title_text, back=True):  
        bar = lv.obj(self._screen)  
        bar.set_width(lv.pct(100))  
        bar.set_height(lv.SIZE_CONTENT)  
        bar.set_flex_flow(lv.FLEX_FLOW.ROW)  
        bar.set_style_border_width(0, lv.PART.MAIN)  
        bar.set_style_pad_all(2, lv.PART.MAIN)  
        if back:  
            b = lv.button(bar)  
            lv.label(b).set_text(lv.SYMBOL.LEFT)  
            b.add_event_cb(lambda e: self._show_menu(), lv.EVENT.CLICKED, None)  
        t = lv.label(bar)  
        t.set_text("  " + title_text)  
        t.set_style_text_font(lv.font_montserrat_14, lv.PART.MAIN)  
        t.set_flex_grow(1)  
        return bar  
  
    def _body(self):  
        b = lv.obj(self._screen)  
        b.set_width(lv.pct(100))  
        b.set_flex_grow(1)  
        b.set_flex_flow(lv.FLEX_FLOW.COLUMN)  
        b.set_scroll_dir(lv.DIR.VER)  
        b.set_style_border_width(0, lv.PART.MAIN)  
        return b  
  
    # ---------- View: menu ----------  
    def _show_menu(self):  
        def build():  
            self._header("Fonts", back=False)  
            lst = lv.list(self._screen)  
            lst.set_width(lv.pct(100))  
            lst.set_flex_grow(1)  
            for label, cb in (  
                (lv.SYMBOL.LIST + "  Installed Fonts", self._show_installed),  
                (lv.SYMBOL.TINT + "  Glyph Picker", self._show_picker),  
                (lv.SYMBOL.DIRECTORY + "  Local Font (.ttf)", self._show_local),  
            ):  
                btn = lst.add_button(None, label)  
                btn.add_event_cb(lambda e, f=cb: f(), lv.EVENT.CLICKED, None)  
        self._show("menu", build)  
  
    # ---------- View: installed fonts ----------  
    def _show_installed(self):  
        def build():  
            self._header("Installed Fonts")  
            lst = lv.list(self._screen)  
            lst.set_width(lv.pct(100))  
            lst.set_flex_grow(1)  
            for info in FontManager.listFonts():  
                btn = lst.add_button(None, info["name"])  
                def cb(e, i=info):  
                    self._show_glyphs(  
                        i["font"], i["name"],  
                        'getFont(size={}, family="{}")'.format(  
                            i["size"], i["family"]))  
                btn.add_event_cb(cb, lv.EVENT.CLICKED, None)  
        self._show("installed", build)  
  
    # ---------- View: glyph detail (shared: installed + local TTF) ----------  
    def _show_glyphs(self, display_font, name, snippet, lookup_font=None):  
        if lookup_font is None:  
            lookup_font = display_font  
        def build():  
            self._header(name)  
            body = self._body()  
            info = lv.label(body)  
            info.set_style_text_font(lv.font_montserrat_12, lv.PART.MAIN)  
            info.set_width(lv.pct(100))  
            glyphs = lv.label(body)  
            glyphs.set_width(lv.pct(99))  
            glyphs.set_long_mode(lv.label.LONG_MODE.WRAP)  
            cps = self._glyphs_of(lookup_font, FULL_RANGES)  
            info.set_text("{} — {} glyphs".format(snippet, len(cps)))  
            text = " ".join(chr(cp) for cp in cps)  
            if lookup_font is not display_font:  
                # composed font: append the emoji drawings, like showfonts  
                text += " " + " ".join(FontManager.getEmojiStrings())  
            glyphs.set_style_text_font(display_font, lv.PART.MAIN)  
            glyphs.set_text(text)  
        self._show("glyphs", build)  
  
    # ---------- View: glyph picker ----------  
    def _show_picker(self):  
        def build():  
            self._header("Glyph Picker")  
            body = self._body()  
            body.set_style_pad_all(4, lv.PART.MAIN)  
  
            emoji_font = FontManager.getFont(size=16, family="Montserrat", emoji=True)  
            base_font = FontManager.getFont(size=16, family="Montserrat")  
  
            self._title(body, "LVGL SYMBOLS")  
            g = self._grid(body)  
            for name in dir(lv.SYMBOL):  
                if not name.startswith("_"):  
                    sym = getattr(lv.SYMBOL, name)  
                    cp = "{:X}".format(ord(sym))  
                    self._cell(g, sym, base_font,  
                        'lv.SYMBOL.{}   U+{}   "\\u{}"'.format(name, cp, cp.lower()))  
  
            self._title(body, "MPOS SYMBOLS")  
            g = self._grid(body)  
            for name in mpos.ui.__all__:  
                val = getattr(mpos.ui, name)  
                if isinstance(val, str) and "SYMBOL" in name:  
                    esc = "".join("\\u{:04x}".format(ord(c)) for c in val)  
                    self._cell(g, val, base_font,  
                        'mpos.ui.{}   "{}"'.format(name, esc))  
  
            self._title(body, "EMOJIS")  
            g = self._grid(body)  
            for e in FontManager.getEmojiStrings():  
                esc = "".join("\\U{:08x}".format(ord(c)) for c in e)  
                self._cell(g, e, emoji_font,  
                    '"{}"  needs getFont(emoji=True)'.format(esc))  
  
            self._title(body, "ICONS PER FONT")  
            for info in FontManager.listFonts():  
                self._title(body, info["name"])  
                g = self._grid(body)  
                desc = 'getFont(size={}, family="{}")'.format(  
                    info["size"], info["family"])  
                for cp in self._glyphs_of(info["base_font"], PICKER_RANGES):  
                    self._cell(g, chr(cp), info["base_font"],  
                               '{}  "\\u{:04x}"'.format(desc, cp))  
  
            self._snippet = lv.label(self._screen)  
            self._snippet.set_text("Tap a glyph for its snippet")  
            self._snippet.set_width(lv.pct(100))  
            self._snippet.set_style_text_font(lv.font_montserrat_12, lv.PART.MAIN)  
        self._show("picker", build)  
  
    # ---------- View: local TTF browser ----------  
    def _show_local(self):  
        def build():  
            self._header("Local Font")  
            hint = lv.label(self._screen)  
            hint.set_width(lv.pct(100))  
            hint.set_long_mode(lv.label.LONG_MODE.WRAP)  
            hint.set_style_text_font(lv.font_montserrat_12, lv.PART.MAIN)  
            hint.set_text('to load a font : font = FontManager.getFont(size=32, ttf="M:/data/fonts/font.ttf)')
            self._path_lbl = lv.label(self._screen)  
            self._path_lbl.set_style_text_font(lv.font_montserrat_12, lv.PART.MAIN)  
            self._fs_list = lv.list(self._screen)  
            self._fs_list.set_width(lv.pct(100))  
            self._fs_list.set_flex_grow(1)  
            self._populate_fs("/")  
        self._show("local", build)  
  
    def _populate_fs(self, path):  
        path = path.rstrip("/") + "/"  
        self._path_lbl.set_text(path)  
        self._fs_list.clean()  
  
        if path != "/":  
            parent = "/".join(path.rstrip("/").split("/")[:-1]) + "/" or "/"  
            btn = self._fs_list.add_button(None, lv.SYMBOL.LEFT + " ..")  
            btn.add_event_cb(lambda e, p=parent: self._populate_fs(p),  
                             lv.EVENT.CLICKED, None)  
        try:  
            items = os.listdir(path.rstrip("/") or "/")  
        except OSError:  
            return  
        dirs, files = [], []  
        for item in items:  
            try:  
                if os.stat(path + item)[0] & 0x4000:  
                    dirs.append(item)  
                elif item.lower().endswith(".ttf"):  
                    files.append(item)  
            except OSError:  
                pass  
        for d in sorted(dirs):  
            btn = self._fs_list.add_button(None, lv.SYMBOL.DIRECTORY + " " + d)  
            btn.add_event_cb(lambda e, p=path + d: self._populate_fs(p),  
                             lv.EVENT.CLICKED, None)  
        for f in sorted(files):  
            btn = self._fs_list.add_button(None, lv.SYMBOL.FILE + " " + f)  
            btn.add_event_cb(lambda e, p=path + f: self._open_ttf(p),  
                             lv.EVENT.CLICKED, None)  
  
    def _open_ttf(self, path):  
        try:  
            self._picked_base = FontManager.getFont(  
                size=TTF_PREVIEW_SIZE, ttf="M:" + path, emoji=False)  
            self._picked_font = FontManager.getFont(  
                size=TTF_PREVIEW_SIZE, ttf="M:" + path, emoji=True)  
        except OSError as err:  
            self._path_lbl.set_text(str(err))  
            return  
        name = path.rstrip("/").split("/")[-1]  
        self._show_glyphs(  
            self._picked_font, name,  
            'getFont(size={}, ttf="M:{}")'.format(TTF_PREVIEW_SIZE, path),  
            lookup_font=self._picked_base)  
  
    # ---------- helpers ----------  
    def _glyphs_of(self, font, ranges):  
        dsc = lv.font_glyph_dsc_t()  
        out = []  
        for start, end in ranges:  
            for cp in range(start, end):  
                if font.get_glyph_dsc(font, dsc, cp, cp):  
                    out.append(cp)  
        return out  
  
    def _cell(self, parent, glyph, font, snippet):  
        c = lv.obj(parent)  
        c.set_size(CELL, CELL)  
        c.set_style_pad_all(0, lv.PART.MAIN)  
        l = lv.label(c)  
        l.set_style_text_font(font, lv.PART.MAIN)  
        l.set_text(glyph)  
        l.center()  
        c.add_event_cb(lambda e, s=snippet: self._snippet.set_text(s),  
                       lv.EVENT.CLICKED, None)  
  
    def _grid(self, parent):  
        g = lv.obj(parent)  
        g.set_width(lv.pct(100))  
        g.set_height(lv.SIZE_CONTENT)  
        g.set_flex_flow(lv.FLEX_FLOW.ROW_WRAP)  
        g.set_style_pad_all(2, lv.PART.MAIN)  
        g.set_style_border_width(0, lv.PART.MAIN)  
        return g  
  
    def _title(self, parent, text):  
        t = lv.label(parent)  
        t.set_text("=== {} ===".format(text))  
        t.set_style_text_font(lv.font_montserrat_14, lv.PART.MAIN)  
        t.set_width(lv.pct(100))