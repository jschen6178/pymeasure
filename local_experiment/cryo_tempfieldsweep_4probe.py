"""
This procedure steps across set fields and runs a temperature sweep to find:
Critical temperature as a function of applied field

Justin 30/7/2024
"""

import sys
import os

current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_directory)
sys.path.append(parent_directory)

# utilities
from time import sleep
import numpy as np
import matplotlib.pyplot as plt
import logging

# instrument imports
from local_instrument.keithley2182 import Keithley2182
from lakeshore import Model336
from local_instrument.Yokogawa_GS200 import YokogawaGS200
from local_instrument.Lakeshore_LS625 import ElectromagnetPowerSupply

# pymeasure imports for running the experiment
from pymeasure.experiment import Procedure, Results, unique_filename
from pymeasure.experiment.parameters import FloatParameter, Parameter, ListParameter
from pymeasure.display.Qt import QtWidgets
from pymeasure.display.windows import ManagedWindow

log = logging.getLogger("")
log.addHandler(logging.NullHandler())
log.setLevel(logging.INFO)


class CryoProcedure(Procedure):
    """
    Procedure class that contains all the code that communicates with the devices.
    3 sections - Startup, Execute, Shutdown.
    Outputs data to the GUI
    """

    # Parameters for the experiment, saved in csv
    # note that we want to reach min(?)_temperature prior to any measurements
    sample_name = Parameter("Sample name", default="DefaultSample")
    min_temperature = FloatParameter("Minimum temperature", units="K", default=9)
    max_temperature = FloatParameter("Maximum temperature", units="K", default=12)
    ramp_rate = FloatParameter("Temperature ramp rate", units="K/min", default=1)
    # voltage_range = FloatParameter("Voltage Range", units="V", default=.200)
    # voltmeter set to auto range works well
    max_field = FloatParameter("Max Field", units="T", default=1)
    min_field = FloatParameter("Min Field", units="T", default=-1)
    field_step = FloatParameter("Field Step", units="T", default=1e-1)
    current_field_constant = FloatParameter(
        "Constant to convert from field to current", units="A/T", default=6.6472 * 2
    )
    
    field = FloatParameter("Current field", units="T", default=0)


    time_per_measurement = FloatParameter(
        "Time per measurement", units="s", default=0.1
    )  # measure every 0.1 seconds?
    num_plc = FloatParameter(
        "Number of power line cycles aka. measurement accurac (0.1/1/10)", default=5
    )
    set_current = FloatParameter("Set current", units="A", default=1e-4)
    #############################################################
    ### DO NOT CHANGE THIS UNLESS YOU KNOW WHAT YOU ARE DOING ###
    #############################################################
    power_amp = FloatParameter("Amperage of heater", units="A", default=1.414)

    # These are the data values that will be measured/collected in the experiment
    DATA_COLUMNS = ["Temperature (K)", "Voltage (V)", "Resistance (ohm)"]

    def startup(self):
        """
        Necessary startup actions (Connecting and configuring to devices).
        """
        # Initialize the instruments, see resources.ipynb
        self.meter = Keithley2182("GPIB::7")
        self.source = YokogawaGS200("GPIB::3")
        self.source.reset()
        self.tctrl = Model336(
            com_port="COM4"
        )  # COM 4 - this is the one that controls sample, magnet, and radiation\
        self.magnet = ElectromagnetPowerSupply("GPIB0::11::INSTR")
        self.meter.reset()
        ### Configure the Keithley2182
        self.meter.active_channel = 1
        self.meter.channel_function = "voltage"
        self.meter.ch_1.setup_voltage(auto_range=True, nplc=self.num_plc)
        # nplc (number power line cycles) controls how fast the measurement takes.
        # The faster the measurement, the less integration cycles --> less accurate.

        ### Current source YokogawaGS300 setup

        self.source.source_mode = "current"
        self.source.source_range = self.set_current
        self.source.current_limit = self.set_current
        self.source.source_enabled = True
        self.source.source_level = self.set_current
        # Configure LS336 and stabilize at min_temperature
        #######################################################################
        ### SEE MANUAL FOR SET UP. DO NOT MISMATCH HEATER AND INPUT CHANNEL ###
        #######################################################################
        self.tctrl.reset_instrument
        self.tctrl.set_heater_pid(
            2, 50, 50, 5
        )  # intended for low setting, may need to adjust for high
        # .set_heater_setup Heater 1 @ 50 Ohm, 1 Amp
        self.tctrl.set_heater_setup(
            2,
            self.tctrl.HeaterResistance.HEATER_25_OHM,
            self.power_amp,
            self.tctrl.HeaterOutputUnits.POWER,
        )
        # .set_heater_output_mode Heater 1 @ closed loop mode, CHANNEL_A for sample stage, True - Remains on after power cycle (?)
        self.tctrl.set_heater_output_mode(
            2,
            self.tctrl.HeaterOutputMode.CLOSED_LOOP,
            self.tctrl.InputChannel.CHANNEL_A,
            True,
        )
        # setpoint to min temperature and wait until stabilize
        self.tctrl.set_setpoint_ramp_parameter(2, False, 0)
        self.tctrl.set_control_setpoint(2, self.min_temperature)
        self.tctrl.set_heater_range(2, self.tctrl.HeaterRange.LOW)
        while True:
            if abs(self.tctrl.get_all_kelvin_reading()[0] - self.min_temperature) < 0.1:
                log.info("Temperature reached, sleeping 10 seconds for stablization.")
                break
            else:
                log.info(
                    "Current temeprature: "
                    + str(self.tctrl.get_all_kelvin_reading()[0])
                )
                sleep(1)
        # Let sample stay at min_temperature for 30 seconds to stabilize
        sleep(10)
        self.magnet.set_magnetic_field(self.field)
        sleep(self.field_step * self.current_field_constant / self.magnet.get_ramp_rate()*2)
        log.info(f"Magnet field set: {self.field}")

    def execute(self):
        """
        Contains the 'experiment' of the procedure.
        Basic requirements are emitting reslts self.emit() with the same data values defined in DATA_COLOUMS.
        """
        log.info("Executing experiment.")
        # start ramping

        self.tctrl.set_heater_range(2, self.tctrl.HeaterRange.LOW)
        self.tctrl.set_setpoint_ramp_parameter(2, True, self.ramp_rate)
        self.tctrl.set_control_setpoint(2, self.max_temperature)
        # main loop
        while True:

            sleep(self.time_per_measurement)  # wait a minute, calm down, chill out.
            voltage = self.meter.voltage  # Measure the voltage
            log.info("Voltage measurement: " + str(voltage))
            temperature = self.tctrl.get_all_kelvin_reading()[
                0
            ]  # index 0 for sample stage temperature
            resistance = voltage / self.set_current
            self.emit(
                "results",
                {
                    "Temperature (K)": temperature,
                    "Voltage (V)": voltage,
                    "Resistance (ohm)": resistance,
                },
            )
            # stop measuring once reached max temperature
            if abs(self.tctrl.get_all_kelvin_reading()[0] - self.max_temperature) < 0.1:
                break

            if self.should_stop():
                log.warning("Catch stop command in procedure")
                self.meter.reset()
                self.tctrl.all_heaters_off()
                self.tctrl.set_setpoint_ramp_parameter(2, False, 0)
                self.tctrl.set_control_setpoint(2, 0)
                break

        log.info("Experiment executed")

    def shutdown(self):
        """
        Shutdown all machines.
        """
        log.info("Shutting down")
        self.meter.reset()
        self.source.shutdown()
        self.tctrl.set_setpoint_ramp_parameter(2, False, 0)
        self.tctrl.set_control_setpoint(2, 0)
        self.tctrl.all_heaters_off()
        self.tctrl.disconnect_usb()


class CryoMeasurementWindow(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=CryoProcedure,
            inputs=[
                "sample_name",
                "min_field",
                "max_field",
                "field_step",
                "min_temperature",
                "max_temperature",
                "ramp_rate",
                "set_current",
                "time_per_measurement",
                "num_plc",
            ],
            displays=[
                "sample_name",
                "min_field",
                "max_field",
                "field_step",
                "min_temperature",
                "max_temperature",
                "ramp_rate",
                "set_current",
                "time_per_measurement",
                "num_plc",
            ],
            x_axis="Temperature (K)",
            y_axis="Voltage (V)",
        )
        self.setWindowTitle("4-Probe Resistance Temperature Sweep Measurement")

    def queue(self, procedure=None):
        procedure = self.make_procedure()
        
        fields_up = np.arange(0, procedure.max_field, procedure.field_step)
        fields_down = np.arange(procedure.max_field, procedure.min_field, procedure.field_step)
        fields_final = np.arange(procedure.min_field, 0, procedure.field_step)
        fields = np.concatenate(
            (fields_up, fields_down, fields_final)
        )  # Include the reverse
        for field in fields:
            # Set the field parameter to the current value
            procedure = self.make_procedure()
            procedure.field = field
            directory = os.path.join(os.path.dirname(__file__), "Results", f"{procedure.sample_name}")  # Change this to the desired directory
            filename = unique_filename(
                directory,
                prefix=f"sample_{procedure.sample_name}_field_{round(field, 3)}T_{procedure.min_temperature}_{procedure.max_temperature}_4probe_{procedure.set_current}",
            )

            results = Results(procedure, filename)
            experiment = self.new_experiment(results)
            self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = CryoMeasurementWindow()
    window.show()
    app.exec_()
