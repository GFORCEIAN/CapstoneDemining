from xbox_controller import XboxController


class Controller:
    def __init__(self):
        self._controller = None
        self._left_trig_moved = False
        self._right_trig_moved = False
        self._connect()

    @property
    def controller(self):
        return self._controller

    # Make sure to disconnect every time we are assigning a new value to controller
    @controller.setter
    def controller(self, value):
        if self._controller is not None:
            self.disconnect()

        # We are potentially connecting for the first time
        if value is not None:
            self._left_trig_moved = False
            self._right_trig_moved = False

        self._controller = value

    def _connect(self):
        """Attempt to connect to an Xbox controller."""
        try:
            self.controller = XboxController()
            self.controller.connect()
            info = self.controller.get_controller_info()
            print(f"Connected to: {info['name']}")
            return True
        except SystemExit as e:
            #print(f"Caught system exit {e}")
            self.controller = None
            return False
        except Exception:
            self.controller = None
            return False

    def is_connected(self):
        """
        Returns True if the controller is connected.

        If not connected, attempts to reconnect.
        """
        if self.controller is not None:
            try:
                # Test access to a known property
                # _ = self.controller.LeftJoystickX
                # TODO: Check if it is still connected somehow
                return True
            except Exception:
                self.controller = None

        return self._connect()

    def disconnect(self):
        """
        Disconnect from the controller if it was already connected
        """
        if self.controller is not None:
            self.controller.disconnect()

    def get_analog_value(self, control_name, update=True):
        """
        Returns the value of the requested analog joystick/trigger value.

        Valid control names:
            left_x
            left_y
            right_x
            right_y
            left_trigger
            right_trigger
        """

        if not self.is_connected() or self.controller is None:
            raise RuntimeError("Controller not connected")

        if update:
            self._state = self.controller.update_state()
        state = self._state

        match control_name:
            case "left_x":
                return state['left_joystick'][0]

            case "left_y":
                return -state['left_joystick'][1] # Invert so up is positive

            case "right_x":
                return state['right_joystick'][0]

            case "right_y":
                return -state['right_joystick'][1] # Invert so up is positive

            case "left_trigger":
                val:float = abs(state['triggers'][0]+1)/2.0 # Convert from [-1, 1] to [0, 1]
                if not self._left_trig_moved:
                    if val == 0.5:
                        val = 0 # The library hasn't updated this value yet (there is a bug in the library)
                    else:
                        self._left_trig_moved = True
                return val

            case "right_trigger":
                val:float = abs(state['triggers'][1]+1)/2.0 # Convert from [-1, 1] to [0, 1]
                if not self._right_trig_moved:
                    if val == 0.5:
                        val = 0 # The library hasn't updated this value yet (there is a bug in the library)
                    else:
                        self._right_trig_moved = True
                return val

            case _:
                raise ValueError(
                    f"Invalid control '{control_name}'. "
                    "Expected one of: left_x, left_y, right_x, "
                    "right_y, left_trigger, right_trigger"
                )


    def get_all_analog(self):
        """
        Return a string of all the analog joystick and trigger values in format:
        left_x, left_y, right_x, right_y, left_trigger, right_trigger
        """
        if not self.is_connected() or self.controller is None:
            return "_, _, _, _, _, _"
        
        return_string = (f"{self.get_analog_value('left_x'):>5.2f}, {self.get_analog_value('left_y', False):>5.2f}, " + 
            f"{self.get_analog_value('right_x', False):>5.2f}, {self.get_analog_value('right_y', False):>5.2f}, " + 
            f"{self.get_analog_value('left_trigger', False):.2f}, {self.get_analog_value('right_trigger', False):.2f}"
        )
        return return_string
        
    def get_all_digital(self):
        """
        Return a string of all the digital/binary button values in format:
        a, b, x, y, left_bumber, right_bumper, back, start, left_joystick, right_joystick, x-box logo
        """
        if not self.is_connected() or self.controller is None:
            return "_, _, _, _, _, _, _, _, _, _, _"

        pressed_buttons = self.controller.update_state()['pressed_buttons']

        return_string = ""
        for i in range(11):
            if i in pressed_buttons:
                return_string = return_string + "1"
            else:
                return_string = return_string + "0"

            if i < 10:
                return_string = return_string + ", "

        return return_string