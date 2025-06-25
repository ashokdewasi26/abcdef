from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element


class ExteriorLightPage(BasePage):

    # Exterior Lighting app
    PACKAGE_NAME = "com.bmwgroup.apinext.exteriorlight"
    EXTLIGHT_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".MainActivity"

    ADDITIONAL_SETTINGS = Element(
        By.XPATH, "//*[contains(@text, 'Settings') or contains(@text, 'Additional settings')]"
    )
    REAR_LIGHTS = Element(By.ID, EXTLIGHT_RESOURCE_ID_PREFIX + "daytimeDrivingLightsRear")
    ONE_TOUCH_INDICATOR = Element(By.ID, EXTLIGHT_RESOURCE_ID_PREFIX + "oneTouchIndicator")
    TOUCH_INDICATOR = Element(By.XPATH, "//*[contains(@text, 'Once') or contains(@text, '3 times')]")
    RADIO_BUTTON = Element(By.ID, EXTLIGHT_RESOURCE_ID_PREFIX + "item_radioButton")
    RIGHT_LEFT = Element(By.ID, EXTLIGHT_RESOURCE_ID_PREFIX + "touristLight")
    TRAFFIC_INDICATOR = Element(
        By.XPATH, "//*[contains(@text, 'Right-hand traffic') or contains(@text, 'Left-hand traffic')]"
    )
    POPUP_ID = Element(By.ID, EXTLIGHT_RESOURCE_ID_PREFIX + "popup_background")
    WELCOME_LIGHT = Element(By.ID, EXTLIGHT_RESOURCE_ID_PREFIX + "welcomeLight")
    FOLLOW_HOME_DURATION = Element(By.ID, EXTLIGHT_RESOURCE_ID_PREFIX + "followMeHomeDuration")
    TOGGLE_BUTTON = Element(By.ID, EXTLIGHT_RESOURCE_ID_PREFIX + "button_icon")

    # Tap Coordinates
    home_light_coords_pu2403 = {
        "min": {"coords": (230, 675), "steps": 24},
        "mid": {"coords": (1747, 675), "steps": 11},
        "max": {"coords": (1747, 675), "steps": 24},
    }
    home_light_coords = {
        "min": {"coords": (228, 556), "steps": 24},
        "mid": {"coords": (1742, 556), "steps": 11},
        "max": {"coords": (1742, 556), "steps": 24},
    }
    tap_out = (1880, 530)

    # Swipe
    swipe_to_end_pu2403 = (770, 620, 770, 300)
    swipe_to_end = (770, 820, 770, 300)
