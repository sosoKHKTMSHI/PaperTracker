__version__ = "0.1.0"


def _install_qt_compatibility_aliases() -> None:
    """Normalize scoped PySide6 enums before the interface module is imported."""
    try:
        import PySide6.QtWidgets as widgets
    except Exception:
        return

    if not hasattr(widgets.QTableWidget, "SelectRows"):
        class CompatTableWidget(widgets.QTableWidget):
            SelectRows = widgets.QAbstractItemView.SelectionBehavior.SelectRows
        widgets.QTableWidget = CompatTableWidget

    if not hasattr(widgets.QHeaderView, "Stretch") or not hasattr(widgets.QHeaderView, "ResizeToContents"):
        class CompatHeaderView(widgets.QHeaderView):
            Stretch = widgets.QHeaderView.ResizeMode.Stretch
            ResizeToContents = widgets.QHeaderView.ResizeMode.ResizeToContents
        widgets.QHeaderView = CompatHeaderView

    if not hasattr(widgets.QDialogButtonBox, "Save"):
        class CompatDialogButtonBox(widgets.QDialogButtonBox):
            Save = widgets.QDialogButtonBox.StandardButton.Save
            Cancel = widgets.QDialogButtonBox.StandardButton.Cancel
            Yes = widgets.QDialogButtonBox.StandardButton.Yes
        widgets.QDialogButtonBox = CompatDialogButtonBox


_install_qt_compatibility_aliases()
