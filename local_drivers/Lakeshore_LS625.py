from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import strict_range

class LakeShore625(Instrument):
    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            "Lake Shore 625 Magnet Power Supply",
            **kwargs
        )

    @property
    def id(self):
        """ Returns the instrument identification string """
        return self.ask("*IDN?")

    @property
    def output_current(self):
        """ Gets the output current in mA """
        return self.ask("IOUT?")

    @output_current.setter
    def output_current(self, value):
        """ Sets the output current in mA """
        value = strict_range(value, [-60000, 60000])  # ±60 A in mA
        self.write(f"IOUT {value:.1f}")

    @property
    def output_voltage(self):
        """ Gets the output voltage in mV """
        return self.ask("VOUT?")

    @output_voltage.setter
    def output_voltage(self, value):
        """ Sets the output voltage in mV """
        value = strict_range(value, [100, 5000])  # 0.1 V to 5 V in mV
        self.write(f"VOUT {value:.1f}")

    def reset(self):
        """ Resets the instrument to its default state """
        self.write("*RST")

    def self_test(self):
        """ Initiates a self-test and returns the result """
        return self.ask("*TST?")

    def ramp_current(self, start, end, rate):
        """ Ramps the current from start to end at a specified rate in mA/s """
        self.write(f"RAMP:START {start:.1f}")
        self.write(f"RAMP:END {end:.1f}")
        self.write(f"RAMP:RATE {rate:.3f}")
        self.write("RAMP:INIT")

    @property
    def ramp_rate(self):
        """ Gets the ramp rate in mA/s """
        return self.ask("RAMP:RATE?")

    @ramp_rate.setter
    def ramp_rate(self, value):
        """ Sets the ramp rate in mA/s """
        value = strict_range(value, [0.1, 99999])  # 0.1 mA/s to 99.999 A/s
        self.write(f"RAMP:RATE {value:.3f}")

    def quench_protection(self):
        """ Checks if quench protection is enabled """
        return self.ask("QUENCH:PROT?")

    def enable_quench_protection(self):
        """ Enables quench protection """
        self.write("QUENCH:PROT ON")

    def disable_quench_protection(self):
        """ Disables quench protection """
        self.write("QUENCH:PROT OFF")

    def read_status(self):
        """ Reads the status of the instrument """
        return self.ask("STATUS?")

    def persistent_switch_heater_on(self):
        """ Turns the persistent switch heater on """
        self.write("PSH ON")

    def persistent_switch_heater_off(self):
        """ Turns the persistent switch heater off """
        self.write("PSH OFF")

# Example usage
if __name__ == "__main__":
    instrument = LakeShore625("GPIB::1")
    print(instrument.id)
    print(instrument.output_current)
    instrument.output_current = 5000  # Set current to 5A
    instrument.ramp_current(0, 5000, 50)  # Ramp current to 5A at 50 mA/s
    print(instrument.read_status())
    instrument.persistent_switch_heater_on()
    instrument.persistent_switch_heater_off()
