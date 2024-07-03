from lakeshore import Model336
tctrl = Model336(
            com_port="COM4"
        )  # COM 4 - this is the one that controls sample, magnet, and radiation
print(tctrl.get_all_kelvin_reading())
tctrl.reset_instrument()
tctrl.clear_interface_command()