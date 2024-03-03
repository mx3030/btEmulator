import dbus
import dbus.service
from pynput.keyboard import Listener as KeyboardListener
from keyboard_mapping import *

class Keyboard():
    """Emulated keyboard"""

    def __init__(self):
        # state structure of the emulated Bluetooth keyboard
        self.state = [
            0xA1,       # input report
            0x01,       # usage report : keyboard
            0x00,       # modifier byte
            0x00,       # Vendor reserved
            0x00,       # 6 bytes for key codes
            0x00,
            0x00,
            0x00,
            0x00,
            0x00]

        self.pressed_key_count = 0              # initialize keypress counter
        self.keymap = KEYMAP_GERMAN             # set keymap

        # initialize D-Bus client
        print("[*] Initialize D-Bus keyboard client")
        self.bus = dbus.SystemBus()
        self.btkservice = self.bus.get_object("org.btEmulator.btkbservice", "/org/btEmulator/btkbservice")
        self.iface = dbus.Interface(self.btkservice, "org.btEmulator.btkbservice")
    
    def send_input(self):
        """Forward keyboard events to the D-Bus service"""
        modifier_byte = self.state[2]
        self.iface.send_keys(self.state)

    def change_state(self, keydata, keypress=True):
        """Change keyboard state"""

        print("key count {}".format(self.pressed_key_count))

        if keypress:
            if keydata[0] != MODIFIER_NONE and keydata[1] != KEY_NONE:
                if keydata[1] not in self.state[4:]:
                    # increase key count
                    self.pressed_key_count += 1

                    # find free key slot
                    i = self.state[4:].index(0)

                    # set key
                    self.state[4 + i] = keydata[1]
                    print("Key press {}".format(keydata[1]))

                self.state[2] = keydata[0]


            elif keydata[1] != KEY_NONE:
                if keydata[1] not in self.state[4:]:
                    # increase key count
                    self.pressed_key_count += 1

                    # find free key slot
                    i = self.state[4:].index(0)

                    # set key
                    self.state[4 + i] = keydata[1]
                    print("Key press {}".format(keydata[1]))

            elif keydata[0] != MODIFIER_NONE and keydata[1] == KEY_NONE:
                # process modifier keys
                print("{} pressed".format(keydata[0]))

                self.state[2] |= keydata[0]
                print("Modify modifier byte {}".format(self.state[2]))

        else:
            if keydata[1] != KEY_NONE:
                # decrease keypress count
                self.pressed_key_count -= 1
                print("Key release {}".format(keydata[1]))

                # update state
                i = self.state[4:].index(keydata[1])
                self.state[4 + i] = 0

            if keydata[0] != MODIFIER_NONE:
                print("{} released".format(keydata[0]))
                self.state[2] &= ~keydata[0]

        print(self)
        self.send_input()

    def on_press(self, key):
        """Change keyboard state on key presses"""
        if self.pressed_key_count < 6:
            # set state of newly pressed key but consider limit of max. 6 keys
            # pressed at the same time
            try:
                # process printable characters
                k = self.keymap[key.char]

                # change keyboard state
                self.change_state(k)
            except AttributeError:
                # process special keys
                k = KEYMAP_SPECIAL_CHARS[key]

                # change keyboard state
                self.change_state(k)
            except KeyError:
                print("KeyError: {}".format(key))

    def on_release(self, key):
        """Change keyboard state on key releases"""

        try:
            # process printable characters
            k = self.keymap[key.char]

            # change keyboard state
            self.change_state(k, False)
        except AttributeError:
            # process special keys
            k = KEYMAP_SPECIAL_CHARS[key]

            # change keyboard state
            self.change_state(k, False)
        except KeyError:
            print(key)
 
    def event_loop(self):
        """Collect keyboard events until released"""

        with KeyboardListener(
                on_press=self.on_press,
                on_release=self.on_release) as listener:
            listener.join()

    def __str__(self):
        """Keyboard state as string"""
        return repr(self.state)


if __name__ == "__main__":
    print("[*] Intialize keyboard")
    keyboard = Keyboard()

    print("[*] Start event loop ...")
    keyboard.event_loop()
