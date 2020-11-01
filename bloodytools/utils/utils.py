import argparse
import datetime
import logging
import os
import re
import requests
import time
import urllib3

from bloodytools import settings
from simc_support.game_data.Talent import get_talent_dict
from simc_support.game_data.WowSpec import WowSpec
from simc_support.game_data.WowClass import WowClass

logger = logging.getLogger(__name__)


def create_basic_profile_string(wow_spec: WowSpec, tier: str, settings: object):
    """Create basic profile string to get the standard profile of a spec. Use this function to get the necessary string for your first argument of a simulation_data object.

    Arguments:
      wow_spec {WowSpec} -- wow spec, e.g. elemental shaman
      tier {str} -- profile tier, e.g. 21 or PR
      settings {object}

    Returns:
      str -- relative link to the standard simc profile
    """

    logger.debug("create_basic_profile_string start")
    # create the basis profile string
    split_path: list = settings.executable.split("simc")
    if len(split_path) > 2:
        # the path contains multiple "simc"
        basis_profile_string: str = "simc".join(split_path[:-1])
    else:
        basis_profile_string: str = split_path[0]

    # fix path for linux users
    if basis_profile_string.endswith("/engine/"):
        split_path = basis_profile_string.split("/engine/")
        if len(split_path) > 2:
            basis_profile_string = "/engine/".join(split_path[:-1])
        else:
            basis_profile_string = split_path[0] + "/"

    basis_profile_string += "profiles/"
    if tier == "PR":
        basis_profile_string += "PreRaids/PR_{}_{}".format(
            wow_spec.wow_class.simc_name.title(), wow_spec.simc_name.title()
        )
    else:
        basis_profile_string += "Tier{}/T{}_{}_{}".format(
            tier, tier, wow_spec.wow_class.simc_name, wow_spec.simc_name
        ).title()
    basis_profile_string += ".simc"

    logger.debug("Created basis_profile_string '{}'.".format(basis_profile_string))
    logger.debug("create_basic_profile_string ended")
    return basis_profile_string


def pretty_timestamp() -> str:
    """Returns a pretty time stamp "YYYY-MM-DD HH:MM"

    Returns:
      str -- timestamp
    """
    # str(datetime.datetime.utcnow())[:-10] should be the same
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")


def extract_profile(path: str, wow_class: WowClass, profile: dict = None) -> dict:
    """Extract all character specific data from a given file.

    Arguments:
        path {str} -- path to file, relative or absolute
        profile {dict} -- profile input that should be updated

    Returns:
        dict -- all known character data
    """

    if os.stat(path).st_size == 0:
        raise ValueError("Empty file")

    if not profile:
        profile = {}

    if not "character" in profile:
        profile["character"] = {}

    profile["character"]["class"] = wow_class.simc_name

    # prepare regex for each extractable slot
    item_slots = [
        "head",
        "neck",
        "shoulders",
        "shoulder",
        "back",
        "chest",
        "wrists",
        "wrist",
        "hands",
        "waist",
        "legs",
        "feet",
        "finger1",
        "finger2",
        "trinket1",
        "trinket2",
        "main_hand",
        "off_hand",
    ]
    unified_slot_names = {"shoulder": "shoulders", "wrist": "wrists"}
    pattern_slots = {}
    for element in item_slots:
        pattern_slots[element] = re.compile(
            '^{}="?([a-z0-9_=,/:.]*)"?$'.format(element)
        )

    # prepare regex for item defining attributes
    item_elements = [
        "id",
        "bonus_id",
        "azerite_powers",
        "enchant",
        "azerite_level",  # neck
        "ilevel",
        "gem_id",
        "enchant_id",
    ]
    pattern_element = {}
    # don't recompile this for each slot
    for element in item_elements:
        pattern_element[element] = re.compile(',{}="?([a-z0-9_/:]*)"?'.format(element))

    # prepare regex for character defining information. like spec
    character_specifics = [
        "level",
        "race",
        "role",
        "position",
        "talents",
        "spec",
        "azerite_essences",
        "covenant",
        "soulbind",
    ]
    pattern_specifics = {}
    for element in character_specifics:
        pattern_specifics[element] = re.compile(
            '^{}="?([a-z0-9_./:]*)"?$'.format(element)
        )

    with open(path, "r") as f:
        for line in f:
            for specific in character_specifics:

                matches = pattern_specifics[specific].search(line)
                if matches:
                    profile["character"][specific] = matches.group(1)

            for slot in item_slots:

                if not "items" in profile:
                    profile["items"] = {}

                matches = pattern_slots[slot].search(line)
                # slot line found
                slot_name = slot
                if slot_name in unified_slot_names:
                    slot_name = unified_slot_names[slot_name]
                if matches:
                    new_line = matches.group(1)
                    if not slot_name in profile:
                        profile["items"][slot_name] = {}

                    # allow pre-prepared profiles to get emptied if input wants to overwrite with empty
                    # 'head=' as a head example for an empty overwrite
                    if not new_line:
                        profile["items"].pop(slot_name, None)

                    # check for all elements
                    for element in item_elements:
                        new_matches = pattern_element[element].search(new_line)
                        if new_matches:
                            profile["items"][slot_name][element] = new_matches.group(1)

    logger.debug(f"extracted profile: {profile}")

    return profile


def create_base_json_dict(
    data_type: str, wow_spec: WowSpec, fight_style: str, settings: object
):
    """Creates as basic json dictionary. You'll need to add your data into 'data'. Can be extended.

    Arguments:
      data_type {str} -- e.g. Races, Trinkets, Azerite Traits (str is used in the title)
      wow_class {str} -- [description]
      wow_spec {str} -- [description]
      fight_style {str} -- [description]

    Returns:
      dict -- [description]
    """

    logger.debug("create_base_json_dict start")

    timestamp = pretty_timestamp()

    profile_location = create_basic_profile_string(wow_spec, settings.tier, settings)

    try:
        profile = extract_profile(profile_location, wow_spec.wow_class)
    except FileNotFoundError:
        profile = None

    if settings.custom_profile:
        try:
            profile = extract_profile("custom_profile.txt", wow_spec.wow_class, profile)
        except ValueError:
            profile = None

    if not profile:
        raise FileNotFoundError("No profile found or provided.")

    # spike the export data with talent data
    talent_data = get_talent_dict(wow_spec, settings.ptr == "1")

    # add class/ id number
    class_id = wow_spec.wow_class.id
    spec_id = wow_spec.id

    subtitle = "UTC {timestamp}".format(timestamp=timestamp)
    if settings.simc_hash:
        subtitle += ' | SimC build: <a href="https://github.com/simulationcraft/simc/commit/{simc_hash}" target="blank">{simc_hash_short}</a>'.format(
            simc_hash=settings.simc_hash, simc_hash_short=settings.simc_hash[0:7]
        )

    return {
        "data_type": "{}".format(data_type.lower().replace(" ", "_")),
        "timestamp": timestamp,
        "title": "{data_type} | {wow_spec} {wow_class} | {fight_style}".format(
            data_type=data_type.title(),
            wow_class=wow_spec.wow_class.full_name,
            wow_spec=wow_spec.full_name,
            fight_style=fight_style.title(),
        ),
        "subtitle": subtitle,
        "simc_settings": {
            "tier": settings.tier,
            "fight_style": fight_style,
            "iterations": settings.iterations,
            "target_error": settings.target_error.get(fight_style, "0.1"),
            "ptr": settings.ptr,
            "simc_hash": settings.simc_hash,
            # deprecated
            "class": wow_spec.wow_class.simc_name,
            # deprecated
            "spec": wow_spec.simc_name,
        },
        "data": {},
        "translations": {},
        "profile": profile,
        "talent_data": talent_data,
        "class_id": class_id,
        "spec_id": spec_id,
    }


def tokenize_str(string: str) -> str:
    """Return SimulationCraft appropriate name.

    Arguments:
      string {str} -- E.g. "Tawnos, Urza's Apprentice"

    Returns:
      str -- "tawnos_urzas_apprentice"
    """

    string = string.lower().split(" (")[0]
    # cleanse name
    if (
        "__" in string
        or " " in string
        or "-" in string
        or "'" in string
        or "," in string
    ):
        return tokenize_str(
            string.replace("'", "")
            .replace("-", "")
            .replace(" ", "_")
            .replace("__", "_")
            .replace(",", "")
        )

    return string


def get_simc_hash(path) -> str:
    """Get the FETCH_HEAD or shallow simc git hash.

    Returns:
      str -- [description]
    """

    if ".exe" in path:
        new_path = path.split("simc.exe")[0]
    else:
        new_path = path[:-5]  # cut "/simc" from unix path
        if "engine" in new_path[-6:]:
            new_path = new_path[:-6]

    # add path to file to variable
    new_path += ".git/FETCH_HEAD"
    simc_hash: str = None
    try:
        with open(new_path, "r", encoding="utf-8") as f:
            for line in f:
                if "'bfa-dev'" in line:
                    simc_hash = line.split()[0]
    except FileNotFoundError:
        try:
            with open("../../SimulationCraft/.git/shallow", "r", encoding="utf-8") as f:
                for line in f:
                    simc_hash = line.strip()
        except FileNotFoundError:
            logger.warning(
                "Couldn't extract SimulationCraft git hash. Result files won't contain a sane hash."
            )
        except Exception as e:
            logger.error(e)
            raise e
    except Exception as e:
        logger.error(e)
        raise e

    return simc_hash


def request(
    url: str,
    *,
    apikey: str = "",
    data: dict = None,
    retries=6,
    session=None,
    timeout=30,
) -> dict:
    """Communicate with url and return response json dict. Handled
    retries, timeouts, and sticks to session if one is provided.

    Args:
        url (str): [description]
        apikey (str, optional): apikey to talk with url. Defaults to ''.
        data (dict, optional): [description]. Defaults to None.
        retries (int, optional): [description]. Defaults to 6 tries.
        session ([type], optional): [description]. Defaults to None.
        timeout (int, optional): [description]. Defaults to 7 seconds.

    Raises:
        ValueError: Connection could not be established, check your
            values or internet connection to the target.

    Returns:
        dict: Response dictionary from url
    """

    if session:
        s = session
    else:
        s = requests.Session()
        # https://stackoverflow.com/a/35504626/8002464
        retries_adapter = urllib3.util.retry.Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retries_adapter)
        # register adapter for target
        s.mount("https://www.raidbots.com/", adapter)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Bloodmallet's shitty tool",
    }

    # post
    if data:
        body = {
            "advancedInput": data,
            "apiKey": apikey,
            "iterations": 100000,
            "reportName": "Bloodmallet's shitty tool",
            "simcVersion": "nightly",
            "type": "advanced",
        }

        response = s.post(url, json=body, headers=headers, timeout=timeout)

        while response.status_code == 429:
            time.sleep(10)
            response = s.post(url, json=body, headers=headers, timeout=timeout)

    # get
    else:
        response = s.get(url, headers=headers, timeout=timeout)

    # if unexpected status code returned, raise error
    response.raise_for_status()

    return response.json()


class Args(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.custom_profile = False
        self.custom_apl = False
        self.custom_fight_style = False
        self.debug = False
        self.executable = settings.executable
        self.fight_styles = [
            "patchwerk",
        ]
        self.profileset_work_threads = settings.profileset_work_threads
        self.ptr = False
        self.raidbots = False
        self.single_sim = ""
        self.sim_all = False
        self.target_error = ""
        self.threads = settings.threads
        self.wow_class_spec_list = []


def logger_config(logger: logging.Logger, debug=False):
    # logging to file and console
    logger.setLevel(logging.DEBUG)

    # console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    if debug:
        console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # file handler
    file_handler = logging.FileHandler("log.txt", "w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(filename)s / %(funcName)s:%(lineno)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # error file handler
    error_handler = logging.FileHandler("error.log", "w", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        "%(asctime)s - %(filename)s / %(funcName)s:%(lineno)s - %(levelname)s - %(message)s"
    )
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)

    return logger


def arg_parse_config():
    parser = argparse.ArgumentParser(
        description="Simulate different aspects of World of Warcraft data."
    )
    parser.add_argument(
        "-a",
        "--all",
        dest="sim_all",
        action="store_const",
        const=True,
        default=False,
        help="Simulate races, trinkets, secondary distributions, and azerite traits for all specs and all talent combinations.",
    )
    parser.add_argument(
        "--executable",
        metavar="PATH",
        type=str,
        help="Relative path to SimulationCrafts executable. Default: '{}'".format(
            settings.executable
        ),
    )
    parser.add_argument(
        "--profileset_work_threads",
        metavar="NUMBER",
        type=str,
        help="Number of threads used per profileset by SimulationCraft. Default: '{}'".format(
            settings.profileset_work_threads
        ),
    )
    parser.add_argument(
        "--threads",
        metavar="NUMBER",
        type=str,
        help="Number of threads used by SimulationCraft. Default: '{}'".format(
            settings.threads
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_const",
        const=True,
        default=settings.debug,
        help="Enables debug modus. Default: '{}'".format(settings.debug),
    )
    parser.add_argument(
        "-ptr", action="store_const", const=True, default=False, help="Enables ptr."
    )
    # sim only one type of data generation for one spec
    parser.add_argument(
        "-s",
        "--single_sim",
        dest="single_sim",
        metavar="STRING",
        type=str,
        help="Activate a single simulation on the local machine. <simulation_types> are races, secondary_distributions, talents, trinkets, soul_binds, conduits, and legendaries. Input structure: <simulation_type>,<wow_class>,<wow_spec>,<fight_style> e.g. -s races,shaman,elemental,patchwerk",
    )
    parser.add_argument(
        "--custom_profile",
        action="store_const",
        const=True,
        default=False,
        help="Enables usage of 'custom_profile.txt' in addition to the base profile. Default: '{}'".format(
            settings.debug
        ),
    )
    parser.add_argument(
        "--custom_apl",
        action="store_const",
        const=True,
        default=False,
        help="Enables usage of 'custom_apl.txt' in addition to the base profile. Default: '{}'".format(
            settings.debug
        ),
    )
    parser.add_argument(
        "--custom_fight_style",
        action="store_const",
        const=True,
        default=False,
        help="Enables usage of 'custom_fight_style.txt' in addition to the base profile. Default: '{}'".format(
            settings.debug
        ),
    )
    parser.add_argument(
        "--target_error",
        metavar="STRING",
        type=str,
        help="Overwrites target_error for all simulations. Default: whatever is in setting.py",
    )
    parser.add_argument(
        "--raidbots",
        action="store_const",
        const=True,
        default=False,
        help="Don't try this at home",
    )

    return parser.parse_args()
