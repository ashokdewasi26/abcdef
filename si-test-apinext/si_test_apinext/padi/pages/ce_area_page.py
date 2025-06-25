import logging

from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import BasePage, Element


logger = logging.getLogger(__name__)


class CEAreaPage(BasePage):

    CE_AREA_PACKAGE_NAME = "com.bmwgroup.padi.cearea"
    CE_AREA_RESOURCE_ID_PREFIX = CE_AREA_PACKAGE_NAME + ":id/"
    # CE_AREA elements resource ID / locators
    CE_AREA_VIDEO_ID = Element(By.ID, CE_AREA_RESOURCE_ID_PREFIX + "video")
    CE_AREA_EXPAND_BUTTON_ID = Element(By.ID, CE_AREA_RESOURCE_ID_PREFIX + "expandCollapseButton")

    # CE_AREA NOT FOCUSED
    CE_AREA_NOT_FOCUSED_ID = Element(By.ID, "com.bmwgroup.padi:id/centralArea")

    # Disable CE_Area
    CE_AREA_DISABLE = "com.bmwgroup.padi.test.event --es TYPE DISABLE_FIRE_TV"
    CE_AREA_ENABLE = "com.bmwgroup.padi.test.event --es TYPE ENABLE_FIRE_TV"
    DISABLE_HDMI = "com.bmwgroup.padi.test.event --es TYPE DISABLE_HDMI"

    # Screen Pop-Up
    POP_UP_ID = Element(By.ID, "com.bmwgroup.rse.system.service:id/dialogContent")
    POP_UP_ID_PU = Element(By.ID, "com.bmwgroup.rse.system.service:id/dialog_content")

    CHILD_LOCK_POP_UP_ID = Element(By.ID, "com.bmwgroup.padi:id/popupDescription")
    CHILD_LOCK_POP_UP_ID_PU = Element(By.ID, "com.bmwgroup.padi:id/popup_description")

    all_ce_area_elements = [CE_AREA_VIDEO_ID]

    CE_AREA_CENTER_COORDS = (3840, 1080)

    cearea_bounds_popups = (2920, 1810, 4760, 2016)

    @classmethod
    def stop_cearea_package(cls):
        cls.apinext_target.execute_command(["am", "broadcast", "-a", cls.CE_AREA_DISABLE])

    @classmethod
    def stop_hdmi_animation(cls):
        cls.apinext_target.execute_command(["am", "broadcast", "-a", cls.DISABLE_HDMI])

    @classmethod
    def enable_interaction(cls):
        """
        Enable interactions with CE_AREA elements
        By sending the  tap event, we will focus on ce area activity
        and  the UI automator will be able to find CE_AREA views
        and interact with it's elements
        """

        try:
            elem = cls.wb.until(
                ec.visibility_of_element_located(cls.CE_AREA_NOT_FOCUSED_ID),
                f"Error while validating CEArea element presence: {cls.CE_AREA_NOT_FOCUSED_ID.selector}",
            )
            elem.click()
        except NoSuchElementException:
            logger.warning("Did not found centralArea elem")
            pass

    @classmethod
    def validate_all_ce_area_elems(cls):
        """Validate presence of all CE_AREA elements"""
        for element in cls.all_ce_area_elements:
            cls.wb.until(
                ec.presence_of_element_located(element),
                f"Error while validating CEArea element presence: {element.selector}",
            )
        return True

    @classmethod
    def get_elem_bounds(cls, elem):
        """
        Find element and return it's bounds

        Args:
            elem - Element (namedtuple) object

        Returns:
            String with element bounds with the structure:
            '[x_start, y_start][x_end, y_end]'
        """
        return super(CEAreaPage, cls).get_elem_bounds(elem)

    @classmethod
    def go_to_home(cls):
        """
        Go to Home and checks that Menu Bar and Widget Area are present

        Raises:
            TimeoutException - If it was unable to find element with id: 'elem_id'
        """
        cls.driver.keyevent(AndroidGenericKeyCodes.KEYCODE_HOME)
        cls.enable_interaction()
        cls.validate_all_ce_area_elems()
