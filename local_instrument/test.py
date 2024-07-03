from Lakeshore_LS625 import ElectromagnetPowerSupply
from time import sleep
magnet = ElectromagnetPowerSupply("GPIB0::11::INSTR")
print("setting magnetic field")
magnet.set_magnetic_field(0)
