import pytest
from pydantic import ValidationError

from anonymizer.mechanisms.randomized_response import RandomizedResponse, RandomizedResponseParameters, RandomizedResponseMode
from anonymizer.utils.discrete_distribution import DiscreteDistributionModel


def test_simple():
    # Always return true answer.
    mechanism = RandomizedResponse(["Yes", "No"], probability_distribution=[[1, 0], [0, 1]])
    assert mechanism.anonymize("No") == "No"
    assert mechanism.anonymize("Yes") == "Yes"
    thrown = False
    try:
        mechanism.anonymize("Foobar")
    except ValueError:
        thrown = True
    assert thrown

    # Mismatch between distribution and values.
    with pytest.raises(ValueError):
        RandomizedResponse(["Yes"], probability_distribution=[[1, 0], [0, 1]])


def test_coin():
    # Always return true answer.
    mechanism = RandomizedResponse.with_coin(["Yes", "No"], coin_p=1, default_value="<None>")
    assert mechanism.anonymize("Yes") == "Yes"
    assert mechanism.anonymize("No") == "No"
    assert mechanism.anonymize("Foobar") == "<None>"

    # Throw error.
    mechanism = RandomizedResponse.with_coin(["Yes", "No"], coin_p=1)
    with pytest.raises(ValueError):
        mechanism.anonymize("Foobar")

    # Always return other answer.
    weights = [[0, 1], [1, 0]]
    mechanism = RandomizedResponse.with_coin(["Yes", "No"], coin_p=0, probability_distribution=weights)
    assert mechanism.anonymize("Yes") == "No"
    assert mechanism.anonymize("No") == "Yes"


def test_dp():
    # Return true answer with very high probability.
    # The true answer has a weight of 1.0, while the wrong answer has a weight of ~3e-44.
    mechanism = RandomizedResponse.with_dp(["Yes", "No"], 100)
    assert mechanism.anonymize("Yes") == "Yes"
    assert mechanism.anonymize("No") == "No"

    # Throw error.
    mechanism = RandomizedResponse.with_coin(["Yes", "No"], coin_p=1)
    with pytest.raises(ValueError):
        mechanism.anonymize("Foobar")

    # Always return other answer.
    weights = [[0, 1], [1, 0]]
    mechanism = RandomizedResponse.with_coin(["Yes", "No"], coin_p=0, probability_distribution=weights)
    assert mechanism.anonymize("Yes") == "No"
    assert mechanism.anonymize("No") == "Yes"


def test_parameters_model():
    mechanism = RandomizedResponse(
        RandomizedResponseParameters(
            values=["Yes", "No"], probability_distribution=DiscreteDistributionModel(weights=[[1, 0], [0, 1]])
        )
    )
    assert mechanism.anonymize("No") == "No"
    assert mechanism.anonymize("Yes") == "Yes"

    with pytest.raises(ValidationError):
        RandomizedResponseParameters(
            values=["Yes"], probability_distribution=DiscreteDistributionModel(weights=[[1, 0], [0, 1]])
        )

    parameters = RandomizedResponseParameters(
        values=["Yes", "No"], probability_distribution=DiscreteDistributionModel(weights=[[1, 0], [0, 1]])
    )
    mechanism = parameters.build()
    assert mechanism.anonymize("No") == "No"
    assert mechanism.anonymize("Yes") == "Yes"

    with pytest.raises(ValidationError):
        RandomizedResponseParameters(
            mode=RandomizedResponseMode.dp,
            values=["Yes", "No"],
            probability_distribution=DiscreteDistributionModel(weights=[[1, 0], [0, 1]]),
        )

    with pytest.raises(ValidationError):
        RandomizedResponseParameters(
            mode=RandomizedResponseMode.coin,
            values=["Yes", "No"],
            probability_distribution=DiscreteDistributionModel(weights=[[1, 0], [0, 1]]),
        )

    # Return true answer with very high probability.
    # The true answer has a weight of 1.0, while the wrong answer has a weight of ~3e-44.
    parameters = RandomizedResponseParameters(mode=RandomizedResponseMode.dp, values=["Yes", "No"], epsilon=100,)
    mechanism = parameters.build()
    assert mechanism.anonymize("Yes") == "Yes"
    assert mechanism.anonymize("No") == "No"

    # Always return other answer.
    parameters = RandomizedResponseParameters(
        mode=RandomizedResponseMode.coin,
        values=["Yes", "No"],
        probability_distribution=DiscreteDistributionModel(weights=[[0, 1], [1, 0]]),
        coin_p=0,
    )
    mechanism = parameters.build()
    assert mechanism.anonymize("Yes") == "No"
    assert mechanism.anonymize("No") == "Yes"
