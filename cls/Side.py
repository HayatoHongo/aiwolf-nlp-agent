from dataclasses import dataclass


@dataclass
class Side:
    UNC = "UNC"
    """Uncertain."""
    BLACK = "BLACK"
    """Black.WEREWOLF"""
    WHITE = "WHITE"
    """White.HUMAN"""

    def __eq__(self, value: object) -> bool:
        if value in vars(self).values():
            return True
        return False
