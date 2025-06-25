from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import Element
from si_test_apinext.idc23.pages.launcher_page import LauncherPage


class TopRightStatusBarPage(LauncherPage):

    PACKAGE_NAME = "com.android.systemui"
    STATUS_BAR_ID_PREFIX = PACKAGE_NAME + ":id/"

    STATUSBAR_NOTIFICATION_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "statusbar_notification_icons")
    MUTE_ICON_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "mute")
    NAVIGATION_BAR_FRAME_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "navigation_bar_frame")
    CAR_TOP_BAR_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "car_top_bar")
    BMW_STATUSBAR_SHADOW_VIEW_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "bmw_statusbar_shadow_view")
    NO_TOUCH_AREA_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "no_touch_area")
    RIGHT_STATUS_BAR_AREA_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "right_status_bar_area")
    REDUCIBLE_ICON_AREA_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "reducible_icon_area")
    NOTIFICATION_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "notification")
    MEDIA_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "media")
    ICON_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "icon")
    NETWORK_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "network")
    USER_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "user")
    USER_IMAGE_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "user_image")
    CLOCK_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "clock")
    GOOGLE_CLOCK_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "google_clock")
    TIME_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "time")
    AM_PM_ID = Element(By.ID, STATUS_BAR_ID_PREFIX + "am_pm")
