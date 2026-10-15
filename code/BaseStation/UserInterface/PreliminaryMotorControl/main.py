import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from Window import MainWindow
from Controller import Controller
from RobotInterface import ArduinoInterface


class Application(MainWindow):
    def __init__(self):
        super().__init__()

        # Create controller
        self.controller = Controller()

        # Create Interface with motors
        self.robot_interface = ArduinoInterface()

        # Create update timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_system)
        self.timer.start(15)

    def update_system(self):
        """
        Called every 15 ms.
        """

        self.update_motor_speeds()
        self.update_controller_connection(self.controller.get_all_analog(), self.controller.get_all_digital())

    def closeEvent(self, event):
        """
        Cleanup before exiting.
        """

        self.timer.stop()
        self.controller.disconnect()
        self.robot_interface.disconnect()
        event.accept()

    def update_motor_speeds(self):
        # Calculate motor speeds as proportions
        if self.controller.is_connected():
            port1_speed:dict = {
                "A": self.controller.get_analog_value('left_y'),
                "B": self.controller.get_analog_value('left_x'),
            }
            port2_speed:dict = {
                "A": self.controller.get_analog_value('right_y'),
                "B": self.controller.get_analog_value('right_x'),
            }
            port3_speed:dict = {
                "A": self.controller.get_analog_value('left_trigger'),
                "B": self.controller.get_analog_value('right_trigger'),
            }
        else:
            port1_speed:dict = {
                "A": 0.0,
                "B": 0.0,
            }
            port2_speed:dict = {
                "A": 0.0,
                "B": 0.0,
            }
            port3_speed:dict = {
                "A": 0.0,
                "B": 0.0,
            }
        
        # Send motor speeds to Arduino
        self.robot_interface.periodic(self.get_comm_port(), [port1_speed, port2_speed, port3_speed])

        # Update UI
        self.update_motor_fields(port1_speed, port2_speed, port3_speed)



def main():
    app = QApplication(sys.argv)

    window = Application()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()