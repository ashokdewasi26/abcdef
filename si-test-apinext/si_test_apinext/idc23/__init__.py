"""SI test tools and helpers for IDC Android"""
__version__ = "1.00"

from pathlib import Path

REF_IMAGES_PATH = Path(__file__).parent / "si_tests_mtee" / "ref_images"

IC_HMI_REF_IMG_PATH = Path(REF_IMAGES_PATH / "ic_hmi")
HMI_BUTTONS_REF_IMG_PATH = Path(REF_IMAGES_PATH / "hmi_buttons")
MFL_REF_IMG_PATH = Path(REF_IMAGES_PATH / "mfl")
EXTERIOR_LIGHT_REF_IMG_PATH = Path(REF_IMAGES_PATH / "exterior_light")
INTERIOR_LIGHT_REF_IMG_PATH = Path(REF_IMAGES_PATH / "interior_light")


AUDIO_REF_IMAGES_PATH = Path(__file__).parent / "traas" / "ref_images" / "audio_test"
CLIMATE_REF_IMG_PATH = Path(__file__).parent / "traas" / "climate_test" / "ref_images"

AUDIO_SAMPLES_PATH = Path(__file__).parent / "traas" / "speech" / "ref_audio"

# There is a Limit of STRs in a row we can do
# When the limit is reached a cold boot is expected to happen
STR_LIMIT = 160
