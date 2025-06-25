"""SI test tools and helpers for  RSE PaDi"""
__version__ = "1.00"


from pathlib import Path

REF_IMAGES_PATH = Path(__file__).parent / "si_tests_mtee" / "ref_images"
LAUNCHER_REF_IMAGES_PATH = Path(__file__).parent / "si_tests_mtee" / "launcher_reference_images"
DISPLAY_REF_IMAGES_PATH = Path(__file__).parent / "si_tests_mtee" / "check_display" / "ref_images"
