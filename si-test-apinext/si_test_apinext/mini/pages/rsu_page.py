from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element


class RSUPage(BasePage):
    # RSU
    RSU_PACKAGE_NAME = "com.bmwgroup.apinext.rsuapp"
    RSU_PACKAGE_PREFIX = RSU_PACKAGE_NAME + ":id/"
    CONTAINER_ID = Element(By.ID, RSU_PACKAGE_PREFIX + "container")
