import logging
from pymeasure.instruments import Instrument, SCPIUnknownMixin
from pymeasure.instruments.validators import (
    strict_discrete_set, truncated_discrete_set, truncated_range
)

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

MIN_RAMP_TIME = 0.1  # seconds


class YokogawaGS200(SCPIUnknownMixin, Instrument):
    """ Represents the Yokogawa GS200 source and provides a high-level interface for interacting
    with the instrument. """

    source_enabled = Instrument.control(
        "OUTPut:STATe?",
        "OUTPut:STATe %d",
        """Control whether the source is enabled. (bool)""",
        validator=strict_discrete_set,
        values={True: 1, False: 0},
        map_values=True
    )

    source_mode = Instrument.control(
        ":SOURce:FUNCtion?",
        ":SOURce:FUNCtion %s",
        """Control the source mode. Can be either 'current' or 'voltage'.""",
        validator=strict_discrete_set,
        values={'current': 'CURR', 'voltage': 'VOLT'},
        get_process=lambda s: s.strip()
    )

    source_range = Instrument.control(
        ":SOURce:RANGe?",
        "SOURce:RANGe %g",
        """Control the range (either in voltage or current)
        of the output. "Range" refers to the maximum source level. (float)""",
        validator=truncated_discrete_set,
        values=[1e-3, 10e-3, 100e-3, 200e-3, 1, 10, 30]
    )

    voltage_limit = Instrument.control(
        "SOURce:PROTection:VOLTage?",
        "SOURce:PROTection:VOLTage %g",
        """Control the voltage limit. "Limit" refers to maximum
        value of the electrical value that is conjugate to the mode (current is conjugate to
        voltage, and vice versa). Thus, voltage limit is only applicable when in 'current' mode""",
        validator=truncated_range,
        values=[1, 30]
    )

    current_limit = Instrument.control(
        "SOURce:PROTection:CURRent?",
        "SOURce:PROTection:CURRent %g",
        """Control the current limit. "Limit" refers to maximum value
        of the electrical value that is conjugate to the mode (current is conjugate to voltage,
        and vice versa). Thus, current limit is only applicable when in 'voltage' mode""",
        validator=truncated_range,
        values=[1e-3, 200e-3]
    )

    def __init__(self, adapter, name="Yokogawa GS200 Source", **kwargs):
        super().__init__(
            adapter, name, **kwargs
        )

    @property
    def source_level(self):
        """ Control the output level, either a voltage or a current,
        depending on the source mode. (float)
        """
        return float(self.ask(":SOURce:LEVel?"))

    @source_level.setter
    def source_level(self, level):
        if level > self.source_range * 1.2:
            raise ValueError(
                "Level must be within 1.2 * source_range, otherwise the Yokogawa will produce an "
                "error."
            )
        else:
            self.write("SOURce:LEVel %g" % level)

    def trigger_ramp_to_level(self, level, ramp_time):
        """
        Ramp the output level from its current value to "level" in time "ramp_time". This method
        will NOT wait until the ramp is finished (thus, it will not block further code evaluation).

        :param float level: final output level
        :param float ramp_time: time in seconds to ramp
        :return: None
        """
        if not self.source_enabled:
            raise ValueError(
                "YokogawaGS200 source must be enabled in order to ramp to a specified level. "
                "Otherwise, the Yokogawa will reject the ramp."
            )
        if ramp_time < MIN_RAMP_TIME:
            log.warning(
                f"Ramp time of {ramp_time}s is below the minimum ramp time of {MIN_RAMP_TIME}s, "
                f"so the Yokogawa will instead be instantaneously set to the desired level."
            )
            self.source_level = level
        else:
            # Use the Yokogawa's "program" mode to create the ramp
            ramp_program = (
                f":program:edit:start;"
                f":source:level {level};"
                f":program:edit:end;"
            )
            # set "interval time" equal to "slope time" to make a continuous ramp
            ramp_program += (
                f":program:interval {ramp_time};"
                f":program:slope {ramp_time};"
            )
            # run it once
            ramp_program += (
                ":program:repeat 0;"
                ":program:run"
            )
            self.write(ramp_program)

    def measure_voltage(self):
        """
        Measure the voltage output when in current mode.

        :return: Measured voltage (float)
        """
        if self.source_mode != 'current':
            raise ValueError("Voltage measurement is only valid in 'current' mode.")
        return float(self.ask(":MEASure:VOLTage?"))

    def measure_current(self):
        """
        Measure the current output when in voltage mode.

        :return: Measured current (float)
        """
        if self.source_mode != 'voltage':
            raise ValueError("Current measurement is only valid in 'voltage' mode.")
        return float(self.ask(":MEASure:CURRent?"))
