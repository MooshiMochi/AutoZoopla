from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


class SparkleUpdater:
    """Sparkle auto-updater wrapper.

    On macOS this loads the bundled ``Sparkle.framework`` through pyobjc and
    drives ``SPUStandardUpdaterController`` (the standard Install / Skip This
    Version / Remind Me Later dialog). On every other platform it is a safe
    no-op, so the app runs unchanged during development on Windows/Linux.
    """

    def __init__(self) -> None:
        self._controller = None
        self._available = sys.platform == "darwin"

    @property
    def available(self) -> bool:
        return self._available

    def start(self, *, check_on_launch: bool = True) -> None:
        if not self._available:
            logger.debug("Updater unavailable on %s; skipping.", sys.platform)
            return
        try:  # pragma: no cover - macOS only
            controller_cls = self._load_sparkle()
            if controller_cls is None:
                logger.warning("Sparkle.framework not found in the app bundle.")
                return
            # startingUpdater:YES starts Sparkle but does NOT force a check — it
            # only wires up the scheduled checker. Sparkle intentionally skips
            # the very first launch and then honours SUScheduledCheckInterval
            # (24h), so a freshly installed app won't notice an update that is
            # already waiting. Start it here, then explicitly kick a silent
            # background check below so a pending update is offered right away.
            self._controller = (
                controller_cls.alloc().initWithStartingUpdater_updaterDelegate_userDriverDelegate_(
                    True, None, None
                )
            )
            if check_on_launch:
                self._check_in_background()
        except Exception:  # pragma: no cover - macOS only
            logger.exception("Failed to initialise the Sparkle updater.")

    def _check_in_background(self) -> None:  # pragma: no cover - macOS only
        """Trigger Sparkle's silent check: prompts only if an update exists."""
        if self._controller is None:
            return
        try:
            self._controller.updater().checkForUpdatesInBackground()
        except Exception:
            logger.exception("Background update check failed to start.")

    def check_for_updates(self) -> None:
        if self._controller is not None:  # pragma: no cover - macOS only
            self._controller.checkForUpdates_(None)

    @staticmethod
    def _load_sparkle():  # pragma: no cover - macOS only
        import objc
        from Foundation import NSBundle

        bundle = NSBundle.mainBundle()
        framework_path = bundle.privateFrameworksPath()
        if not framework_path:
            return None
        objc.loadBundle(
            "Sparkle",
            globals(),
            bundle_path=framework_path + "/Sparkle.framework",
        )
        return globals().get("SPUStandardUpdaterController")
