import os
import sys
import dbus
import dbus.service
import socket
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

class HID_Profile(dbus.service.Object):
    fd = -1

    @dbus.service.method('org.bluez.Profile1', in_signature='', out_signature='')
    def Release(self):
        print('Release')
        mainloop.quit()

    @dbus.service.method('org.bluez.Profile1', in_signature='oha{sv}', out_signature='')
    def NewConnection(self, path, fd, properties):
        self.fd = fd.take() # take ownership of filedescriptor fd
        print('NewConnection({}, {})'.format(path, self.fd))
        for key in properties.keys():
            if key == 'Version' or key == 'Features':
                print('{} = 0x{:04x}'.format(key, properties[key]))
            else:
                print('{} = {}'.format(key, properties[key]))

    @dbus.service.method('org.bluez.Profile1', in_signature='o', out_signature='')
    def RequestDisconnection(self, path):
        print('RequestDisconnection {}'.format(path))
        if self.fd > 0:
            os.close(self.fd)
            self.fd = -1

class BTKbDevice:
    MY_DEV_NAME = 'BT_HID_Keyboard'
    P_CTRL = 17
    P_INTR = 19
    PROFILE_DBUS_PATH = '/bluez/btEmulator/btkb_profile'
    ADAPTER_IFACE = 'org.bluez.Adapter1'
    DEVICE_INTERFACE = 'org.bluez.Device1'
    DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'
    DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'
    
    script_directory = os.path.dirname(os.path.realpath(__file__))
    SDP_RECORD_PATH = os.path.join(script_directory, 'sdp_records/keyboard_mouse.xml')

    UUID = '00001124-0000-1000-8000-00805f9b34fb'

    def __init__(self, hci=0):
        self.scontrol = None
        self.ccontrol = None # socket object for control
        self.sinterrupt = None
        self.cinterrupt = None # socket object for interrupt
        self.dev_path = '/org/bluez/hci{}'.format(hci)
        print('Setting up BT device')
        self.bus = dbus.SystemBus()
        self.adapter_methods = dbus.Interface(self.bus.get_object('org.bluez', self.dev_path), self.ADAPTER_IFACE)
        self.adapter_property = dbus.Interface(self.bus.get_object('org.bluez', self.dev_path), self.DBUS_PROP_IFACE)
        self.bus.add_signal_receiver(self.interfaces_added, 
                                     dbus_interface=self.DBUS_OM_IFACE, 
                                     signal_name='InterfacesAdded')
        self.bus.add_signal_receiver(self._properties_changed, 
                                     dbus_interface=self.DBUS_PROP_IFACE, 
                                     signal_name='PropertiesChanged', 
                                     arg0=self.DEVICE_INTERFACE, 
                                     path_keyword='path')
        print('Configuring for name {}'.format(BTKbDevice.MY_DEV_NAME))
        self.configure_hid_profile()
        self.alias = BTKbDevice.MY_DEV_NAME
        self.discoverabletimeout = 0
        self.discoverable = True
        
    def interfaces_added(self, path, device_info):
        pass
    
    def _properties_changed(self, interface, changed, invalidated, path):
        if self.on_disconnect is not None:
            if 'Connected' in changed:
                if not changed['Connected']:
                    self.on_disconnect()

    def on_disconnect(self):
        print('The client has been disconnect')
        self.listen()

    @property
    def address(self):
        """Return the adapter MAC address."""
        return self.adapter_property.Get(self.ADAPTER_IFACE, 'Address')
    
    @property
    def powered(self):
        """
        power state of the Adapter.
        """
        return self.adapter_property.Get(self.ADAPTER_IFACE, 'Powered')
    
    @powered.setter
    def powered(self, new_state):
        self.adapter_property.Set(self.ADAPTER_IFACE, 'Powered', new_state)

    @property
    def alias(self):
        return self.adapter_property.Get(self.ADAPTER_IFACE, 'Alias')

    @alias.setter
    def alias(self, new_alias):
        self.adapter_property.Set(self.ADAPTER_IFACE, 'Alias', new_alias)

    @property
    def discoverabletimeout(self):
        """Discoverable timeout of the Adapter."""
        return self.adapter_property.Get(self.ADAPTER_IFACE, 'DiscoverableTimeout')

    @discoverabletimeout.setter
    def discoverabletimeout(self, new_timeout):
        self.adapter_property.Set(self.ADAPTER_IFACE, 'DiscoverableTimeout', dbus.UInt32(new_timeout))

    @property
    def discoverable(self):
        """Discoverable state of the Adapter."""
        return self.adapter_property.Get(self.ADAPTER_IFACE, 'Discoverable')

    @discoverable.setter
    def discoverable(self, new_state):
        self.adapter_property.Set(self.ADAPTER_IFACE, 'Discoverable', new_state)

    def configure_hid_profile(self):
        """
        Setup and register HID Profile
        """
        print('Configuring Bluez Profile')
        service_record = self.read_sdp_service_record()

        opts = {
            'Role' : 'server',
            'RequireAuthentication' : False,
            'RequireAuthorization' : False,
            'AutoConnect' : True,
            'ServiceRecord' : service_record,
        }

        manager = dbus.Interface(self.bus.get_object('org.bluez', '/org/bluez'), 'org.bluez.ProfileManager1')
        HID_Profile(self.bus, BTKbDevice.PROFILE_DBUS_PATH)
        manager.RegisterProfile(BTKbDevice.PROFILE_DBUS_PATH, BTKbDevice.UUID, opts)

        print('Profile registered.')

    @staticmethod
    def read_sdp_service_record():
        """
        Read and return SDP record from a file
        :return: (string) SDP record
        """
        print('Reading service record')
        try:
            fh = open(BTKbDevice.SDP_RECORD_PATH, 'r')
        except OSError:
            sys.exit('Could not open the sdp record. Exiting...')

        return fh.read()   

    def listen(self):
        """
        Listen for connections coming from HID client
        """

        print('Waiting for connections')
        self.scontrol = socket.socket(socket.AF_BLUETOOTH,
                                      socket.SOCK_SEQPACKET,
                                      socket.BTPROTO_L2CAP)
        self.scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sinterrupt = socket.socket(socket.AF_BLUETOOTH,
                                        socket.SOCK_SEQPACKET,
                                        socket.BTPROTO_L2CAP)
        self.sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.scontrol.bind((self.address, self.P_CTRL))
        self.sinterrupt.bind((self.address, self.P_INTR))

        # Start listening on the server sockets
        self.scontrol.listen(1)  # Limit of 1 connection
        self.sinterrupt.listen(1)

        self.ccontrol, cinfo = self.scontrol.accept()
        print('{} connected on the control socket'.format(cinfo[0]))

        self.cinterrupt, cinfo = self.sinterrupt.accept()
        print('{} connected on the interrupt channel'.format(cinfo[0]))

    def send(self, data):
        """
        Send HID message
        :param msg: (bytes) HID packet to send
        """
        self.cinterrupt.send(data)


class BTKbService(dbus.service.Object):
    """
    Setup of a D-Bus service to recieve HID messages from other
    processes.
    Send the recieved HID messages to the Bluetooth HID server to send
    """
    def __init__(self):
        print('Setting up service')
        bus_name = dbus.service.BusName('org.btEmulator.btkbservice', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/org/btEmulator/btkbservice')
        # create and setup our device
        self.device = BTKbDevice()
        # start listening for socket connections
        self.device.listen()

    @dbus.service.method('org.btEmulator.btkbservice', in_signature='ay')
    def send_keys(self, state):
        data = bytearray(state)
        self.device.send(data)

    @dbus.service.method('org.btEmulator.btkbservice', in_signature='ay')
    def send_mouse(self, state):
        data = bytearray(state)
        self.device.send(data)

if __name__ == "__main__":
    # The sockets require root permission
    if not os.geteuid() == 0:
        sys.exit('Only root can run this script.')

    DBusGMainLoop(set_as_default = True)
    myservice = BTKbService()
    mainloop = GLib.MainLoop()
    mainloop.run()
