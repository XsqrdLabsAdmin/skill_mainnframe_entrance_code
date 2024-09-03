import subprocess
import requests 
from ovos_bus_client.message import Message
from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler, skill_api_method


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

    @intent_handler("add_user.intent")
    def handle_add_user(self, message: Message):
        """
        Handle adding a new user with an entrance code, only if the active user is the admin
        """
        if self.active_user != self.admin_user:
            self.speak_dialog("admin_only")
            return
        
        user = self.get_response("What is the name of the user?")
        entrance_code = self.get_response("Dictate a pass code please.")
        
        if user and entrance_code:
            self.settings["entrance_codes"][user] = entrance_code
            self.speak_dialog("user_added", {"user": user})
        else:
            self.speak_dialog("operation_failed")

    @intent_handler("remove_user.intent")
    def handle_remove_user(self, message: Message):
        """
        Handle removing an existing user, only if the active user is the admin
        """
        if self.active_user != self.admin_user:
            self.speak_dialog("admin_only")
            return
        
        user = self.get_response("get_user_name_to_remove")

        if user in self.entrance_codes:
            del self.settings["entrance_codes"][user]
            self.speak_dialog("user_removed", {"user": user})
        else:
            self.speak_dialog("user_not_found", {"user": user})

    @intent_handler("login_user.intent")
    def handle_login_user(self, message: Message):
        """
        Handle user login
        """
        self.authenticate_user()

    @intent_handler("logout_user.intent")
    def handle_logout_user(self, message: Message):
        """
        Handle logging out the current user
        """
        self.active_user = ""
        self.speak_dialog("user_logged_out")

    def authenticate_user(self):
        user_code = self.get_response("entrance_code")

        if self.attempts < 3:
            for user, entrance_code in self.entrance_codes.items():
                if user_code.lower().replace(".", "") == entrance_code:
                    self.speak_dialog("valid_code", data={"user": user})
                    self.active_user = user
                    self.voice_on()
                    self.connect_to_spotify()
                    return
            if not self.active_user:
                self.speak_dialog("wrong_code", data={"code": user_code})
                self.attempts += 1
                self.authenticate_user()
        else:
            self.speak_dialog("shutdown")
            self.bus.emit(Message("system.shutdown"))
            self.attempts = 1

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
        self.speak_dialog("Turning on the voice changer.")  # Vocal response for starting the voice changer
        requests.get("http://192.168.0.238:8000/start")
        self.speak_dialog("Voice changer on.")
    
    def shutdown(self):
        """
        Override shutdown to reset skill state or save data if necessary
        """
        self.active_user = ""
        super().shutdown()