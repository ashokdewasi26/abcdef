from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element


class DeskclockPage(BasePage):

    # Deskclock Package
    DESKCLOCK_RESOURCE_ID_PREFIX = "com.android.deskclock:id/"
    ANALOG_CLOCK_WIDGET_ID = Element(By.ID, DESKCLOCK_RESOURCE_ID_PREFIX + "analog_appwidget")
    DIGITAL_CLOCK_WIDGET_ID = Element(By.ID, DESKCLOCK_RESOURCE_ID_PREFIX + "digital_widget")
    DIGITAL_CLOCK_ID = Element(By.ID, DESKCLOCK_RESOURCE_ID_PREFIX + "digital_clock")
