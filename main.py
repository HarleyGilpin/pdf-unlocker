import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import ctypes
from ctypes import wintypes
from typing import Optional

from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import PdfReadError
from PyQt6 import QtCore
from PyQt6.QtCore import (
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    pyqtSignal,
    pyqtSlot,
    QUrl
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap, QPdfWriter,
    QDesktopServices,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTextEdit
)

# Color themes
# Glassmorphic Dark Theme
GLASS_THEME = {
    "background": "#0F0F0FB3",  # Deep matte black background with alpha (70%)
    "surface": "rgba(30, 30, 30, 0.60)",  # Glassy semi-transparent surface
    "primary": "#60A5FA",  # Bright accent blue
    "secondary": "rgba(255, 255, 255, 0.1)",
    "text": "#F3F4F6",  # Cool white
    "text-secondary": "#9CA3AF",
    "border": "rgba(255, 255, 255, 0.08)",  # Subtle glass border
    "hover": "rgba(255, 255, 255, 0.1)",
    "success": "#34D399",
    "warning": "#FBBF24",
    "error": "#F87171",
}


def resource_path(relative_path: str) -> str:
    """ Get the absolute path to a resource, compatible with PyInstaller and development mode """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))  # Use _MEIPASS if frozen
    return os.path.join(base_path, relative_path)





@dataclass
class PDFFile:
    """Data class to store PDF file information."""
    path: str
    encrypted: bool = False
    password: Optional[str] = None
    status: str = "pending"  # pending, processing, success, error
    error_message: Optional[str] = None


class WorkerSignals(QObject):
    """Signals for worker thread communication."""
    finished = pyqtSignal(str, bool, str)
    progress = pyqtSignal(str, int)
    error = pyqtSignal(str, str)


class PDFProcessWorker(QRunnable):
    """Worker thread for processing PDFs."""

    def __init__(self, pdf_file: PDFFile, output_path: str, overwrite: bool):
        super().__init__()
        self.pdf_file = pdf_file
        self.output_path = output_path
        self.overwrite = overwrite
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        input_path = self.pdf_file.path
        file_name = os.path.basename(input_path)
        output_file = os.path.join(self.output_path, "unlocked_" + file_name)

        try:
            if os.path.exists(output_file) and not self.overwrite:
                self.signals.error.emit(input_path, "File already exists")
                return

            self.signals.progress.emit(input_path, 10)

            with open(input_path, "rb") as f:
                reader = PdfReader(f)
                self.signals.progress.emit(input_path, 30)

                if reader.is_encrypted:
                    unlocked = False
                    if self.pdf_file.password:
                        if reader.decrypt(self.pdf_file.password) > 0:
                            unlocked = True
                    if not unlocked and reader.decrypt("") > 0:
                        unlocked = True

                    if not unlocked:
                        self.signals.error.emit(input_path, "Could not unlock file")
                        create_placeholder_pdf(output_file)
                        return

                self.signals.progress.emit(input_path, 50)
                writer = PdfWriter()
                total_pages = len(reader.pages)

                for i, page in enumerate(reader.pages):
                    writer.add_page(page)
                    progress = 50 + int((i / total_pages) * 40)
                    self.signals.progress.emit(input_path, progress)

                with open(output_file, "wb") as out_file:
                    writer.write(out_file)

                self.signals.progress.emit(input_path, 100)
                self.signals.finished.emit(input_path, True, "")

        except Exception as e:
            self.signals.error.emit(input_path, str(e))


def create_placeholder_pdf(output_path):
    """Create a placeholder PDF for files that couldn't be unlocked."""
    pdf_writer = QPdfWriter(output_path)
    painter = QPainter()
    painter.begin(pdf_writer)
    painter.setFont(QFont("Arial", 12))
    painter.setPen(QColor(GLASS_THEME["text"]))
    rect = painter.viewport()
    painter.drawText(
        rect,
        Qt.AlignmentFlag.AlignLeft,
        "This PDF was encrypted and couldn't be unlocked due to missing or incorrect password.",
    )
    painter.end()


def get_stylesheet(theme):
    """Generate stylesheet from theme colors."""
    return f"""
    QWidget {{
        color: {theme['text']};
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        font-size: 14px;
    }}
    QDialog, QMessageBox, QFileDialog {{
        background-color: {theme['background']};
    }}
    QLabel {{
        background-color: transparent;
        border: none;
    }}
    QPushButton {{
        background-color: {theme['surface']};
        border: 1px solid {theme['border']};
        border-radius: 8px;
        padding: 12px 24px;
        min-width: 120px;
        font-weight: 600;
        background-origin: border-box;
    }}
    QPushButton:hover {{
        background-color: {theme['hover']};
        border-color: {theme['primary']};
    }}
    QPushButton:pressed {{
        background-color: {theme['primary']};
        color: #000000;
        border-color: {theme['primary']};
    }}
    QListWidget {{
        background-color: transparent;
        border: none;
        outline: none;
        padding: 8px;
    }}
    QListWidget::item {{
        background-color: {theme['surface']};
        border-radius: 12px;
        padding: 0px;
        margin-bottom: 8px;
        border: 1px solid {theme['border']};
    }}
    QListWidget::item:hover {{
        background-color: {theme['hover']};
        border: 1px solid {theme['primary']};
    }}
    QListWidget::item:selected {{
        background-color: {theme['secondary']};
        border: 1px solid {theme['primary']};
    }}
    QCheckBox {{
        spacing: 8px;
        background-color: transparent;
        color: {theme['text-secondary']};
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid {theme['border']};
        border-radius: 6px;
        background-color: {theme['surface']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {theme['primary']};
        border-color: {theme['primary']};
        image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>');
    }}
    QLineEdit {{
        background-color: {theme['surface']};
        border: 1px solid {theme['border']};
        border-radius: 8px;
        padding: 12px;
        selection-background-color: {theme['primary']};
        selection-color: black;
    }}
    QLineEdit:focus {{
        border: 1px solid {theme['primary']};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {theme['secondary']};
        min-height: 20px;
        border-radius: 4px;
        margin: 0px 1px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {theme['hover']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QProgressBar {{
        border: none;
        border-radius: 4px;
        background-color: {theme['secondary']};
        text-align: center;
        height: 6px;
    }}
    QProgressBar::chunk {{
        background-color: {theme['primary']};
        border-radius: 4px;
    }}
    QMessageBox QLabel, QDialog QLabel {{
        color: {theme['text']};
        background: transparent;
    }}
    QDialogButtonBox QPushButton {{
        background-color: {theme['surface']};
        border: 1px solid {theme['border']};
        border-radius: 6px;
        padding: 8px 16px;
        min-width: 80px;
    }}"""


class WindowsBlurEffect:
    """Apply Windows DWM blur effect (Acrylic/Mica)."""
    
    def __init__(self):
        self.dwmapi = ctypes.windll.dwmapi
        self.user32 = ctypes.windll.user32
        
    def apply_blur(self, hwnd):
        """Enable Acrylic blur for the given window handle."""
        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_int),
                ("AnimationId", ctypes.c_int)
            ]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.POINTER(ACCENT_POLICY)),
                ("SizeOfData", ctypes.c_int)
            ]

        # Accent State: 3 = ACCENT_ENABLE_BLURBEHIND, 4 = ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent = ACCENT_POLICY()
        accent.AccentState = 4  # Acrylic
        accent.GradientColor = 0x01000000  # Transparent
        
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        
        self.user32.SetWindowCompositionAttribute(
            wintypes.HWND(int(hwnd)), 
            ctypes.pointer(data)
        )


class WindowControlButton(QPushButton):
    """Custom window control button (Close/Minimize) with anti-aliasing."""
    
    def __init__(self, btn_type, parent=None, theme=None):
        super().__init__(parent)
        self.btn_type = btn_type  # 'close' or 'minimize'
        self.theme = theme
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hovered = False
        
    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background on hover
        if self.hovered:
            color = self.theme['error'] if self.btn_type == 'close' else self.theme['hover']
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), 17, 17)
            
        # Draw Icon
        icon_color = QColor(self.theme['text'])
        # For close button on hover, white text usually looks better on red
        if self.hovered and self.btn_type == 'close':
             icon_color = Qt.GlobalColor.white
             
        pen = QPen(icon_color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        center = self.rect().center()
        if self.btn_type == 'close':
            offset = 5
            painter.drawLine(center.x() - offset, center.y() - offset, 
                             center.x() + offset, center.y() + offset)
            painter.drawLine(center.x() + offset, center.y() - offset, 
                             center.x() - offset, center.y() + offset)
        elif self.btn_type == 'minimize':
            painter.drawLine(center.x() - 5, center.y(), 
                             center.x() + 5, center.y())


class ErrorDialog(QDialog):
    """Dialog to display processing errors."""

    def __init__(self, errors, log_path, parent=None):
        super().__init__(parent)
        self.log_path = log_path
        self.setWindowTitle("Processing Errors")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText("\n".join(errors))
        layout.addWidget(self.text_edit)

        btn_box = QDialogButtonBox()
        self.open_btn = btn_box.addButton("Open Log File", QDialogButtonBox.ButtonRole.ActionRole)
        self.close_btn = btn_box.addButton(QDialogButtonBox.StandardButton.Close)
        self.open_btn.clicked.connect(self.open_log_file)
        layout.addWidget(btn_box)

        self.setStyleSheet(get_stylesheet(parent.theme if parent else GLASS_THEME))

    def open_log_file(self):
        if self.log_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_path)))


class PasswordDialog(QDialog):
    """Dialog for entering PDF passwords."""

    def __init__(self, filename, theme, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Password Required - {os.path.basename(filename)}")
        self.setStyleSheet(get_stylesheet(theme))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(f"🔒 Password required for:")
        title.setStyleSheet(f"font-weight: 600; color: {theme['primary']};")
        layout.addWidget(title)

        filename_label = QLabel(os.path.basename(filename))
        filename_label.setStyleSheet(f"font-size: 13px; color: {theme['text-secondary']};")
        layout.addWidget(filename_label)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password...")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme['surface']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                padding: 12px;
                margin-top: 20px;
            }}""")
        layout.addWidget(self.password_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.password_input.setFocus()

    def get_password(self):
        return self.password_input.text()


class PDFDropZone(QWidget):
    """Modern drop zone for PDF files."""

    def __init__(self, parent=None, theme=GLASS_THEME):
        super().__init__(parent)
        self.parent_window = parent
        self.theme = theme
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.icon_label)

        self.text_label = QLabel("\n📁 Drag PDF files here\nor click to select\n")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet(f"color: {theme['text-secondary']}; font-size: 16px;")
        layout.addWidget(self.text_label)

        self.load_icon(resource_path("resources/down_arrow_icon.png"), fallback_text="⬇️")
        self.setStyleSheet(f"""
            PDFDropZone {{
                background-color: {theme['surface']};
                border: 2px dashed {theme['border']};
                border-radius: 12px;
            }}
            PDFDropZone:hover {{
                border-color: {theme['primary']};
                background-color: {theme['hover']};
            }}""")
        self.setMinimumHeight(200)

    def load_icon(self, icon_path, fallback_text=""):
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio)
            self.icon_label.setPixmap(scaled_pixmap)
        else:
            self.icon_label.setText(fallback_text)
            self.icon_label.setStyleSheet("font-size: 32px;")

    def update_text(self, count=0):
        if count > 0:
            self.text_label.setText(
                f"{count} PDF file{'s' if count != 1 else ''} ready\n"
                f"Drag more or click to add")
        else:
            self.text_label.setText("\n📁 Drag PDF files here\nor click to select\n")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.setStyleSheet(f"""
                PDFDropZone {{
                    background-color: {self.theme['hover']};
                    border: 2px dashed {self.theme['primary']};
                    border-radius: 12px;
                }}""")
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(f"""
            PDFDropZone {{
                background-color: {self.theme['surface']};
                border: 2px dashed {self.theme['border']};
                border-radius: 12px;
            }}
            PDFDropZone:hover {{
                border-color: {self.theme['primary']};
                background-color: {self.theme['hover']};
            }}""")

    def dropEvent(self, event):
        self.setStyleSheet(f"""
            PDFDropZone {{
                background-color: {self.theme['surface']};
                border: 2px dashed {self.theme['border']};
                border-radius: 12px;
            }}
            PDFDropZone:hover {{
                border-color: {self.theme['primary']};
                background-color: {self.theme['hover']};
            }}""")
        if self.parent_window:
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'):
                    self.parent_window.handle_pdf_file(url.toLocalFile())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.parent_window:
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select PDF Files", "", "PDF Files (*.pdf);;All Files (*)"
            )
            for file_path in files:
                self.parent_window.handle_pdf_file(file_path)


class FileListItem(QWidget):
    """Custom widget for file list items with status indicator."""
    
    remove_requested = pyqtSignal()

    def __init__(self, pdf_file: PDFFile, theme, parent=None):
        super().__init__(parent)
        self.pdf_file = pdf_file
        self.theme = theme
        
        # Main layout for the card
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # File Icon
        icon_label = QLabel("📄" if not pdf_file.encrypted else "🔒")
        icon_label.setStyleSheet("font-size: 20px; background: transparent;")
        layout.addWidget(icon_label)

        # File Info Container
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.name_label = QLabel(os.path.basename(pdf_file.path))
        self.name_label.setStyleSheet(f"font-weight: 600; font-size: 14px; color: {theme['text']}; background: transparent;")
        info_layout.addWidget(self.name_label)

        dir_path = os.path.dirname(pdf_file.path)
        if len(dir_path) > 40:
            drive = os.path.splitdrive(dir_path)[0]
            last_part = os.path.basename(dir_path)
            short_path = f"{drive}\\...\\{last_part}" if drive else f".../{last_part}"
            display_path = short_path
        else:
            display_path = dir_path

        self.path_label = QLabel(display_path)
        self.path_label.setStyleSheet(f"font-size: 12px; color: {theme['text-secondary']}; background: transparent;")
        self.path_label.setToolTip(dir_path)
        info_layout.addWidget(self.path_label)
        
        layout.addLayout(info_layout, stretch=1)

        # Status Section
        status_layout = QVBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("background: transparent;")
        status_layout.addWidget(self.status_label)

        self.progress_container = QWidget()
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(8)
        self.progress_bar.setFixedWidth(80)
        progress_layout.addWidget(self.progress_bar)
        self.progress_container.setVisible(False)
        status_layout.addWidget(self.progress_container)
        layout.addLayout(status_layout)
        
        # Remove Button
        self.remove_btn = WindowControlButton('close', theme=theme)
        self.remove_btn.setFixedSize(28, 28) # Slightly smaller than window controls
        self.remove_btn.clicked.connect(self.remove_requested.emit)
        layout.addWidget(self.remove_btn)

        self.update_status(pdf_file.status)
        self.setMinimumHeight(50)

    def update_status(self, status, message=""):
        status_map = {
            "pending": ("⏱️", f"color: {self.theme['text-secondary']};"),
            "processing": ("⚙️", f"color: {self.theme['warning']};"),
            "success": ("✅", f"color: {self.theme['success']};"),
            "error": ("❌", f"color: {self.theme['error']};"),
        }
        icon, style = status_map.get(status, ("❓", ""))
        self.status_label.setText(icon)
        self.status_label.setStyleSheet(f"font-size: 16px; {style}")
        self.progress_container.setVisible(status == "processing")
        if status == "error" and message:
            self.setToolTip(message)

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.progress_container.setVisible(True)


class PDFUnlocker(QMainWindow):
    """Main application window for PDF Unlocker."""

    def __init__(self):
        super().__init__()
        self.theme = GLASS_THEME
        self.config_dir = Path.home() / ".pdf_unlocker"
        self.error_log_path = self.config_dir / "errors.txt"
        self.errors = []
        self.pdf_files = {}
        self.thread_pool = QThreadPool()
        self.init_ui()

        if not self.config_dir.exists():
            self.config_dir.mkdir(exist_ok=True)

    def init_ui(self):
        self.setWindowTitle("PDF Unlocker")
        self.setGeometry(100, 100, 900, 700)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(get_stylesheet(self.theme))
        
        # Apply Windows Blur Effect
        if os.name == 'nt':
            try:
                blur = WindowsBlurEffect()
                blur.apply_blur(self.winId())
            except Exception as e:
                print(f"Failed to apply blur: {e}")

        if os.path.exists("resources/app_icon.png"):
            self.setWindowIcon(QIcon("resources/app_icon.png"))

        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        # Apply border radius to central widget content if needed, 
        # but usually main window transparency handles the shape.
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Custom Title Bar
        header_layout = QHBoxLayout()
        header = QLabel("PDF Unlocker")
        header.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {self.theme['primary']}; background: transparent;")
        header_layout.addWidget(header)
        header_layout.addStretch()

        # Window Controls
        self.min_btn = WindowControlButton('minimize', theme=self.theme)
        self.min_btn.clicked.connect(self.showMinimized)
        
        self.close_btn = WindowControlButton('close', theme=self.theme)
        self.close_btn.clicked.connect(self.close)

        header_layout.addWidget(self.min_btn)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.close_btn)
        layout.addLayout(header_layout)

        self.drop_zone = PDFDropZone(self, self.theme)
        layout.addWidget(self.drop_zone)

        self.file_list = QListWidget()
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.file_list)

        options_layout = QHBoxLayout()
        self.overwrite_checkbox = QCheckBox("Overwrite existing files")
        self.overwrite_checkbox.setStyleSheet(f"color: {self.theme['text-secondary']};")
        options_layout.addWidget(self.overwrite_checkbox)
        options_layout.addStretch()

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_all_files)
        options_layout.addWidget(self.clear_btn)
        layout.addLayout(options_layout)

        self.process_btn = QPushButton("Process PDFs")
        self.process_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme['primary']};
                color: white;
                font-weight: 600;
                border: none;
                padding: 14px 28px;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: #0061d1; }}""")
        self.process_btn.setFixedHeight(50)
        self.process_btn.clicked.connect(self.process_files)
        layout.addWidget(self.process_btn)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Use the background color from theme but as QColor
        bg_color = QColor(self.theme['background'])
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        # Draw rounded rect with 20px radius
        painter.drawRoundedRect(self.rect(), 20, 20)

    # Window Dragging Logic
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            if hasattr(self, 'drag_pos'):
                self.move(event.globalPosition().toPoint() - self.drag_pos)
                event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.remove_pdf_file()
        else:
            super().keyPressEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None



    def handle_pdf_file(self, file_path):
        if file_path in self.pdf_files:
            return
        try:
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                encrypted = reader.is_encrypted
                if encrypted and reader.decrypt("") > 0:
                    try:
                        _ = len(reader.pages)
                        self.add_pdf_file(PDFFile(path=file_path, encrypted=True, password=""))
                        return
                    except Exception:
                        pass
                if encrypted:
                    self.handle_encrypted_file(file_path)
                else:
                    self.add_pdf_file(PDFFile(path=file_path))
        except PdfReadError as e:
            if "not been unlocked" in str(e):
                self.handle_encrypted_file(file_path)
            else:
                self.show_error(f"Error reading {os.path.basename(file_path)}:\n{str(e)}")
        except Exception as e:
            self.show_error(f"Failed to process {os.path.basename(file_path)}:\n{str(e)}")

    def handle_encrypted_file(self, file_path):
        dialog = PasswordDialog(file_path, self.theme, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            password = dialog.get_password()
            try:
                with open(file_path, 'rb') as f:
                    reader = PdfReader(f)
                    if reader.decrypt(password) > 0:
                        try:
                            _ = len(reader.pages)
                            self.add_pdf_file(PDFFile(path=file_path, encrypted=True, password=password))
                        except Exception as e:
                            self.show_error(f"Error accessing file: {str(e)}")
                    else:
                        self.show_error(f"Incorrect password for {os.path.basename(file_path)}")
            except Exception as e:
                self.show_error(f"Decryption failed for {os.path.basename(file_path)}:\n{str(e)}")

    def add_pdf_file(self, pdf_file):
        self.pdf_files[pdf_file.path] = pdf_file
        item = QListWidgetItem()
        list_item_widget = FileListItem(pdf_file, self.theme)
        list_item_widget.remove_requested.connect(lambda: self.remove_file_item(item))
        item.setSizeHint(list_item_widget.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, list_item_widget)
        self.drop_zone.update_text(len(self.pdf_files))

    def remove_file_item(self, item):
        widget = self.file_list.itemWidget(item)
        if isinstance(widget, FileListItem) and widget.pdf_file.path in self.pdf_files:
            del self.pdf_files[widget.pdf_file.path]
        row = self.file_list.row(item)
        self.file_list.takeItem(row)
        self.drop_zone.update_text(len(self.pdf_files))

    def show_context_menu(self, position):
        menu = QMenu()
        menu.setStyleSheet(get_stylesheet(self.theme))
        remove_action = menu.addAction("Remove selected")
        clear_action = menu.addAction("Clear all")
        action = menu.exec(self.file_list.mapToGlobal(position))
        if action == remove_action:
            self.remove_selected_files()
        elif action == clear_action:
            self.clear_all_files()

    def remove_selected_files(self):
        for item in self.file_list.selectedItems():
            widget = self.file_list.itemWidget(item)
            if isinstance(widget, FileListItem) and widget.pdf_file.path in self.pdf_files:
                del self.pdf_files[widget.pdf_file.path]
            self.file_list.takeItem(self.file_list.row(item))
        self.drop_zone.update_text(len(self.pdf_files))

    def clear_all_files(self):
        if not self.pdf_files:
            return
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirm Clear")
        msg_box.setText("Remove all files from list?")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setStyleSheet(get_stylesheet(self.theme))
        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            self.pdf_files.clear()
            self.file_list.clear()
            self.drop_zone.update_text(0)

    def process_files(self):
        if not self.pdf_files:
            self.show_warning("No files to process")
            return
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return

        for path, pdf_file in self.pdf_files.items():
            if pdf_file.status == "pending":
                pdf_file.status = "processing"
                for i in range(self.file_list.count()):
                    item = self.file_list.item(i)
                    widget = self.file_list.itemWidget(item)
                    if isinstance(widget, FileListItem) and widget.pdf_file.path == path:
                        widget.update_status("processing")

        for path, pdf_file in self.pdf_files.items():
            if pdf_file.status == "processing":
                worker = PDFProcessWorker(pdf_file, output_dir, self.overwrite_checkbox.isChecked())
                worker.signals.progress.connect(self.update_progress)
                worker.signals.finished.connect(self.process_finished)
                worker.signals.error.connect(self.process_error)
                self.thread_pool.start(worker)

    def update_progress(self, file_path, progress):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            widget = self.file_list.itemWidget(item)
            if isinstance(widget, FileListItem) and widget.pdf_file.path == file_path:
                widget.update_progress(progress)
                break

    def process_finished(self, file_path, success, message):
        if file_path in self.pdf_files:
            pdf_file = self.pdf_files[file_path]
            pdf_file.status = "success" if success else "error"
            if not success:
                pdf_file.error_message = message
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                widget = self.file_list.itemWidget(item)
                if isinstance(widget, FileListItem) and widget.pdf_file.path == file_path:
                    widget.update_status(pdf_file.status, message)
        self.check_all_completed()

    def process_error(self, file_path, error_message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {file_path}: {error_message}\n"
        try:
            with open(self.error_log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Failed to write to error log: {str(e)}")
        self.errors.append(f"• {os.path.basename(file_path)}: {error_message}")

        if file_path in self.pdf_files:
            pdf_file = self.pdf_files[file_path]
            pdf_file.status = "error"
            pdf_file.error_message = error_message
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                widget = self.file_list.itemWidget(item)
                if isinstance(widget, FileListItem) and widget.pdf_file.path == file_path:
                    widget.update_status("error", error_message)
        self.check_all_completed()

    def check_all_completed(self):
        all_done = all(pdf_file.status != "processing" for pdf_file in self.pdf_files.values())
        if all_done:
            results = {
                "success": sum(1 for f in self.pdf_files.values() if f.status == "success"),
                "error": sum(1 for f in self.pdf_files.values() if f.status == "error"),
                "total": len(self.pdf_files)
            }
            self.show_results_dialog(results)
            if self.errors:
                error_dialog = ErrorDialog(self.errors, self.error_log_path, self)
                error_dialog.exec()
                self.errors = []

    def show_results_dialog(self, results):
        dialog = QDialog(self)
        dialog.setWindowTitle("Processing Results")
        dialog.setFixedWidth(400)
        dialog.setStyleSheet(get_stylesheet(self.theme))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Processing Complete")
        title.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {self.theme['primary']};")
        layout.addWidget(title)

        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)

        success_layout = QHBoxLayout()
        success_icon = QLabel("✅")
        success_icon.setStyleSheet(f"color: {self.theme['success']};")
        success_layout.addWidget(success_icon)
        success_layout.addWidget(QLabel(f"Successfully processed: {results['success']}"))
        results_layout.addLayout(success_layout)

        if results["error"] > 0:
            error_layout = QHBoxLayout()
            error_icon = QLabel("❌")
            error_icon.setStyleSheet(f"color: {self.theme['error']};")
            error_layout.addWidget(error_icon)
            error_layout.addWidget(QLabel(f"Errors encountered: {results['error']}"))
            results_layout.addLayout(error_layout)

        results_widget.setStyleSheet(f"background-color: {self.theme['surface']}; border-radius: 8px; padding: 15px;")
        layout.addWidget(results_widget)

        info = QLabel("You can now clear the list or add more files to process.")
        info.setStyleSheet(f"color: {self.theme['text-secondary']};")
        layout.addWidget(info)

        buttons_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear List")
        clear_btn.clicked.connect(lambda: [dialog.accept(), self.clear_all_files()])
        buttons_layout.addWidget(clear_btn)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"background-color: {self.theme['primary']}; color: white;")
        close_btn.clicked.connect(dialog.accept)
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)
        dialog.exec()

    def show_error(self, message):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Error")
        msg_box.setText(message)
        msg_box.setStyleSheet(get_stylesheet(self.theme))
        msg_box.exec()

    def show_warning(self, message):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Warning")
        msg_box.setText(message)
        msg_box.setStyleSheet(get_stylesheet(self.theme))
        msg_box.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PDFUnlocker()
    window.show()
    sys.exit(app.exec())
