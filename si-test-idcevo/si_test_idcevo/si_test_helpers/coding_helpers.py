import glob
import logging
import re

logger = logging.getLogger(__name__)


def read_vpc_value_from_fa_filename(vehicle_order) -> str:
    """Read VehicleProfileChecksum(VPC) value from FA filename.

    FA filename should be defined with pattern FA_[vehicle_series]_[VPC].xml, and VPC value is Hex value.

    :return str: return read-out vpc hex value in string.
    :raises RuntimeError: if filename does NOT fit the expected pattern.
    """
    match = re.compile(r".*_(?P<vpc>\w+).xml").search(vehicle_order)

    if not match:
        raise RuntimeError("Failed to read VPC value from %s", vehicle_order)

    vpc_value = "0x" + match.group("vpc")
    logger.info("Read out VPC value: %s", vpc_value)
    return vpc_value


def install_coding_fa(test, vehicle_orders, enable_doip_protocol=True):
    """Install coding features

    :param vehicle_orders: str: Path to the folder containing coding features
    :return: List with all the coding features that failed to install
    """
    failed_coding_features = []
    for vehicle_order in vehicle_orders:
        try:
            vpc_value = read_vpc_value_from_fa_filename(vehicle_order)
            test.vcar_manager.set_vpc(vpc_value)
            logger.info("VPC value set to %s", vpc_value)
            test.mtee_target.install_coding(enable_doip_protocol=enable_doip_protocol, vehicle_order=vehicle_order)
        except Exception as e:
            logger.warning(f"Failed to install coding feature {vehicle_order}. Error: {e}")
            failed_coding_features.append(vehicle_order)

    return failed_coding_features


def pdx_setup_class(test, target_name):
    """Setup pdx and svk_all variables for pdx tests"""
    if "rse26" in target_name or "cde" in target_name:
        if "rse26" in target_name:
            pattern = r"[sS][vV][tT]_(RSE).*\.xml$"
        else:
            pattern = r"[sS][vV][tT]_(CDE).*\.xml$"
        svt_regex = re.compile(pattern, re.IGNORECASE)
        # find all files .xml
        all_xml_files = glob.glob("/images/pdx/**/*.xml", recursive=True)
        logger.info("Found the following xml files: %s", all_xml_files)
        for file in all_xml_files:
            if svt_regex.search(file):
                svk_all = file
                pdx = glob.glob("/images/pdx/*.pdx")[0]
                break
        else:
            raise RuntimeError("Required SVT files not found under the specified pattern.")
    else:
        pdx = glob.glob(f"/images/pdx/{target_name.upper()}_*.pdx")[0]
        svk_all = test.mtee_target.pdx_svt_file
        logger.info("Use SVT file %s", svk_all)
    return pdx, svk_all
