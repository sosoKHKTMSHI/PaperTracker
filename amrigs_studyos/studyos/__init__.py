__version__ = "0.1.0"


def _install_qt_compatibility_aliases() -> None:
    """Keep the UI compatible with both scoped and legacy PySide6 enums."""
    try:
        from PySide6.QtWidgets import QAbstractItemView, QDialogButtonBox, QHeaderView, QTableWidget
    except Exception:
        return

    aliases = [
        (QTableWidget, "SelectRows", QAbstractItemView.SelectionBehavior.SelectRows),
        (QHeaderView, "Stretch", QHeaderView.ResizeMode.Stretch),
        (QHeaderView, "ResizeToContents", QHeaderView.ResizeMode.ResizeToContents),
        (QDialogButtonBox, "Save", QDialogButtonBox.StandardButton.Save),
        (QDialogButtonBox, "Cancel", QDialogButtonBox.StandardButton.Cancel),
        (QDialogButtonBox, "Yes", QDialogButtonBox.StandardButton.Yes),
    ]
    for cls, name, value in aliases:
        if not hasattr(cls, name):
            setattr(cls, name, value)


_install_qt_compatibility_aliases()
