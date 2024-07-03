from pymeasure.instruments import Instrument
from pymeasure.adapters import VISAAdapter


class ElectromagnetPowerSupply(Instrument):
    """Class representing a Lake Shore Model 643 or 648 electromagnet power supply."""

    def __init__(self, resource_name, **kwargs):
        super().__init__(
            VISAAdapter(resource_name),
            "Lake Shore Electromagnet Power Supply",
            **kwargs,
        )

    def set_magnetic_field(self, field_strength):
        """Sets the magnetic field strength.

        Args:
            field_strength (float): Desired magnetic field strength in the appropriate units (e.g., Tesla).
        """
        self.write(f"SETF {field_strength}")

    def measured_magnetic_field(self):
        """Gets the current magnetic field strength.

        Returns:
            float: Current magnetic field strength in the appropriate units (e.g., Tesla).
        """
        return float(self.ask("RDGF?"))

    def set_current(self, current):
        """Sets the output current."""
        self.write(f"SETI {current}")

    def get_current(self):
        """Returns the output current setting."""
        return float(self.ask("SETI?"))

    def set_ramp_rate(self, ramp_rate):
        """Sets the output current ramp rate."""
        self.write(f"RATE {ramp_rate}")

    def get_ramp_rate(self):
        """Returns the output current ramp rate."""
        return float(self.ask("RATE?"))

    def set_limits(self, max_current, max_ramp_rate):
        """Sets the upper setting limits for output current, and output current ramp rate."""
        self.write(f"LIMIT {max_current}, {max_ramp_rate}")

    def get_limits(self):
        """Returns the upper setting limits for output current, and output current ramp rate."""
        return [float(element) for element in self.ask("LIMIT?").split(",")]

    def set_ramp_segment(self, segment, current, ramp_rate):
        """Sets the current and ramp rate of one of the ramp segments."""
        self.write(f"RSEGS {segment}, {current}, {ramp_rate}")

    def get_ramp_segment(self, segment):
        """Returns the current and ramp rate of a specific ramp segment."""
        return [float(x) for x in self.ask(f"RSEGS? {segment}").split(",")]

    def set_ramp_segments_enable(self, state):
        """Specifies if ramp segments are to be used."""
        self.write(f"RSEG {int(state)}")

    def get_ramp_segments_enable(self):
        """Returns if ramp segments are to be used."""
        return bool(int(self.ask("RSEG?")))

    def get_measured_current(self):
        """Returns actual measured output current."""
        return float(self.ask("RDGI?"))

    def get_measured_voltage(self):
        """Returns actual output voltage measured at the power supply terminals."""
        return float(self.ask("RDGV?"))

    def stop_output_current_ramp(self):
        """Stops the output current ramp."""
        self.write("STOP")

    def set_programming_mode(self, mode):
        """Sets the current programming mode of the instrument."""
        self.write(f"XPGM {mode}")

    def get_programming_mode(self):
        """Returns the current programming mode of the instrument."""
        return int(self.ask("XPGM?"))

    def set_ieee_488(self, terminator, eoi_enable, address):
        """Configures the IEEE-488 interface."""
        self.write(f"IEEE {terminator},{eoi_enable},{address}")

    def get_ieee_488(self):
        """Returns IEEE-488 interface configuration."""
        return [int(x) for x in self.ask("IEEE?").split(",")]

    def set_ieee_interface_mode(self, mode):
        """Sets the interface mode of the instrument."""
        self.write(f"MODE {mode}")

    def get_ieee_interface_mode(self):
        """Returns the interface mode of the instrument."""
        return int(self.ask("MODE?"))

    def set_factory_defaults(self):
        """Sets all configuration values to factory defaults and resets the instrument."""
        self.write("DFLT 99")

    def reset_instrument(self):
        """Sets the controller parameters to power-up settings."""
        self.write("*RST")


# Create aliases using the product names
Model643 = ElectromagnetPowerSupply
Model648 = ElectromagnetPowerSupply
