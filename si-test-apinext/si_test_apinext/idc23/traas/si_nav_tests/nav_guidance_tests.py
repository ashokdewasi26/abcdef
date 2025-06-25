# Copyright (C) 2023. BMW Car IT. All rights reserved.
import logging

from mtee.testing.test_environment import require_environment, require_environment_setup, TEST_ENVIRONMENT as TE
from si_test_apinext.idc23 import HMI_BUTTONS_REF_IMG_PATH
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.navigation_page import NavigationPage as Navi
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.hmi_helper import HMIhelper
from si_test_apinext.util.mtee_utils import MteeUtils

logger = logging.getLogger(__name__)
REQUIREMENTS = TE.target_type.hu, TE.test_bench.rack


@require_environment(*REQUIREMENTS)
class TestNaviGuidance:
    hmi_buttons_ref_img_path = HMI_BUTTONS_REF_IMG_PATH

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.hmihelper = HMIhelper(cls.test, cls.hmi_buttons_ref_img_path)
        cls.mtee_util.change_language("en_GB")
        utils.start_recording(cls.test)
        Navi.go_to_navigation()
        Navi.activate_demo_mode(cls.test, cls.hmihelper, "TestNaviGuidance")

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        Navi.stop_route_guidance()
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestNaviGuidance")
        cls.test.quit_driver()

    def setup(self):
        Launcher.go_to_home()
        Navi.go_to_navigation()

    @utils.gather_info_on_fail
    def test_00_start_poi_guidance(self):
        """
        Start and stop poi guidance

        Steps:
        1. Go inside navigation.
        2. Validate maps are loaded correctly.
        3. Enable demo mode.
        4. Select poi from the list and expect poi suggestions.
        5. Start guidance and validate guidance is active.
        6. Stop guidance and validate guidance is stopped.

        Traceability: ABPI-236221, ABPI-236223
        """
        Navi.select_poi()
        Navi.start_guidance()
        Navi.stop_route_guidance()

    @utils.gather_info_on_fail
    def test_01_start_guidance(self):
        """
        Start and stop guidance

        Steps:
        1. Go inside navigation.
        2. Validate maps are loaded correctly.
        3. Enable demo mode.
        4. Go to search destination screen.
        5. Enter destination, and expect destination suggestions.
        6. Start guidance and validate guidance is active.
        7. Stop guidance and validate guidance is stopped.

        Traceability: ABPI-236221, ABPI-236223
        """
        Navi.search_destination()
        Navi.select_route()
        Navi.start_guidance()
        Navi.stop_route_guidance()

    @utils.gather_info_on_fail
    def test_02_start_guidance(self):
        """
        Add & remove intermediate destination

        Steps:
        1. Go inside navigation.
        2. Validate maps are loaded correctly.
        3. Enable demo mode.
        4. Go to search destination screen.
        5. Enter destination, and expect destination suggestions.
        6. Start guidance and validate guidance is active.
        7. Enter intermediate destination to active guidance and validate destination is added.
        7. Remove intermediate destination to from guidance and validate destination is removed.
        8. Stop guidance and validate guidance is stopped.

        Traceability: ABPI-361231, ABPI-361238
        """
        Navi.search_destination(destination="Ulm Hbf")
        Navi.select_route()
        Navi.start_guidance()
        Navi.add_intermediate_dest()
        Navi.remove_intermediate_dest()
        Navi.stop_route_guidance()
