from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element


class HdmiAppPage(BasePage):

    HDMI_APP_PACKAGE_NAME = "com.bmw.hdmiapp"
    HDMI_APP_RESOURCE_ID_PREFIX = HDMI_APP_PACKAGE_NAME + ":id/"

    ACTION_BAR_ROOT_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "action_bar_root")
    ASPECT_RATIO_TV_VIEW_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "aspect_ratio_tv_view")
    NOHDMIINPUTDETECTED_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "noHDMIInputDetected")
    BACKGROUNDIMAGE_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "backgroundImage")
    NOHDMIINFO_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "noHDMiInfo")
    TXTNOHDMIINFO_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "txtNoHDMiInfo")
    TXTCONNECTHDMIINSTRUCTION_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "txtConnectHDMIInstruction")
    INPUTICONBLOCK_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "inputIconBlock")
    LEFTAUDIOJACK_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "leftAudioJack")
    INPUTUSB_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "inputUSB")
    HDMIPLUG_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "hdmiPlug")
    RIGHTAUDIOJACK_ID = Element(By.ID, HDMI_APP_RESOURCE_ID_PREFIX + "rightAudioJack")
