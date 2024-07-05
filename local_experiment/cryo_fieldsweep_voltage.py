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
from local_instrument.keithley2001 import Keithley2001
from lakeshore import Model336
from local_instrument.Lakeshore_LS625 import ElectromagnetPowerSupply

# pymeasure imports for running the experiment
from pymeasure.experiment import Procedure, Results, unique_filename
from pymeasure.experiment.parameters import FloatParameter
from pymeasure.display.Qt import QtWidgets
from pymeasure.display.windows import ManagedWindow

log = logging.getLogger("")
log.addHandler(logging.NullHandler())
log.setLevel(logging.INFO)

"""
Update: measured_magnetic_field uses scpi RDGF? not SETF? Problem solved

Note: (Ignore, problem solved)

In this program you will see us using the set current command in order to set the field.
This is because the ramp_rate is calculated in amps, and the ramp_rate tells us how long
to wait until we reach our set point field.

Lame, but what can you do :(. Write better SCPI commands T-T
Conversion rate: 6.6472 Amps per Tesla of applied field.
"""
class CryoProcedure(Procedure):
    """
    Procedure class that contains all the code that communicates with the devices.
    3 sections - Startup, Execute, Shutdown.
    Outputs data to the GUI
    """

    # Parameters for the experiment, saved in csv
    # note that we want to reach min(?)_temperature prior to any measurements
    set_temperature = FloatParameter("Set temperature", units="K", default=10)
    start_field = FloatParameter("Start Field", units="T", default=0)
    end_field = FloatParameter("End Field", units="T", default=0)
    current_field_constant = FloatParameter("Constant to convert from field to current", units="A/T", default=6.6472)
    voltage_range = FloatParameter("Voltage Range", units="V", default=.200)
    time_per_measurement = FloatParameter(
        "Time per measurement", units="s", default=0.1
    )  # measure every 0.1 seconds?
    num_plc = FloatParameter(
        "Number of power line cycles aka. measurement accurac (0.1/1/10)", default=1
    )
    power_amp = FloatParameter("Amperage of heater", units="A", default=1.414)

    # These are the data values that will be measured/collected in the experiment
    DATA_COLUMNS = ["Temperature (K)", "Voltage (V)", "Magnetic Field (T)"]

    def startup(self):
        """
        Necessary startup actions (Connecting and configuring to devices).
        """
        # Initialize the instruments, see resources.ipynb
        self.meter = Keithley2001("GPIB::12")
        self.tctrl = Model336(
            com_port="COM4"
        )  # COM 4 - this is the one that controls sample, magnet, and radiation
        self.magnet = ElectromagnetPowerSupply("GPIB0::11::INSTR")
        self.tctrl.reset_instrument()
        self.meter.reset()
        self.magnet.set_magnetic_field(0)
        # Configure the Keithley2001
        self.meter.measure_voltage()
        self.meter.voltage_range = self.voltage_range
        # nplc (number power line cycles) controls how fast the measurement takes.
        # The faster the measurement, the less integration cycles --> less accurate.
        self.meter.voltage_nplc = self.num_plc

        # Configure LS336 and stabilize at min_temperature
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
        self.tctrl.set_control_setpoint(2, self.set_temperature)
        self.tctrl.set_heater_range(2, self.tctrl.HeaterRange.LOW)

        # set ramp rate of magnet at 0.1A/s
        self.magnet.set_ramp_rate(0.1)

        # heat sample stage to set temperature
        while True:
            if abs(self.tctrl.get_all_kelvin_reading()[0] - self.set_temperature) < 0.01:
                log.info("Temperature reached, sleeping 15 seconds for stablization.")
                break
            else:
                log.info(f"Current temeprature: {self.tctrl.get_all_kelvin_reading()[0]}")
                sleep(1)
        # Let sample stay at min_temperature for 15 seconds to stabilize
        sleep(15)
        
        # Check that temperature of the magnet is cold enough, otherwise shut off experiment
        if self.tctrl.get_all_kelvin_reading()[1] > 5.3:
            log.warning("Catch stop command in procedure. Magnet overheated")
            self.meter.reset()
            self.tctrl.all_heaters_off()
            self.magnet.set_current(0)
            sys.exit()
        else:
            log.info(f"Magnet cooled at temperature {self.tctrl.get_all_kelvin_reading()[1]} K")
            log.info(f"Starting field at {self.start_field} T")
            self.magnet.set_magnetic_field(self.start_field)
            while True:
                if abs(self.magnet.measured_magnetic_field() - self.start_field) < 0.005:
                    log.info("Start field reached, sleeping 15 seconds for stablization.")
                    break
                else:
                    log.info(f"Current field:{self.magnet.measured_magnetic_field()}")
                    sleep(1)
        sleep(15)
        log.info(f"Magnetic field at {self.magnet.measured_magnetic_field()} T")

    def execute(self):
        """
        Contains the 'experiment' of the procedure.
        Basic requirements are emitting reslts self.emit() with the same data values defined in DATA_COLOUMS.
        """
        log.info("Executing experiment.")
        # start ramping
        self.magnet.set_magnetic_field(self.end_field)

        # main loop
        while True:

            sleep(self.time_per_measurement)  # wait a minute, calm down, chill out.
            voltage = float(
                self.meter.voltage[0].strip("NVDC")
            )  # Measure the voltage
            log.info(f"Voltage measurement: {voltage}")
            field = self.magnet.measured_magnetic_field()
            self.emit(
                "results",
                {"Magnetic Field (T)": field, "Voltage (V)": voltage},
            )
            # stop measuring once reached max temperature
            if abs(self.magnet.measured_magnetic_field() - self.end_field) < 0.01:
                break

            if self.should_stop():
                log.warning("Catch stop command in procedure")
                self.meter.reset()
                self.tctrl.all_heaters_off()
                self.magnet.set_magnetic_field(0)
                break

        log.info("Experiment executed")

    def shutdown(self):
        """
        Shutdown all machines.
        """
        log.info("Shutting down")
        self.meter.reset()
        self.tctrl.set_control_setpoint(2, 0)
        self.tctrl.all_heaters_off()
        self.magnet.set_magnetic_field(0)
        self.tctrl.reset_instrument()
        self.tctrl.disconnect_usb()


class IVMeasurementWindow(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=CryoProcedure,
            inputs=[
                "set_temperature",
                "start_field",
                "end_field",
                "voltage_range",
                "time_per_measurement",
                "num_plc",
                "power_amp",
            ],
            displays=[
                "set_temperature",
                "start_field",
                "end_field",
                "voltage_range",
                "time_per_measurement",
                "num_plc",
                "power_amp",
            ],
            x_axis="Magnetic Field (T)",
            y_axis="Voltage (V)",
        )
        self.setWindowTitle("Field Sweep Measurement")

    def queue(self, procedure=None):
        directory = "./"  # Change this to the desired directory
        filename = unique_filename(directory, prefix="B_SWEEP")

        procedure = self.make_procedure()
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)

        self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = IVMeasurementWindow()
    window.show()
    app.exec_()
