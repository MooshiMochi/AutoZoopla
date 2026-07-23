import sys

from relister.gui.updater import SparkleUpdater


def test_updater_is_noop_off_macos():
    updater = SparkleUpdater()
    if sys.platform != "darwin":
        assert updater.available is False
    # start() / check_for_updates() must never raise, regardless of platform.
    updater.start()
    updater.check_for_updates()


def test_updater_reports_platform_availability():
    updater = SparkleUpdater()
    assert updater.available is (sys.platform == "darwin")
