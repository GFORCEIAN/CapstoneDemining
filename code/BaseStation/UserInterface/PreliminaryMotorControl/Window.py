import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QSplitter,
    QPushButton
)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Robot Control Panel")
        self.resize(1600, 900)

        # =====================================================
        # SECTION 1 - IMAGE DISPLAY
        # =====================================================
        image_group = QGroupBox("Camera View")
        image_layout = QVBoxLayout()

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap("image.png")
        if not pixmap.isNull():
            self.image_label.setPixmap(
                pixmap.scaled(
                    1200,
                    800,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                    # Qt.KeepAspectRatio,
                    # Qt.SmoothTransformation,
                )
            )
        else:
            self.image_label.setText("No Camera Stream Available")

        image_layout.addWidget(self.image_label)
        image_group.setLayout(image_layout)

        # =====================================================
        # SECTION 2 - CONNECTIONS INFO
        # =====================================================
        connections_group = QGroupBox("Connections Info")
        connections_layout = QVBoxLayout()

        # Arduino
        arduino_group = QGroupBox("Arduino")
        arduino_layout = QGridLayout()

        self.port_combo = QComboBox()
        self.port_combo.addItems(["COM1", "COM2", "COM3"]) # TODO: Auto-generate these

        self.comm_latency = QLabel("__ms")

        arduino_layout.addWidget(QLabel("Port"), 0, 0)
        arduino_layout.addWidget(self.port_combo, 0, 1)

        arduino_layout.addWidget(QLabel("Comm Latency"), 1, 0)
        arduino_layout.addWidget(self.comm_latency, 1, 1)

        arduino_group.setLayout(arduino_layout)

        # Controller
        controller_group = QGroupBox("Controller")
        controller_layout = QGridLayout()

        self.buttons_field = QLabel("[]")
        self.joysticks_field = QLabel("[]")

        controller_layout.addWidget(QLabel("Buttons"), 0, 0)
        controller_layout.addWidget(self.buttons_field, 0, 1)

        controller_layout.addWidget(QLabel("Joysticks"), 1, 0)
        controller_layout.addWidget(self.joysticks_field, 1, 1)

        controller_group.setLayout(controller_layout)

        connections_layout.addWidget(arduino_group)
        connections_layout.addWidget(controller_group)
        connections_layout.addStretch()

        connections_group.setLayout(connections_layout)

        # =====================================================
        # SECTION 3 - MOTOR SPEEDS
        # =====================================================
        motor_group = QGroupBox("Motor Speeds")
        motor_layout = QVBoxLayout()

        self.motor_fields = {}
        self.motor_lables = {}

        for port_name in ["Port 1", "Port 2", "Port 3"]:
            port_group = QGroupBox(port_name)
            port_layout = QGridLayout()

            a_field = QLineEdit()
            b_field = QLineEdit()

            a_label = QLabel("A (Left y)")
            b_label = QLabel("B (Left x)")

            port_layout.addWidget(a_label, 0, 0)
            port_layout.addWidget(a_field, 0, 1)

            port_layout.addWidget(b_label, 1, 0)
            port_layout.addWidget(b_field, 1, 1)

            port_group.setLayout(port_layout)

            self.motor_fields[port_name] = {
                "A": a_field,
                "B": b_field,
            }
            self.motor_lables[port_name] = {
                "A": a_label,
                "B": b_label,
            }

            motor_layout.addWidget(port_group)

        # Adjust lables
        self.motor_lables["Port 2"]["A"].setText("A (Right y)")
        self.motor_lables["Port 2"]["B"].setText("B (Right x)")
        self.motor_lables["Port 3"]["A"].setText("A (Left Trigger)")
        self.motor_lables["Port 3"]["B"].setText("B (Right Trigger)")

        motor_layout.addStretch()
        motor_group.setLayout(motor_layout)

        # =====================================================
        # RIGHT COLUMN
        # Connections Info above Motor Speeds
        # =====================================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        right_layout.addWidget(connections_group)
        right_layout.addWidget(motor_group)

        right_layout.setStretch(0, 1)
        right_layout.setStretch(1, 1)

        # =====================================================
        # TOP AREA
        # =====================================================
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        top_splitter.addWidget(image_group)
        top_splitter.addWidget(right_panel)

        # Wide image area
        top_splitter.setSizes([1100, 350])

        # =====================================================
        # SECTION 4 - INSTRUCTIONS
        # =====================================================
        instructions_group = QGroupBox("Instructions")
        instructions_layout = QHBoxLayout()

        controller_image = QLabel()

        controller_pixmap = QPixmap("code/BaseStation/UserInterface/PreliminaryMotorControl/controller.png")
        if not controller_pixmap.isNull():
            controller_image.setPixmap(
                controller_pixmap.scaled(
                    300,
                    300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                    # Qt.KeepAspectRatio,
                    # Qt.SmoothTransformation,
                )
            )
        else:
            controller_image.setText("Controller picture missing")

        self.instructions_text = QTextEdit()
        self.instructions_text.setReadOnly(True)
        self.instructions_text.setText("""Emergency Stop: Red 'B' Button\n"""+
            """Port 1: Left Joystick\n"""+
            """Port 2: Right Joystick\n"""+
            """Port 3: Triggers at top of controller"""
        )

        instructions_layout.addWidget(controller_image)
        instructions_layout.addWidget(self.instructions_text)

        instructions_group.setLayout(instructions_layout)

        # =====================================================
        # SECTION 5 - CONSOLE
        # =====================================================
        console_group = QGroupBox("Console")
        console_layout = QVBoxLayout()

        # Top row: command input + send button
        command_layout = QHBoxLayout()

        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Enter command...")
        self.send_button = QPushButton("Send")

        command_layout.addWidget(self.console_input)
        command_layout.addWidget(self.send_button)

        # Console Output
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)

        console_layout.addLayout(command_layout)
        console_layout.addWidget(self.console_output)

        console_group.setLayout(console_layout)

        # =====================================================
        # BOTTOM AREA
        # =====================================================
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        bottom_splitter.addWidget(instructions_group)
        bottom_splitter.addWidget(console_group)

        bottom_splitter.setSizes([600, 800])

        # =====================================================
        # MAIN WINDOW LAYOUT
        # =====================================================
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_splitter)

        # Give more room to image section
        main_splitter.setSizes([650, 250])

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(main_splitter)

    def update_controller_connection(self, analogValues, digitalValues):
        self.buttons_field.setText(f"[{digitalValues}]")
        self.joysticks_field.setText(f"[{analogValues}]")

    def update_motor_fields(self, port1:dict, port2:dict, port3:dict):
        self.motor_fields['Port 1']['A'].setText(f"{(port1['A']*100):.2f}%")
        self.motor_fields['Port 1']['B'].setText(f"{(port1['B']*100):.2f}%")
        self.motor_fields['Port 2']['A'].setText(f"{(port2['A']*100):.2f}%")
        self.motor_fields['Port 2']['B'].setText(f"{(port2['B']*100):.2f}%")
        self.motor_fields['Port 3']['A'].setText(f"{(port3['A']*100):.2f}%")
        self.motor_fields['Port 3']['B'].setText(f"{(port3['B']*100):.2f}%")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())