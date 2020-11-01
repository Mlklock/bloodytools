"""Welcome to bloodytools - a SimulationCraft automator/wrapper

Generate your data more easily without having to create each and every needed profile to do so by hand:
  - races
  - trinkets
  - azerite traits
  - secondary distributions
  - gear path

Output is usually saved as .json. But you can add different ways to output the data yourself.

Contact:
  - https://discord.gg/tFR2uvK Bloodmallet(EU)#8246

Github:
  - https://github.com/Bloodmallet/bloodytools

Support the development:
  - https://www.patreon.com/bloodmallet
  - https://www.paypal.me/bloodmallet

May 2018
"""

import datetime
import sys
import threading
import time
import logging

from bloodytools import settings

# from bloodytools.simulations.gear_path_simulation import gear_path_simulation
from bloodytools.simulations.conduit_simulation import conduit_simulation
from bloodytools.simulations.legendary_simulations import legendary_simulation
from bloodytools.simulations.race_simulation import race_simulation
from bloodytools.simulations.secondary_distribution_simulation import (
    secondary_distribution_simulation,
)
from bloodytools.simulations.soul_bind_simulation import soul_bind_simulation
from bloodytools.simulations.talent_simulation import talent_simulation
from bloodytools.simulations.trinket_simulation import trinket_simulation
from bloodytools.utils.utils import arg_parse_config
from bloodytools.utils.utils import get_simc_hash
from bloodytools.utils.utils import logger_config
from simc_support.game_data.WowSpec import WOWSPECS, get_wow_spec


def _update_settings(args: object, logger: logging.Logger) -> None:
    if args.single_sim:
        logger.debug("-s / --single_sim detected")
        try:
            simulation_type, wow_class, wow_spec, fight_style = args.single_sim.split(
                ","
            )
        except Exception:
            logger.error("-s / --single_sim arg is missing parameters. Read -h.")
            sys.exit("Input error. Bloodytools terminates.")

        # single sim will always use all cores unless --threads is defined
        settings.threads = ""
        settings.wow_class_spec_list = [
            get_wow_spec(wow_class, wow_spec),
        ]
        settings.fight_styles = [
            fight_style,
        ]
        if args.target_error:
            settings.target_error[fight_style] = args.target_error
        settings.iterations = "20000"
        # disable all simulation types
        settings.enable_race_simulations = False
        settings.enable_trinket_simulations = False
        settings.enable_secondary_distributions_simulations = False
        settings.enable_gear_path = False
        settings.enable_talent_simulations = False
        settings.enable_soul_bind_simulations = False
        settings.enable_conduit_simulations = False

        # set dev options
        settings.use_own_threading = False
        settings.use_raidbots = False

        if simulation_type == "races":
            settings.enable_race_simulations = True
        elif simulation_type == "trinkets":
            settings.enable_trinket_simulations = True
        elif simulation_type == "soul_binds":
            settings.enable_soul_bind_simulations = True
        elif simulation_type == "conduits":
            settings.enable_conduit_simulations = True
        elif simulation_type == "secondary_distributions":
            settings.enable_secondary_distributions_simulations = True
        elif simulation_type == "legendaries":
            settings.enable_legendary_simulations = True
        elif simulation_type == "talents":
            settings.enable_talent_simulations = True
        else:
            raise ValueError("Unknown simulation type entered.")

    # set new executable path if provided
    if args.executable:
        settings.executable = args.executable
        logger.debug("Set executable to {}".format(settings.executable))

    # set new threads if provided
    if args.threads:
        settings.threads = args.threads
        logger.debug("Set threads to {}".format(settings.threads))

    # set new profileset_work_threads if provided
    if args.profileset_work_threads:
        settings.profileset_work_threads = args.profileset_work_threads
        logger.debug(
            "Set profileset_work_threads to {}".format(settings.profileset_work_threads)
        )

    if args.ptr:
        settings.ptr = "1"

    if args.custom_profile:
        settings.custom_profile = args.custom_profile

    if args.custom_apl:
        settings.custom_apl = args.custom_apl
        settings.default_actions = "0"

    if args.custom_fight_style:
        settings.custom_fight_style = args.custom_fight_style

    if args.target_error:
        for fight_style in settings.target_error:
            settings.target_error[fight_style] = args.target_error

    if args.raidbots:
        settings.use_raidbots = True


def main(args=None):
    if not args:
        args = arg_parse_config()

    # activate debug mode as early as possible
    if args.debug:
        settings.debug = args.debug

    logger = logger_config(logging.getLogger("bloodytools"), args.debug)

    logger.debug("main start")
    logger.info("Bloodytools at your service.")

    _update_settings(args, logger)

    # only
    new_hash = get_simc_hash(settings.executable)
    if new_hash:
        settings.simc_hash = new_hash
    if not hasattr(settings, "simc_hash"):
        settings.simc_hash = None

    bloodytools_start_time = datetime.datetime.utcnow()

    # empty class-spec list? great, we'll run all class-spec combinations
    if not hasattr(settings, "wow_class_spec_list"):
        settings.wow_class_spec_list = WOWSPECS

    # list of all active threads. when empty, terminate tool
    thread_list = []

    # trigger race simulations
    if settings.enable_race_simulations:
        if not settings.use_own_threading:
            logger.info("Starting Race simulations.")

        if settings.use_own_threading:
            race_thread = threading.Thread(
                name="Race Thread",
                target=race_simulation,
                args=(settings),
            )
            thread_list.append(race_thread)
            race_thread.start()
        else:
            race_simulation(settings)

        if not settings.use_own_threading:
            logger.info("Race simulations finished.")

    # trigger trinket simulations
    if settings.enable_trinket_simulations:
        if not settings.use_own_threading:
            logger.info("Starting Trinket simulations.")

        if settings.use_own_threading:
            trinket_thread = threading.Thread(
                name="Trinket Thread", target=trinket_simulation, args=(settings,)
            )
            thread_list.append(trinket_thread)
            trinket_thread.start()
        else:
            trinket_simulation(settings)

        if not settings.use_own_threading:
            logger.info("Trinket simulations finished.")

    # trigger soul bind (nodes) simulations
    if settings.enable_soul_bind_simulations:
        if not settings.use_own_threading:
            logger.info("Starting Soul Bind simulations.")

        if settings.use_own_threading:
            soul_bind_thread = threading.Thread(
                name="Soul Bind Thread", target=soul_bind_simulation, args=(settings,)
            )
            thread_list.append(soul_bind_thread)
            soul_bind_thread.start()
        else:
            soul_bind_simulation(settings)

        if not settings.use_own_threading:
            logger.info("Soul Bind simulations finished.")

    # trigger conduit simulations
    if settings.enable_conduit_simulations:
        if not settings.use_own_threading:
            logger.info("Starting Conduit simulations.")

        if settings.use_own_threading:
            conduit_thread = threading.Thread(
                name="Conduit Thread", target=conduit_simulation, args=(settings,)
            )
            thread_list.append(conduit_thread)
            conduit_thread.start()
        else:
            conduit_simulation(settings)

        if not settings.use_own_threading:
            logger.info("Conduit simulations finished.")

    # trigger legendary simulations
    if settings.enable_legendary_simulations:
        if not settings.use_own_threading:
            logger.info("Starting Legendary simulations.")

        if settings.use_own_threading:
            legendary_thread = threading.Thread(
                name="Legendary Thread", target=legendary_simulation, args=(settings,)
            )
            thread_list.append(legendary_thread)
            legendary_thread.start()
        else:
            legendary_simulation(settings)

        if not settings.use_own_threading:
            logger.info("Legendary simulations finished.")

    # trigger secondary distributions
    if settings.enable_secondary_distributions_simulations:

        if not settings.use_own_threading:
            logger.info("Starting Secondary Distribtion simulations.")

        if settings.use_own_threading:
            secondary_distribution_thread = threading.Thread(
                name="Secondary Distribution Thread",
                target=secondary_distribution_simulation,
                args=(settings,),
            )
            thread_list.append(secondary_distribution_thread)
            secondary_distribution_thread.start()
        else:
            secondary_distribution_simulation(settings)

        if not settings.use_own_threading:
            logger.info("Secondary Distribution simulations finished.")

    # TODO: re-enable other simulation types
    # trigger gear path simulations
    # if settings.enable_gear_path:
    #     if not settings.use_own_threading:
    #         logger.info("Gear Path simulations start.")

    #     if settings.use_own_threading:
    #         gearing_path_thread = threading.Thread(
    #             name="Gear Path Thread",
    #             target=gear_path_simulation,
    #             args=(settings.wow_class_spec_list, settings)
    #         )
    #         thread_list.append(gearing_path_thread)
    #         gearing_path_thread.start()
    #     else:
    #         gear_path_simulation(settings.wow_class_spec_list, settings)

    #     if not settings.use_own_threading:
    #         logger.info("Gear Path simulations end.")

    # TODO: re-enable other simulation types
    # trigger talent simulations
    if settings.enable_talent_simulations:
        if not settings.use_own_threading:
            logger.info("Talent simulations start.")

        if settings.use_own_threading:
            talent_thread = threading.Thread(
                name="Talent Thread",
                target=talent_simulation,
                args=(settings,),
            )
            thread_list.append(talent_thread)
            talent_thread.start()
        else:
            talent_simulation(settings)

        if not settings.use_own_threading:
            logger.info("Talent simulations end.")

    while thread_list:
        time.sleep(1)
        for thread in thread_list:
            if thread.is_alive():
                logger.debug("{} is still in progress.".format(thread.getName()))
            else:
                logger.info("{} finished.".format(thread.getName()))
                thread_list.remove(thread)

    logger.info(
        "Bloodytools took {} to finish.".format(
            datetime.datetime.utcnow() - bloodytools_start_time
        )
    )
    logger.debug("main ended")


if __name__ == "__main__":
    main()
