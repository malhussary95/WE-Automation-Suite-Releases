def run_on_ui(gui, callback, *args, **kwargs):
    gui.root.after(0, lambda: callback(*args, **kwargs))


def set_progress(gui, value, status):
    def update():
        if hasattr(gui.progress, "set"):
            gui.progress.set(max(0, min(value, 100)) / 100)
        else:
            gui.progress["value"] = value
        gui.status_var.set(status)
        if hasattr(gui, "stat_progress_label") and gui.stat_progress_label:
            gui.stat_progress_label.configure(text=f"{max(0, min(value, 100)):.0f}%")
        if hasattr(gui, "status_color_var"):
            gui.status_color_var.set("success" if value >= 100 else "gray")
        if hasattr(gui, "_update_status_color"):
            gui._update_status_color()
        gui.root.update_idletasks()

    run_on_ui(gui, update)


def reset_ui(gui, reset_progress=True):
    if not hasattr(gui, "reset_ui"):
        return

    def update():
        try:
            gui.reset_ui(reset_progress=reset_progress)
        except TypeError:
            gui.reset_ui()

    run_on_ui(gui, update)


def show_error(gui, title, message):
    def update():
        gui.status_var.set("FAILED")
        if hasattr(gui, "status_color_var"):
            gui.status_color_var.set("error")
        if hasattr(gui, "_update_status_color"):
            gui._update_status_color()
        if hasattr(gui, "reset_ui"):
            try:
                gui.reset_ui(reset_progress=True)
            except TypeError:
                gui.reset_ui()
        gui.messagebox.showerror(title, message)

    run_on_ui(gui, update)


def show_info(gui, title, message):
    def update():
        if hasattr(gui, "status_color_var"):
            gui.status_color_var.set("success")
        if hasattr(gui, "_update_status_color"):
            gui._update_status_color()
        if hasattr(gui, "reset_ui"):
            try:
                gui.reset_ui(reset_progress=False)
            except TypeError:
                gui.reset_ui()
        gui.messagebox.showinfo(title, message)

    run_on_ui(gui, update)
