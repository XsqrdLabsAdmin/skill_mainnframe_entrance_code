import subprocess
import requests
from ovos_bus_client.message import Message
from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler, skill_api_method
import os
from time import sleep


class BootFinishedSkill(OVOSSkill):
    def __init__(self, *args, bus=None, skill_id="", **kwargs):
        super().__init__(*args, bus=bus, skill_id=skill_id, **kwargs)
        self.attempts = 1
        self.active_user = ""
        self.admin_user = "Jay"  # Replace with your actual username
        self.add_event("mycroft.ready", self.handle_ready)
        self.start_wake()
        self.authenticate_user()

    @property
    def entrance_codes(self):
        return self.settings.get("entrance_codes") or {}

    @property
    def speak_ready(self):
        """
        Speak `ready` dialog when ready unless disabled in settings
        """
        return self.settings.get("speak_ready", True)

    @property
    def ready_sound(self):
        """
        Play sound when ready unless disabled in settings
        """
        return self.settings.get("ready_sound", True)

    @skill_api_method
    def get_active_user(self):
        return self.active_user

    def handle_ready(self, message: Message):
        """
        Handle mycroft.ready event. Notify the user everything is ready if
        configured.
        """
        if self.ready_sound:
            self.acknowledge()
        self.enclosure.eyes_on()
        if self.speak_ready:
            self.speak_dialog("ready")
        else:
            self.log.debug("Ready notification disabled in settings")
        self.enclosure.eyes_blink("b")
        if self.entrance_codes:
            self.authenticate_user()
        else:
            self.log.warning(
                f"No entrance codes configured, please add them in the skill settings at {self.settings.path}"
            )

    @intent_handler("enable_ready_notification.intent")
    def handle_enable_notification(self, message: Message):
        """
        Handle a request to enable ready announcements
        """
        self.settings["speak_ready"] = True
        self.speak_dialog("confirm_speak_ready")

    @intent_handler("disable_ready_notification.intent")
    def handle_disable_notification(self, message: Message):
        """
        Handle a request to disable ready announcements
        """
        self.settings["speak_ready"] = False
        self.speak_dialog("confirm_no_speak_ready")

    def authenticate_user(self):
        user_code = self.get_response("entrance_code")

        if self.attempts < 3:
            for user, entrance_code in self.entrance_codes.items():
                if user_code.lower().replace(".", "") == entrance_code:
                    self.speak_dialog("valid_code", data={"user": user})
                    self.active_user = user
                    try:
                        self.phone_on()
                    except:
                        print("Could not turn on the phone")
                    try:
                        self.voice_on()
                    except:
                        self.speak_dialog("Could not turn on the voice changer")

                    try:
                        self.connect_to_spotify()
                    except:
                        print("Could not connect to Spotify")
                    return
            if not self.active_user:
                self.speak_dialog("wrong_code", data={"code": user_code})
                self.attempts += 1
                self.authenticate_user()
        else:
            self.speak_dialog("shutdown")
            self.bus.emit(Message("system.shutdown"))
            self.attempts = 1

    def phone_on(self):
        try:
            self.speak_dialog(
                "Turning on the phone."
            )  # Vocal response for starting the phone
            os.system("bash /home/ovos/phone-scripts/phone-restart")
        except:
            self.speak_dialog("Could not turn on the phone")

    def connect_to_spotify(self):
        self.speak_dialog("spotify_connecting")
        with subprocess.Popen(
            ["spotify-up"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as process:
            out, err = process.communicate()
            if out:
                self.log.info(out.strip())
                self.speak_dialog("spotify_connected")
            if err:
                self.log.error(err.strip())

    def start_wake(self):
        self.speak_dialog("Starting wake word")
        with subprocess.Popen(
            ["mainnframe_voice-up"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as process:
            out, err = process.communicate()
            if out:
                self.log.info(out.strip())
            if err:
                self.log.error(err.strip())

    def voice_on(self):
        try:
            self.speak_dialog(
                "Turning on the voice changer."
            )  # Vocal response for starting the voice changer
            response = requests.post("http://192.168.0.238:8000/start", timeout=3)
            response.raise_for_status()

            message = response.json()
            self.speak_dialog(message["message"])
        except:
            raise Exception("Could not turn on the voice changer")

    @intent_handler("shutdown.intent")
    def handle_shutdown(self, message: Message):
        """
        Handle a request to shutdown the system
        """
        self.speak_dialog("System shutting down... Goodbye!")
        sleep(5)
        try:
            response = requests.post("http://192.168.0.238:8000/shutdown", timeout=3)
            response.raise_for_status()
            message = response.json()
            self.speak_dialog(message["message"])
        except:
            self.speak_dialog("Could not turn off the voice changer")
        sleep(5)
        self.bus.emit(Message("system.shutdown"))
