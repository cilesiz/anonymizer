from typing import Union

from .generalization import GeneralizationParameters
from .pseudonymization import PseudonymizationParameters
from .randomized_response import RandomizedResponseParameters
from .suppression import SuppressionParameters


def mechanism_config_types_wo_stateful():
    return Union[GeneralizationParameters, PseudonymizationParameters, SuppressionParameters, RandomizedResponseParameters]


def mechanism_config_types():
    from .stateful_mechanism import StatefulMechanismParameters

    return Union[StatefulMechanismParameters, mechanism_config_types_wo_stateful()]
