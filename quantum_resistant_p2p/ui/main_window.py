"""
Main window for the post-quantum P2P application.
"""

import logging
import asyncio
import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QTabWidget, QLabel, QStatusBar, QAction, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon

from .peer_list import PeerListWidget
from .messaging_widget import MessagingWidget
from .settings_dialog import SettingsDialog
from .login_dialog import LoginDialog
from ..app import SecureMessaging, SecureLogger
from ..crypto import KeyStorage
from ..networking import P2PNode, NodeDiscovery

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main window for the application."""
    
    # Signal for running async tasks
    async_task = pyqtSignal(object)
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        # Initialize components
        self.key_storage = KeyStorage()
        self.secure_logger = SecureLogger()
        
        # Network components will be initialized after login
        self.node = None
        self.node_discovery = None
        self.secure_messaging = None
        
        # UI initialization
        self.setWindowTitle("Quantum Resistant P2P")
        self.setMinimumSize(800, 600)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        layout = QVBoxLayout(self.central_widget)
        layout.addWidget(QLabel("Logging in..."))
        
        # Connect async signal
        self.async_task.connect(self._run_async_task)
        
        # Show login dialog first
        QTimer.singleShot(100, self._show_login_dialog)
    
    def _show_login_dialog(self):
        """Show the login dialog to unlock key storage."""
        dialog = LoginDialog(self.key_storage, self)
        dialog.login_successful.connect(self._init_after_login)
        
        # If dialog is rejected, exit the application
        if dialog.exec_() == LoginDialog.Rejected:
            sys.exit(0)
    
    def _init_after_login(self):
        """Initialize components after successful login."""
        self._init_network()
        self._init_ui()
        self._start_network()
    
    def _init_network(self):
        """Initialize network components."""
        # Create the P2P node
        self.node = P2PNode()
        # Create node discovery
        self.node_discovery = NodeDiscovery(self.node.node_id, port=self.node.port)
        # Create secure messaging
        self.secure_messaging = SecureMessaging(
            node=self.node,
            key_storage=self.key_storage,
            logger=self.secure_logger
        )
        
        logger.info("Network components initialized")
    
    def _init_ui(self):
        """Initialize the user interface."""
        # Create central widget
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for main layout
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - peer list
        self.peer_list = PeerListWidget(self.node, self.node_discovery)
        splitter.addWidget(self.peer_list)
        
        # Right panel - messaging
        self.messaging = MessagingWidget(self.secure_messaging)
        splitter.addWidget(self.messaging)
        
        # Set initial splitter sizes
        splitter.setSizes([200, 600])
        
        # Set up the status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Status indicators
        self.connection_status = QLabel("Not connected")
        self.encryption_status = QLabel("No encryption")
        self.status_bar.addPermanentWidget(self.connection_status)
        self.status_bar.addPermanentWidget(self.encryption_status)
        
        # Initial status message
        self.status_bar.showMessage("Welcome to Quantum P2P")
        
        # Set up menu bar
        self._setup_menu()
        
        # Set central widget
        self.setCentralWidget(central_widget)
        
        # Connect signals
        self.peer_list.peer_selected.connect(self.messaging.set_current_peer)
        
        logger.info("User interface initialized")
    
    def _setup_menu(self):
        """Set up the menu bar."""
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        
        # Connect to peer action
        connect_action = QAction("Connect to Peer...", self)
        connect_action.triggered.connect(self._show_connect_dialog)
        file_menu.addAction(connect_action)
        
        # Send file action
        send_file_action = QAction("Send File...", self)
        send_file_action.triggered.connect(self._show_send_file_dialog)
        file_menu.addAction(send_file_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Settings menu
        settings_menu = menu_bar.addMenu("Settings")
        
        # Crypto settings action
        crypto_settings_action = QAction("Cryptography Settings...", self)
        crypto_settings_action.triggered.connect(self._show_crypto_settings)
        settings_menu.addAction(crypto_settings_action)
        
        # Security metrics action
        metrics_action = QAction("Security Metrics...", self)
        metrics_action.triggered.connect(self._show_security_metrics)
        settings_menu.addAction(metrics_action)
        
        # View logs action
        logs_action = QAction("View Logs...", self)
        logs_action.triggered.connect(self._show_logs)
        settings_menu.addAction(logs_action)
        
        # Help menu
        help_menu = menu_bar.addMenu("Help")
        
        # About action
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)
    
    def _start_network(self):
        """Start the network components."""
        # Start the network components asynchronously
        asyncio.create_task(self._async_start_network())
    
    async def _async_start_network(self):
        """Asynchronously start the network components."""
        try:
            # Start node discovery
            await self.node_discovery.start()
            
            # Start P2P node
            asyncio.create_task(self.node.start())
            
            # Update UI
            self.connection_status.setText(f"Node ID: {self.node.node_id[:8]}...")
            self.encryption_status.setText(
                f"Crypto: {self.secure_messaging.key_exchange.name.split()[0]}, "
                f"{self.secure_messaging.symmetric.name}, "
                f"{self.secure_messaging.signature.name.split()[0]}"
            )
            
            self.status_bar.showMessage("Network started", 3000)
            
            # Start periodic update of peer list
            asyncio.create_task(self._periodic_peer_update())
            
            logger.info("Network components started")
            
        except Exception as e:
            logger.error(f"Failed to start network: {e}")
            self.status_bar.showMessage(f"Error starting network: {e}", 5000)
    
    async def _periodic_peer_update(self):
        """Periodically update the peer list."""
        while True:
            try:
                # Get discovered nodes
                discovered = self.node_discovery.get_discovered_nodes()
                # Get connected peers
                connected = self.node.get_peers()
                
                # Update the UI
                self.peer_list.update_peers(discovered, connected)
                
                # Wait before next update
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating peer list: {e}")
                await asyncio.sleep(5)
    
    @pyqtSlot(object)
    def _run_async_task(self, coro):
        """Run an asynchronous task in the event loop.
        
        Args:
            coro: The coroutine to run
        """
        asyncio.create_task(coro)
    
    def _show_connect_dialog(self):
        """Show the dialog to connect to a specific peer."""
        pass  # TODO: Implement
    
    def _show_send_file_dialog(self):
        """Show the dialog to send a file to a peer."""
        if not self.messaging.current_peer:
            QMessageBox.warning(self, "Error", "Please select a peer first.")
            return
        
        # Show file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File to Send", str(Path.home())
        )
        
        if file_path:
            # Send the file asynchronously
            self.async_task.emit(
                self.secure_messaging.send_file(self.messaging.current_peer, file_path)
            )
    
    def _show_crypto_settings(self):
        """Show the cryptography settings dialog."""
        dialog = SettingsDialog(self.secure_messaging, self)
        dialog.exec_()
    
    def _show_security_metrics(self):
        """Show the security metrics dialog."""
        pass  # TODO: Implement
    
    def _show_logs(self):
        """Show the logs view."""
        pass  # TODO: Implement
    
    def _show_about_dialog(self):
        """Show the about dialog."""
        QMessageBox.about(
            self,
            "About Quantum P2P",
            "<h2>Quantum P2P</h2>"
            "<p>A secure peer-to-peer application using post-quantum cryptography.</p>"
            "<p>Version: 0.1.0</p>"
            "<p>© 2025 Your Name</p>"
        )
    
    def closeEvent(self, event):
        """Handle the window close event.
        
        Args:
            event: The close event
        """
        # Stop the network components asynchronously
        asyncio.create_task(self._async_stop_network())
        event.accept()
    
    async def _async_stop_network(self):
        """Asynchronously stop the network components."""
        try:
            # Stop node discovery
            if self.node_discovery:
                await self.node_discovery.stop()
            
            # Stop P2P node
            if self.node:
                await self.node.stop()
            
            logger.info("Network components stopped")
            
        except Exception as e:
            logger.error(f"Error stopping network: {e}")
