#utilities
from time import sleep
import sys
import numpy as np
import matplotlib.pyplot as plt
import logging

# instrument imports
from lakeshore import Model336

# pymeasure imports for running the experiment
from pymeasure.experiment import Procedure, Results, Worker, unique_filename
from pymeasure.experiment.parameters import FloatParameter
from pymeasure.display.Qt import QtWidgets
from pymeasure.display.windows import ManagedWindow

log = logging.getLogger('')
log.addHandler(logging.NullHandler())
log.setLevel(logging.INFO)
#main class Procedure that holds initiating code and executing code. will be used in results()
class IVProcedure(Procedure):
    # Parameters for the experiment
    # note that we want to reach max_temperature prior to any measurements
    # delay to allow for temperature and magnetic field settling
    
    
    DATA_COLUMNS = ['Set Temperature (K)', 'Measure Temperature (K)']
    log.info("is this visible?")
    def startup(self):
        log.info("starting up!")
        # try to initialize things
        try:
            # Initialize LakeShore336 instruments
            log.info('initalizing')
            self.ls336_1 = Model336(com_port='COM3') # COM 3
            self.ls336_2 = Model336(com_port='COM4') # COM 4
            log.info('initialized')
            # set heater pid control rate so that we can heat shit up to the right temperature
            log.info(self.ls336_1.get_all_kelvin_reading())
            self.ls336_1.set_heater_pid(1,40,27,0)
            self.ls336_2.set_heater_pid(3,35,20,0)
            self.ls336_1.set_heater_setup(1, self.ls336_1.HeaterResistance.HEATER_50_OHM, 0.75, self.ls336_1.HeaterOutputUnits.POWER)
            self.ls336_1.set_heater_output_mode(1, self.ls336_1.HeaterOutputMode.CLOSED_LOOP, self.ls336_1.InputChannel.CHANNEL_A)
            self.ls336_1.set_control_setpoint(1, 305)
            log.info('setpointed')
            self.ls336_1.set_heater_range(1, self.ls336_1.HeaterRange.MEDIUM)
            log.info('heater ranged')
            # self.ls336_1.input_B.wait_for_temperature(290)
            log.info(self.ls336_1.get_heater_output(1))
            log.info('done heating')
            sleep(20)
            log.info(self.ls336_1.get_all_kelvin_reading())
        except Exception as e:  
            log.error(f"Error initializing LakeShore336: {e}")
            self.ls336_1 = None
            self.ls336_2 = None
        
    
    def execute(self):
        log.info("executing!")
        temperatures = np.arange(2, 300, 1)
        for temperature in temperatures:
            self.ls336_1.output_2.setpoint = temperature
            self.ls336_1.input_B.wait_for_temperature(temperature)
            measurement = self.ls336_1.input_B.temperature
            self.emit('results', {
                'Set Temperature (K)' : temperature,
                'Measure Temperature (K)': measurement,
            })
            if self.should_stop():
                log.warning("Catch stop command in procedure")
                break
            sleep(10)
        

    def shutdown(self):
        
        self.ls336_1.all_heaters_off()
        self.ls336_2.all_heaters_off()

class MainWindow(ManagedWindow):

    def __init__(self):
        super().__init__(
            procedure_class=IVProcedure,
            x_axis='Set Temperature (K)',
            y_axis='Measure Temperature (K)'
        )
        self.setWindowTitle('IV Measurement')

    def queue(self):
        directory = "./"  # Change this to the desired directory
        filename = unique_filename(directory, prefix='IV')

        procedure = self.make_procedure()
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)

        self.manager.queue(experiment)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())