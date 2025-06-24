from dataclasses import dataclass


@dataclass
class Species:
    UNC = 'UNC'
    HUMAN = 'HUMAN'
    WEREWOLF = 'WEREWOLF'

    def __eq__(self, value: object) -> bool:
        if value in vars(self).values():
            return True
        return False
