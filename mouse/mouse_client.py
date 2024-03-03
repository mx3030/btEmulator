import dbus
import dbus.service
from pynput.mouse import Listener as MouseListener
from pynput.mouse import Button
import evdev
import time

MOUSEMAP = {
    Button.left : 0, 
    Button.right : 1,
    Button.middle : 2
}

class Mouse():
    """Emulated Mouse"""

    def __init__(self):
        # state structure of the emulated Bluetooth keyboard
        self.state = [
            0xA1,       # input report
            0x02,       # usage report : mouse
            0x00,       # buttons
            0x00,       # move x
            0x00,       # move y
            0x00]       # wheel
        
        # for mouse movement
        self.prev_x = 0
        self.prev_y = 0
        self.last = 0
        self.mouse_delay = 1/20

        # initialize D-Bus client
        print("[*] Initialize D-Bus keyboard client")
        self.bus = dbus.SystemBus()
        self.btkservice = self.bus.get_object("org.btEmulator.btkbservice", "/org/btEmulator/btkbservice")
        self.iface = dbus.Interface(self.btkservice, "org.btEmulator.btkbservice")
 
    def send_input(self):
        """Forward mouse events to the D-Bus service""" 
        self.iface.send_mouse(self.state)

    def on_click(self, x, y, button, pressed):
        """Change mouse state on click event"""
        if pressed == True:
            self.state[2] |= 1 << MOUSEMAP.get(button)
        else:
            self.state[2] &= ~(1 << MOUSEMAP.get(button))
        self.send_input()

    def on_move(self, x, y):
        """Change mouse state on move event"""
        current = time.monotonic()
        if current - self.last < self.mouse_delay:
            return
        self.last = current
        # relative mouse movements need to be send
        rel_x = x - self.prev_x
        rel_y = y - self.prev_y
        self.prev_x = x
        self.prev_y = y
        self.state[3] = min(127, max(-127, rel_x)) & 255
        self.state[4] = min(127, max(-127, rel_y)) & 255
        self.send_input()

    def on_scroll(self, x, y, dx, dy):
        """Change mouse state on scroll event"""
        print(x, y, dx, dy)

    def event_loop(self):
        """Collect mouse events until released"""
        with MouseListener(
                on_click = self.on_click,
                on_move = self.on_move,
                on_scroll = self.on_scroll) as listener:
            listener.join()

    def __str__(self):
        """Mouse state as string"""
        return repr(self.state)

# main
if __name__ == "__main__":
    print("[*] Intialize mouse")
    mouse = Mouse()

    print("[*] Start event loop ...")
    mouse.event_loop()


