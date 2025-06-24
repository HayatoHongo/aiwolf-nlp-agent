from dataclasses import dataclass


@dataclass
class Role:
    """Enumeration type for role."""

    UNC = "UNC"
    """Uncertain."""

    POSSESSED = "POSSESSED"
    """Possessed human."""

    SEER = "SEER"
    """Seer."""

    VILLAGER = "VILLAGER"
    """Villager."""

    WEREWOLF = "WEREWOLF"
    """Werewolf."""

    ANY = "ANY"
    """Wildcard."""

    def __eq__(self, value: object) -> bool:
        if value in vars(self).values():
            return True
        return False
