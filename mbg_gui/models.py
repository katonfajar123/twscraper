"""Qt item models used by the GUI."""

from __future__ import annotations

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class PreviewTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.headers: list[str] = []
        self.rows: list[list[str]] = []

    def set_table(self, headers: list[str], rows: list[list[str]]) -> None:
        self.beginResetModel()
        self.headers = headers
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - Qt API
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - Qt API
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self.rows[index.row()][index.column()]
        if role in {Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole}:
            return value
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and section < len(self.headers):
            return self.headers[section]
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None
