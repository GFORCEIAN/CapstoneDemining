import serial


class ArduinoInterface:
    #
    # These values must match protocol.h
    #
    CMD_PING = 0x00
    CMD_SET_MOTOR = 0x01
    CMD_SET_ALL = 0x02
    CMD_STOP_ALL = 0x03

    def __init__(self):
        self._serial = None
        self._motorSpeeds = [
            {
                "A": 0.0,
                "B": 0.0,
            },
            {
                "A": 0.0,
                "B": 0.0,
            },
            {
                "A": 0.0,
                "B": 0.0,
            },
            {
                "A": 0.0,
                "B": 0.0,
            },
        ]

    def _connect(self, port, baudrate=115200):
        if self._serial is not None:
            self.disconnect()
        
        self._port = port
        self._baudrate = baudrate

        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=0.1
            )
            print(f"Connected to {port}!")
        except Exception:
            # Could not open this port
            self._serial = None
            return False

        return self._serial.is_open

    def disconnect(self):
        if self._serial is None:
            return
        
        self.halt_motors()
        self._serial.close()

    def ping(self):
        """
        Send a ping command.
        """
        if self._serial is None:
            return
                
        self._serial.write(bytes([self.CMD_PING]))

    def halt_motors(self):
        """
        Stop all motors.
        """
        if self._serial is None:
            return
                
        self._serial.write(bytes([self.CMD_STOP_ALL]))

    def set_motor_speed(self, port, motor, speed):
        """
        port: 1-4

        motor:
            'A' / 0
            'B' / 1

        speed:
            -1 to +1
        """
        if self._serial is None:
            return

        if port < 1 or port > 4:
            raise ValueError("port must be 1-4")

        if motor not in ('A', 'B', 0, 1):
            raise ValueError("motor must be A/0 or B/1")
        
        if motor == 'A':
            motor = 0
        elif motor == 'B':
            motor = 1

        # Get speed to fit within an int8
        raw_speed = int(speed*127)
        raw_speed = min(raw_speed, 127)
        raw_speed = max(raw_speed, -127)
        raw_speed &= 0xFF # Convert to int8

        address = (port << 4) | motor

        packet = bytes([
            self.CMD_SET_MOTOR,
            address,
            raw_speed
        ])

        self._serial.write(packet)

    def set_port_speed(self, port, speed):
        """
        Set both motors on a port (1-4) to a specific speed [-1, 1].
        """
        if self._serial is None:
            return
                
        if port < 1 or port > 4:
            raise ValueError("port must be 1-4")

        # Get speed to fit within an int8
        raw_speed = int(speed*127)
        raw_speed = min(raw_speed, 127)
        raw_speed = max(raw_speed, -127)
        raw_speed &= 0xFF # Convert to int8

        packet = bytes([
            self.CMD_SET_ALL,
            port,
            raw_speed
        ])

        self._serial.write(packet)

    def periodic(self, comm_port, speeds:list[dict[str, float]]):
        """
        Called by the GUI timer.
        Currently keeps the link alive by pinging.
        """

        # Try connecting if there is no established connection
        if self._serial is None or not self._serial.is_open:
            self._connect(comm_port)
            #print(f"{comm_port} is not open!")

        if self._serial is None:
            return
                
        
        if self._serial.is_open:
            # Loop through every motor port
            foundDifference = False
            for motor_port in range(len(speeds)):
                # Send command to set motor speeds if they have changed significantly
                if abs(speeds[motor_port]['A'] - self._motorSpeeds[motor_port]['A']) > 0.005:
                    self.set_motor_speed(motor_port, 'A', speeds[motor_port]['A'])
                    self._motorSpeeds[motor_port]['A'] = speeds[motor_port]['A']
                    foundDifference = True
                if abs(speeds[motor_port]['B'] - self._motorSpeeds[motor_port]['B']) > 0.005:
                    self.set_motor_speed(motor_port, 'B', speeds[motor_port]['B'])
                    self._motorSpeeds[motor_port]['B'] = speeds[motor_port]['B']
                    foundDifference = True

            # If no motors have been updated, just send a heartbeat
            if not foundDifference:
                self.ping()

            # Check for any responses from the arduino
            print(self.read_responses(), end="") # Record responses

    def read_responses(self):
        """
        Helper for consuming replies.
        """
        if self._serial is None:
            return 

        if self._serial.in_waiting:
            return self._serial.read(self._serial.in_waiting)

        return b""