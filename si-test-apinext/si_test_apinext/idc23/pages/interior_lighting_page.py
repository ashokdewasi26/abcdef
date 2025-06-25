from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element


class InteriorLighting(BasePage):

    # Interior Lighting app
    PACKAGE_NAME = "com.bmwgroup.apinext.interiorlight"
    INTLIGHT_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".MainActivity"

    DISPLAY_SUBMENU_TITLE_ID = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "statusbar_title")

    TYRE_ID = Element(By.XPATH, "//*[@text='Tyre Pressure Monitor']")
    INTERIOR_LIGHTING_SUBMENU_TITLE = "INTERIOR LIGHTING"
    READING_LIGHT = Element(By.XPATH, "//*[@text='Reading light']")
    READING_LIGHT_TITLE = ["READING LIGHT", INTERIOR_LIGHTING_SUBMENU_TITLE]
    AMBIENT_LIGHTING = Element(By.XPATH, "//*[@text='Ambient lighting']")
    AMBIENT_LIGHTING_TITLE = ["AMBIENCE", INTERIOR_LIGHTING_SUBMENU_TITLE]
    VEHICLE_DASHBOARD_BRIGHTNESS = Element(
        By.XPATH, "//*[contains(@text, 'Cockpit Brightness') or contains(@text, 'Cockpit brightness')]"
    )
    DASHBOARD_BRIGHTNESS_TITLE = ["COCKPIT BRIGHTNESS AT NIGHT", INTERIOR_LIGHTING_SUBMENU_TITLE]
    LIGHTWHENOPENDOOR = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "lightWhenOpenDoor")
    SPOTLIGHTDR = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "spotLightDr")
    SPOTLIGHTPS = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "spotLightPs")
    MAINLIGHT = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "mainLight")
    SPOTLIGHTDR2ND = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "spotLightDr2nd")
    SPOTLIGHTPS2ND = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "spotLightPs2nd")
    DRIVERBRIGHTNESS = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "spotLightDriverBrightness")
    PASSENGERBRIGHTNESS = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "spotLightPassengerBrightness")
    DRIVER2NDBRIGHTNESS = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "spotLightDriver2ndBrightness")
    PASSENGER2NDBRIGHTNESS = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "spotLightPassenger2ndBrightness")
    SPOTLIGHT_OFF = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "item_lightstate")
    SPOTLIGHT_ON = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "item_glow")
    BRIGHTNESS_SLIDER = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "list_item_slider_content_main")

    AMBIENT_LIGHT_TOGGLE = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "main_ambient_light_toggle")
    AMBIENT_LIGHT_COLOR = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "color")
    COLOR_02 = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "color_02")
    COLOR_12 = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "color_12")
    COLOR_TEXT = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "item_text")
    COLOR_IMAGE = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "item_image")
    BACKGROUND_LIGHT_SEEKBAR = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "background_light_seekbar")
    ACCENT_LIGHTING_SEEKBAR = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "accent_lighting_seekbar")
    REDUCED_FOR_NIGHT_DRIVING_TOGGLE = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "reduced_for_night_driving_toggle")
    LIGHTING_EVENTS = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "localbglayer")
    LIGHTING_EVENTS_TITLE = ["LIGHTING EVENTS", "LIGHTING EFFECTS"]
    ALERT_OPTION = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "alert")
    LOCK_OPTION = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "lock")
    CALL_OPTION = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "call")
    WCA_OPTION = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "wca")
    SIDE_NAVIGATION_BACK_ARROW = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "side_navigation_back_arrow")

    COCKPIT_BRIGHTNESS_SEEKBAR = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "cockpit_brightness_seekbar")
    TOGGLE_BUTTON = Element(By.ID, INTLIGHT_RESOURCE_ID_PREFIX + "button_icon")

    WELCOME_OPTION = Element(
        By.XPATH,
        "//*[contains(@resource-id,'com.bmwgroup.apinext.interiorlight:id/contentScroller')and @index='0']"
        "//*[contains(@class,'android.view.ViewGroup') and @index='0']",
    )

    # Tap Coordinates
    bg_light_coords = {
        "min": {"coords": (230, 480), "steps": 10},
        "mid": {"coords": (940, 480), "steps": 5},
        "max": {"coords": (930, 480), "steps": 10},
    }
    acc_light_coords = {
        "min": {"coords": (230, 690), "steps": 10},
        "mid": {"coords": (940, 690), "steps": 5},
        "max": {"coords": (940, 690), "steps": 10},
    }
    cockpit_brightness_coords = {
        "min": {"coords": (230, 342), "steps": 10},
        "mid": {"coords": (1756, 342), "steps": 5},
        "max": {"coords": (1756, 342), "steps": 10},
    }
    back_button = (90, 455)

    # Swipe
    swipe_to_end = (770, 620, 770, 300)

    @classmethod
    def get_option_button(cls, option):
        """
        Get the toggle button in the wanted option.

        param: option - Android id of the option
        """
        option_element = cls.driver.find_element(*option)
        button = option_element.find_element(*cls.TOGGLE_BUTTON)
        return button
