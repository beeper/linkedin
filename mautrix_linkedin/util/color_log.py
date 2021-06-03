from mautrix.util.logging.color import (
    ColorFormatter as BaseColorFormatter,
    PREFIX,
    RESET,
)

# TODO different color for LinkedIn?
LINKEDIN_COLOR = PREFIX + "35;1m"  # magenta


class ColorFormatter(BaseColorFormatter):
    def _color_name(self, module: str) -> str:
        if module.startswith("maufbapi"):
            return LINKEDIN_COLOR + module + RESET
        return super()._color_name(module)
