from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

"""
This class waits for an element with a specified time
If timeout is reached it throws an exception
"""


class WaitForElement:
    @staticmethod
    def wait(driver, id, time_out=100):
        try:
            WebDriverWait(driver, time_out).until(lambda driver: driver.find_element(*id))
        except TimeoutException:
            print("Not able to find ID:" + id)
