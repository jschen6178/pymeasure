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
from local_instrument.Yokogawa_GS200 import YokogawaGS200
from lakeshore import Model336
from local_instrument.Lakeshore_LS625 import ElectromagnetPowerSupply

# pymeasure imports for running the experiment
from pymeasure.experiment import Procedure, Results, unique_filename
from pymeasure.experiment.parameters import FloatParameter, Parameter
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
    sample_name = Parameter("Sample name", default="DefaultSample")
    set_temperature = FloatParameter("Set temperature", units="K", default=10)
    set_current = FloatParameter("Set Current", units="A", default=1e-4)
    max_field = FloatParameter("Max Field", units="T", default=0.5)
    min_field = FloatParameter("Min Field", units="T", default=-0.5)
    field_step = FloatParameter("Field Step", units="T", default=10e-3)
    current_field_constant = FloatParameter("Constant to convert from field to current", units="A/T", default=6.6472*2)
    magnet_ramp_rate = FloatParameter("Magnet Ramp Rate", units="A/s", default=0.1)
    # voltage_range = FloatParameter("Voltage Range", units="V", default=.200)
    time_per_measurement = FloatParameter(
        "Time per measurement", units="s", default=0.1
    )  # measure every 0.1 seconds?
    num_plc = FloatParameter(
        "Number of power line cycles aka. measurement accurac (0.1/1/10)", default=5
    )
    power_amp = FloatParameter("Amperage of heater", units="A", default=1.414)

    # These are the data values that will be measured/collected in the experiment
    DATA_COLUMNS = ["Resistance (ohm)", "Voltage (V)", "Magnetic Field (T)"]

    def startup(self):
        """
        Necessary startup actions (Connecting and configuring to devices).
        """
        # Initialize the instruments, see resources.ipynb
        self.meter = Keithley2182("GPIB::7")
        self.source = YokogawaGS200("GPIB::3")
        self.tctrl = Model336(
            com_port="COM4"
        )  # COM 4 - this is the one that controls sample, magnet, and radiation
        self.magnet = ElectromagnetPowerSupply("GPIB0::11::INSTR")
        self.tctrl.reset_instrument()
        self.meter.reset()
        self.source.reset()
        self.magnet.set_magnetic_field(0)
        # Configure the Keithley2001
        self.meter.active_channel = 1
        self.meter.channel_function = "voltage"
        self.meter.ch_1.setup_voltage(auto_range=True, nplc=self.num_plc)

        # Configure the YokogawaGS200
        
        self.source.source_mode = "current"
        self.source.source_range = self.set_current
        self.source.source_level = self.set_current
        self.source.current_limit = self.set_current
        self.source.source_enabled = True
        
        # Configure LS336 and stabilize at min_temperature
        self.tctrl.set_heater_pid(
            2, 50, 50, 0
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
        self.magnet.set_ramp_rate(self.magnet_ramp_rate)

        # heat sample stage to set temperature
        while True:
            if abs(self.tctrl.get_all_kelvin_reading()[0] - self.set_temperature) < 0.05:
                log.info("Temperature reached, sleeping 10 seconds for stablization.")
                break
            else:
                log.info(f"Current temeprature: {self.tctrl.get_all_kelvin_reading()[0]}")
                sleep(1)
        # Let sample stay at min_temperature for 30 seconds to stabilize
        voltage=self.meter.voltage
        log.info(f"Voltage: {voltage}")
        sleep(10)
        
        # Check that temperature of the magnet is cold enough, otherwise shut off experiment
        if self.tctrl.get_all_kelvin_reading()[1] > 5.1:
            log.warning("Catch stop command in procedure. Magnet overheated")
            self.meter.reset()
            self.tctrl.all_heaters_off()
            self.magnet.set_current(0)
            sys.exit()
        else:
            log.info(f"Magnet cooled at temperature {self.tctrl.get_all_kelvin_reading()[1]} K")
            
            

    def execute(self):
        """
        Contains the 'experiment' of the procedure.
        Basic requirements are emitting reslts self.emit() with the same data values defined in DATA_COLOUMS.
        """
        fields_up = np.arange(0, self.max_field, self.field_step)
        fields_down = np.arange(self.max_field, self.min_field, -self.field_step)
        fields_final = np.arange(self.min_field, 0, self.field_step)
        fields = np.concatenate((fields_up, fields_down, fields_final))  # Include the reverse
        log.info("Executing experiment.")
        # start ramping
        

        # main loop
        for field in fields:
            self.magnet.set_magnetic_field(field)
            sleep(self.field_step * self.current_field_constant / self.magnet.get_ramp_rate()*5) # wait a minute, calm down, chill out.
            voltage = self.meter.voltage  # Measure the voltage
            log.info(f"Voltage measurement: {voltage}")
            field = self.magnet.measured_magnetic_field()
            resistance = voltage/self.set_current
            self.emit(
                "results",
                {"Magnetic Field (T)": field, "Voltage (V)": voltage, "Resistance (ohm)": resistance},
            )
            sleep(20e-3)

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
        self.source.shutdown()
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
                "sample_name",
                "set_temperature",
                "set_current",
                "min_field",
                "max_field",
                "field_step",
                "num_plc",

            ],
            displays=[
                "sample_name",
                "set_temperature",
                "set_current",
                "min_field",
                "max_field",
                "field_step",
                "num_plc",

            ],
            x_axis="Magnetic Field (T)",
            y_axis="Voltage (V)",
        )
        self.setWindowTitle("Field Sweep Measurement")

    def queue(self, procedure=None):
        

        procedure = self.make_procedure()
        directory = os.path.join(os.path.dirname(__file__), "Results", f"{procedure.sample_name}")
        filename = unique_filename(directory, prefix=f"sample_{procedure.sample_name}_fieldsweep_{procedure.max_field}T_{procedure.set_temperature}K_4probe_{procedure.set_current}A")
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)

        self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = IVMeasurementWindow()
    window.show()
    app.exec_()
